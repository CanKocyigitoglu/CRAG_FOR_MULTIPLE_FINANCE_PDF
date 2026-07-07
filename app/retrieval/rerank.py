"""Cross-encoder reranking with graceful degradation.

We over-retrieve with hybrid search, then rerank the candidates with a local
cross-encoder and keep the top few. If sentence-transformers/torch isn't
installed (see requirements-rerank.txt) or RERANKER=off, we fall back to the
existing RRF order — the app stays functional, just slightly less precise.
"""
from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)

_model = None
_load_failed = False


def _get_model():
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model
    try:
        from sentence_transformers import CrossEncoder

        _model = CrossEncoder(settings.rerank_model)
        logger.info("loaded cross-encoder reranker: %s", settings.rerank_model)
    except Exception as exc:
        _load_failed = True
        logger.warning(
            "cross-encoder unavailable (%s); falling back to RRF ordering. "
            "Install requirements-rerank.txt to enable reranking.",
            exc,
        )
    return _model


def rerank(query: str, candidates: list[dict], top_k: int | None = None) -> list[dict]:
    top_k = top_k or settings.final_top_k
    if settings.reranker == "off" or not candidates:
        return candidates[:top_k]

    model = _get_model()
    if model is None:
        return candidates[:top_k]

    scores = model.predict([(query, c["text"]) for c in candidates])
    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    return [{**c, "rerank_score": float(s)} for c, s in ranked[:top_k]]
