"""LLM interface + grounded answer assembly with citations.

Local Ollama by default; provider is env-swappable. The prompt forces the model
to answer only from retrieved context and to cite sources as [n]; we map those
markers back to real (doc, page) references so every answer carries verifiable
provenance.
"""
from __future__ import annotations

import logging
import math
import re

import httpx

from app.config import settings
from app.ingestion.embed import embed_texts

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(180.0)

_SYSTEM = (
    "You are a financial-document assistant. Answer ONLY using the numbered "
    "sources provided. Cite every claim with its source marker like [1] or [2]. "
    "If the answer is not in the sources, say you don't have that information in "
    "the documents. Do not use outside knowledge and never invent figures. "
    "Be concise and precise with numbers."
)


def chat(messages: list[dict], fmt: dict | None = None, temperature: float = 0.1) -> str:
    """Low-level chat completion. messages = [{'role','content'}, ...].

    `fmt` is an optional JSON schema passed to Ollama's native structured-output
    `format` field (used by the CRAG grader/verifier); when set, the returned
    content is a JSON string conforming to that schema.
    """
    if settings.llm_provider != "ollama":
        raise NotImplementedError(
            f"llm_provider '{settings.llm_provider}' not implemented; use 'ollama'"
        )
    payload: dict = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if fmt is not None:
        payload["format"] = fmt
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(f"{settings.ollama_url}/api/chat", json=payload)
        if resp.status_code != 200:
            # Ollama puts the real cause (e.g. "llama runner process has
            # terminated" on out-of-memory) in the body; surface it instead of
            # losing it to raise_for_status.
            detail = resp.text.strip()
            logger.error(
                "Ollama /api/chat failed (%s) for model '%s': %s",
                resp.status_code, settings.llm_model, detail,
            )
            raise RuntimeError(
                f"Ollama chat failed ({resp.status_code}) for model "
                f"'{settings.llm_model}': {detail}"
            )
        return resp.json()["message"]["content"].strip()


def complete(prompt: str) -> str:
    return chat([{"role": "user", "content": prompt}])


def _dedupe_sources(chunks: list[dict]) -> list[dict]:
    """Collapse reranked child chunks to unique parent contexts, preserving order."""
    seen: set[tuple] = set()
    sources: list[dict] = []
    for c in chunks:
        key = (c.get("doc"), c.get("page"), c.get("parent_text"))
        if key in seen:
            continue
        seen.add(key)
        sources.append(c)
    return sources


def _snippet(text: str, limit: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _match_scores(query: str, texts: list[str]) -> list[float | None]:
    """Semantic match % of each source text against the query.

    Cosine similarity of their embeddings, mapped to 0–100. This is the same
    signal that drove dense retrieval (Qdrant uses cosine), recomputed here
    because RRF/rerank overwrite the original score upstream. Best-effort: if
    embedding fails we return None so the answer still ships without a score.
    """
    if not texts:
        return []
    try:
        vecs = embed_texts([query] + texts)
    except Exception as exc:
        logger.warning("could not compute citation match scores: %s", exc)
        return [None] * len(texts)
    qv, doc_vs = vecs[0], vecs[1:]
    return [round(max(0.0, _cosine(qv, dv)) * 100, 1) for dv in doc_vs]


def generate_answer(query: str, chunks: list[dict], history: list[dict] | None = None) -> tuple[str, list[dict]]:
    """Return (answer, citations). citations = [{doc, page, snippet}]."""
    sources = _dedupe_sources(chunks)
    if not sources:
        return "I don't have any indexed documents to answer that from.", []

    context = "\n\n".join(
        f"[{i}] ({s.get('doc')}, p.{s.get('page')})\n{s.get('parent_text') or s.get('text')}"
        for i, s in enumerate(sources, start=1)
    )
    user = f"Sources:\n{context}\n\nQuestion: {query}"

    messages = [{"role": "system", "content": _SYSTEM}]
    messages += history or []
    messages.append({"role": "user", "content": user})

    answer = chat(messages)

    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer) if 1 <= int(n) <= len(sources)})
    used = [sources[n - 1] for n in cited] if cited else sources
    matches = _match_scores(query, [s.get("text", "") for s in used])
    citations = [
        {
            "doc": s.get("doc"),
            "page": s.get("page"),
            "snippet": _snippet(s.get("text", "")),
            "match": m,
        }
        for s, m in zip(used, matches)
    ]
    return answer, citations
