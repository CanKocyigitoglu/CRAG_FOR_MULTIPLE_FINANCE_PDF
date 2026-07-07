"""Hybrid retrieval: dense (semantic) + BM25 (keyword), fused with RRF.

Dense vectors live in Qdrant. BM25 is built in-memory from the same chunk
payloads (Qdrant is the source of truth), rebuilt when the chunk count changes —
this keeps the two retrievers in sync without a separate sparse store, which
embedded Qdrant doesn't need for a portfolio-scale corpus.
"""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from app.config import settings
from app.ingestion.embed import embed_query
from app.ingestion.index import count_chunks, iter_all_chunks, search_dense

_bm25: BM25Okapi | None = None
_payloads: list[dict] = []
_indexed_count = -1

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _key(p: dict) -> tuple:
    return (p.get("doc_id"), p.get("page"), p.get("text"))


def _ensure_bm25() -> None:
    """Rebuild the BM25 index if the corpus changed since we last built it."""
    global _bm25, _payloads, _indexed_count
    current = count_chunks()
    if _bm25 is not None and current == _indexed_count:
        return
    _payloads = iter_all_chunks()
    _bm25 = BM25Okapi([_tokenize(p["text"]) for p in _payloads]) if _payloads else None
    _indexed_count = current


def _bm25_search(query: str, top_k: int, doc_ids: list[str] | None) -> list[dict]:
    _ensure_bm25()
    if _bm25 is None:
        return []
    scores = _bm25.get_scores(_tokenize(query))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    out: list[dict] = []
    for i in ranked:
        p = _payloads[i]
        if doc_ids and p.get("doc_id") not in doc_ids:
            continue
        out.append({**p, "score": float(scores[i])})
        if len(out) >= top_k:
            break
    return out


def _rrf(ranked_lists: list[list[dict]], k: int = 60) -> list[dict]:
    scores: dict[tuple, float] = {}
    items: dict[tuple, dict] = {}
    for lst in ranked_lists:
        for rank, item in enumerate(lst):
            key = _key(item)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            items[key] = item
    ordered = sorted(scores, key=lambda key: scores[key], reverse=True)
    return [{**items[key], "score": scores[key]} for key in ordered]


def hybrid_search(query: str, top_k: int | None = None, doc_ids: list[str] | None = None) -> list[dict]:
    """Return the top_k chunk payloads by fused dense+BM25 relevance."""
    top_k = top_k or settings.retrieve_top_k
    dense = search_dense(embed_query(query), top_k, doc_ids)
    sparse = _bm25_search(query, top_k, doc_ids)
    return _rrf([dense, sparse])[:top_k]
