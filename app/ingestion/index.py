"""Qdrant vector store — embedded on-disk mode (no Docker).

NOTE: embedded Qdrant keeps an exclusive lock on QDRANT_PATH, so only one process
can open it at a time. The API server owns the store while running; run the batch
`scripts/ingest_corpus.py` with the API stopped. Set QDRANT_URL to point at a real
Qdrant server if you outgrow embedded mode.
"""
from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    PointStruct,
    VectorParams,
)

from app.config import settings
from app.ingestion.chunk import Chunk
from app.ingestion.embed import embed_texts, embedding_dim

_client: QdrantClient | None = None
_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000042")


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        if settings.qdrant_url:
            _client = QdrantClient(url=settings.qdrant_url)
        else:
            _client = QdrantClient(path=settings.qdrant_path)
    return _client


def ensure_collection(dim: int | None = None) -> None:
    client = get_client()
    if client.collection_exists(settings.qdrant_collection):
        return
    client.create_collection(
        settings.qdrant_collection,
        vectors_config=VectorParams(size=dim or embedding_dim(), distance=Distance.COSINE),
    )
    # Payload indexes only speed up a real Qdrant server; embedded mode ignores
    # them (and warns), so only create it when talking to a server.
    if settings.qdrant_url:
        client.create_payload_index(settings.qdrant_collection, "doc_id", field_schema="keyword")


def index_chunks(chunks: list[Chunk]) -> int:
    """Embed child texts and upsert them. Returns the number of chunks indexed."""
    if not chunks:
        return 0
    ensure_collection()
    vectors = embed_texts([c.text for c in chunks])
    points = [
        PointStruct(
            id=str(uuid.uuid5(_NAMESPACE, c.id)),
            vector=vec,
            payload={
                "doc_id": c.doc_id,
                "doc": c.doc,
                "page": c.page,
                "text": c.text,
                "parent_text": c.parent_text,
            },
        )
        for c, vec in zip(chunks, vectors)
    ]
    get_client().upsert(settings.qdrant_collection, points=points)
    return len(points)


def _doc_filter(doc_ids: list[str] | None) -> Filter | None:
    if not doc_ids:
        return None
    return Filter(must=[FieldCondition(key="doc_id", match=MatchAny(any=doc_ids))])


def search_dense(query_vector: list[float], top_k: int, doc_ids: list[str] | None = None) -> list[dict]:
    """Dense (semantic) search. Returns payload dicts with an added 'score'."""
    if not get_client().collection_exists(settings.qdrant_collection):
        return []
    res = get_client().query_points(
        settings.qdrant_collection,
        query=query_vector,
        limit=top_k,
        query_filter=_doc_filter(doc_ids),
        with_payload=True,
    )
    return [{**p.payload, "score": p.score} for p in res.points]


def iter_all_chunks() -> list[dict]:
    """Scroll every chunk payload (used to (re)build the in-memory BM25 index)."""
    client = get_client()
    if not client.collection_exists(settings.qdrant_collection):
        return []
    out: list[dict] = []
    offset = None
    while True:
        points, offset = client.scroll(
            settings.qdrant_collection,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        out.extend(p.payload for p in points)
        if offset is None:
            break
    return out


def count_chunks(doc_id: str | None = None) -> int:
    client = get_client()
    if not client.collection_exists(settings.qdrant_collection):
        return 0
    return client.count(settings.qdrant_collection, count_filter=_doc_filter([doc_id] if doc_id else None)).count
