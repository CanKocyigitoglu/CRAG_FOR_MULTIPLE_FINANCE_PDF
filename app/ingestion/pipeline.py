"""The indexing path: parse -> chunk -> embed+index. Shared by the API upload
endpoint and the batch corpus script so both stay identical."""
from __future__ import annotations

from app.ingestion.chunk import chunk_pages
from app.ingestion.index import index_chunks
from app.ingestion.parse import parse_pdf


def ingest_pdf(path: str, doc_id: str, filename: str) -> int:
    """Parse, chunk, embed, and index one PDF. Returns the number of chunks indexed."""
    pages = parse_pdf(path)
    chunks = chunk_pages(pages, doc_id, filename)
    return index_chunks(chunks)
