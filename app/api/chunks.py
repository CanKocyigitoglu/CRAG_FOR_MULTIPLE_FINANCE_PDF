"""GET /api/chunks — read-only inspection of what's stored in Qdrant.

Powers the Chunks Explorer UI. Returns index-level metadata (where/how the data
is stored) plus every chunk's content and provenance (doc + page). Additive to the
§5 contract — the chat frontend is unaffected.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.ingestion.index import get_client, iter_all_chunks

router = APIRouter()


def _index_meta(total_chunks: int, total_documents: int) -> dict:
    dim, distance = None, None
    client = get_client()
    if client.collection_exists(settings.qdrant_collection):
        params = client.get_collection(settings.qdrant_collection).config.params.vectors
        # unnamed (single) vector config exposes .size / .distance directly
        dim = getattr(params, "size", None)
        dist = getattr(params, "distance", None)
        distance = getattr(dist, "value", None) or (str(dist) if dist else None)
    return {
        "collection": settings.qdrant_collection,
        "embedding_model": settings.embedding_model,
        "vector_dim": dim,
        "distance": distance,
        "total_chunks": total_chunks,
        "total_documents": total_documents,
    }


@router.get("/api/chunks")
async def list_chunks() -> dict:
    rows = iter_all_chunks()
    chunks = [
        {
            "doc_id": p.get("doc_id"),
            "doc": p.get("doc"),
            "page": p.get("page"),
            "text": p.get("text"),
            "parent_text": p.get("parent_text"),
            "child_len": len(p.get("text") or ""),
            "parent_len": len(p.get("parent_text") or ""),
        }
        for p in rows
    ]
    chunks.sort(key=lambda c: (c["doc"] or "", c["page"] or 0))

    # per-document running index ("chunk k of n") for nicer display
    counters: dict[str, int] = {}
    for c in chunks:
        counters[c["doc_id"]] = counters.get(c["doc_id"], 0) + 1
        c["doc_index"] = counters[c["doc_id"]]

    documents = sorted({(c["doc_id"], c["doc"]) for c in chunks}, key=lambda d: d[1] or "")
    return {
        "meta": _index_meta(len(chunks), len(documents)),
        "documents": [{"doc_id": d[0], "doc": d[1], "chunks": counters[d[0]]} for d in documents],
        "chunks": chunks,
    }
