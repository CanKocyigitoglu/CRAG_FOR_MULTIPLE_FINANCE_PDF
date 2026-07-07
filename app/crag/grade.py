"""Document relevance grading — the "corrective" signal in Corrective RAG.

Each retrieved document is graded on its own (one LLM call per doc, per the
chosen design) using Ollama's native structured output. Grading is bounded to
the top `crag_grade_top_k` reranked docs so the call count stays predictable,
and the count is returned for logging.

The per-doc scores are collapsed into one of three verdicts:
  - correct    : at least one doc scores >= crag_relevance_threshold
  - incorrect  : the best doc scores <= crag_incorrect_max (nothing useful)
  - ambiguous  : in between (borderline docs, but none clearly relevant)
"""
from __future__ import annotations

import json
import logging

from app.config import settings
from app.generation.generate import chat

logger = logging.getLogger(__name__)

_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant": {"type": "boolean"},
        "score": {"type": "number"},
    },
    "required": ["relevant", "score"],
}

_SYSTEM = (
    "You grade whether a SINGLE document is relevant to answering the user's "
    "question about financial documents. Return JSON with `relevant` (boolean) "
    "and `score` (0.0-1.0 confidence that this document helps answer the "
    "question). Judge relevance only, not whether the answer is correct."
)


def _grade_one(query: str, doc: dict) -> float:
    text = doc.get("parent_text") or doc.get("text") or ""
    user = f"Question: {query}\n\nDocument:\n{text[:2000]}"
    raw = chat(
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
        fmt=_SCHEMA,
        temperature=0.0,
    )
    return float(json.loads(raw).get("score", 0.0))


def grade_documents(query: str, documents: list[dict]) -> tuple[str, list[dict], int]:
    """Return (verdict, relevant_docs, llm_calls). verdict in
    {'correct','incorrect','ambiguous'}."""
    graded = documents[: settings.crag_grade_top_k]
    scored: list[tuple[dict, float]] = []
    calls = 0
    for d in graded:
        try:
            score = _grade_one(query, d)
        except Exception as exc:  # a bad/unparseable grade shouldn't abort the round
            logger.warning("grade call failed (%s); treating doc as irrelevant", exc)
            score = 0.0
        calls += 1
        scored.append((d, score))

    relevant = [d for d, s in scored if s >= settings.crag_relevance_threshold]
    best = max((s for _, s in scored), default=0.0)
    if relevant:
        verdict = "correct"
    elif best <= settings.crag_incorrect_max:
        verdict = "incorrect"
    else:
        verdict = "ambiguous"

    logger.info(
        "CRAG grade=%s best=%.2f relevant=%d/%d calls=%d",
        verdict, best, len(relevant), len(graded), calls,
    )
    return verdict, relevant, calls
