"""POST /api/upload and GET /api/status/{doc_id}.

Ingestion is slow (parse + embed), so upload returns immediately with status
"indexing" and the work runs in a background task. Embedded Qdrant keeps a
single writer, so we serialize ingestion with a lock.
"""
from __future__ import annotations

import logging
import re
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, UploadFile

from app.ingestion.pipeline import ingest_pdf

logger = logging.getLogger(__name__)
router = APIRouter()

RAW_DIR = Path("data/raw")
_ingest_lock = threading.Lock()

# doc_id -> {"status": "indexing"|"ready"|"error", "chunks": int|None}
_status: dict[str, dict] = {}


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) or "file.pdf"


def _run_ingest(path: str, doc_id: str, filename: str) -> None:
    with _ingest_lock:
        try:
            n = ingest_pdf(path, doc_id, filename)
            _status[doc_id] = {"status": "ready", "chunks": n}
            logger.info("indexed %s (%s): %d chunks", filename, doc_id, n)
        except Exception as exc:
            _status[doc_id] = {"status": "error", "chunks": None}
            logger.exception("ingestion failed for %s: %s", filename, exc)


@router.post("/api/upload")
async def upload(files: list[UploadFile], background: BackgroundTasks) -> list[dict]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for f in files:
        doc_id = uuid.uuid4().hex[:12]
        filename = f.filename or f"{doc_id}.pdf"
        dest = RAW_DIR / f"{doc_id}_{_safe_name(filename)}"
        dest.write_bytes(await f.read())

        _status[doc_id] = {"status": "indexing", "chunks": None}
        background.add_task(_run_ingest, str(dest), doc_id, filename)
        results.append({"doc_id": doc_id, "filename": filename, "status": "indexing"})
    return results


@router.get("/api/status/{doc_id}")
async def status(doc_id: str) -> dict:
    return _status.get(doc_id, {"status": "error", "chunks": None})
