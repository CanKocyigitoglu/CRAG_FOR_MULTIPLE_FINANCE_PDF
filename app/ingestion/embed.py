"""Embeddings. Local Ollama by default; provider is env-swappable.

Only the Ollama path is implemented for Milestone 1. OpenAI/Cohere are wired as
explicit NotImplementedError so the swap point is obvious and honest.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BATCH = 64
_TIMEOUT = httpx.Timeout(120.0)
# Safety cap comfortably under nomic-embed-text's ~2048-token context. Chunking
# already keeps children small; this only guards against a pathological input so
# one oversized chunk can't 400 and abort a whole document's ingestion.
_MAX_CHARS = 4000


def _clip(texts: list[str]) -> list[str]:
    over = sum(1 for t in texts if len(t) > _MAX_CHARS)
    if over:
        logger.warning("%d chunk(s) exceeded %d chars; truncated for embedding", over, _MAX_CHARS)
    return [t[:_MAX_CHARS] for t in texts]


def _ollama_embed(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    with httpx.Client(timeout=_TIMEOUT) as client:
        for i in range(0, len(texts), _BATCH):
            batch = texts[i : i + _BATCH]
            resp = client.post(
                f"{settings.ollama_url}/api/embed",
                json={"model": settings.embedding_model, "input": batch},
            )
            resp.raise_for_status()
            out.extend(resp.json()["embeddings"])
    return out


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    texts = _clip(texts)
    if settings.embedding_provider == "ollama":
        return _ollama_embed(texts)
    raise NotImplementedError(
        f"embedding_provider '{settings.embedding_provider}' not implemented; use 'ollama'"
    )


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def embedding_dim() -> int:
    """Probe the model once for its vector dimension (keeps us model-agnostic)."""
    return len(embed_query("dimension probe"))
