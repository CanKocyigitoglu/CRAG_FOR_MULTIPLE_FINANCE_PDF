"""FastAPI app: CORS, routers, and the static frontend."""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import chat, chunks, conversations, upload
from app.config import settings
from app.ingestion.index import count_chunks

logging.basicConfig(level=logging.INFO)

# On Windows, mimetypes reads .js from the registry (often text/plain), and
# browsers refuse to execute ES module scripts served with a non-JS MIME type.
# Force the correct types so the built SPA loads.
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")

app = FastAPI(title="Finance RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(chunks.router)
app.include_router(conversations.router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "chunks": count_chunks()}


# Serve the built React app (frontend/dist) from the same origin
# (open http://localhost:8000). Mounted last so /api/* routes take precedence.
# In dev, run `npm run dev` (Vite on :5173) which proxies /api to :8000 instead.
_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
