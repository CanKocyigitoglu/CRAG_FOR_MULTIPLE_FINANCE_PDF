# Finance RAG

Retrieval-Augmented Generation over a corpus of financial PDFs, with a web UI for
grounded, **cited** Q&A and multi-turn follow-ups.

This is **Milestone 1** from [CLAUDE.md](CLAUDE.md) §9: the end-to-end retrieval
core, running **Docker-free and ~£0** on local open-source models (Ollama).

## What's implemented

**Offline indexing:** `parse (PyMuPDF text + pdfplumber tables) → sentence-aware
parent-child chunking → Ollama embeddings → Qdrant (embedded, on-disk)`

**Online query:** `history-aware rewrite → hybrid retrieval (dense + BM25 + RRF) →
cross-encoder rerank (optional) → grounded generation with [n] citations`

- FastAPI backend implementing the [§5 API contract](CLAUDE.md) exactly, plus an
  additive read-only `GET /api/chunks` for the Chunks Explorer.
- **React (Vite) frontend** in `frontend/` with two views:
  - **Chat** — grounded, cited Q&A.
  - **Chunks Explorer** — visualizes exactly what's stored in Qdrant: index
    metadata (collection, embedding model, vector dim, distance), a per-document
    filter, and one card per chunk showing its **source (doc + page)**, the
    **CHILD** text (embedded/BM25-indexed) and the **PARENT** context (sent to the
    LLM), with text search + highlight.
- Multi-turn: follow-ups like *"what about 2022?"* are rewritten to standalone
  queries before retrieval.

**Deferred to later milestones** (kept honest — not built yet): PII/injection input
guardrails, output faithfulness guardrails, RAGAS/DeepEval evaluation, Langfuse
tracing, Redis semantic cache, RabbitMQ async ingestion. Redis/RabbitMQ need Docker.

## Stack (this build)

| Layer | Choice | Notes |
|---|---|---|
| Vector store | **Qdrant embedded** (on-disk, no Docker) | single-writer; set `QDRANT_URL` to use a server |
| Embeddings | **Ollama `nomic-embed-text`** (768-d) | swappable via env |
| Generation | **Ollama `qwen2:7b`** | low temperature; swappable via env |
| Sparse | **BM25** (`rank-bm25`, in-memory, rebuilt from Qdrant) | fused with dense via RRF |
| Rerank | cross-encoder (optional) | graceful fallback to RRF if not installed |

## Prerequisites

- **Python 3.13** (a `.venv/` is already created in this repo).
- **Node.js 16+** and npm (for the React frontend; verified on Node 16 + Vite 4).
- **[Ollama](https://ollama.com)** running, with the models pulled:
  ```bash
  ollama pull nomic-embed-text
  ollama pull qwen2:7b
  ```

## Setup

The Python virtualenv and core deps are already installed. To recreate from scratch:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# optional (heavy: torch) — enables cross-encoder reranking:
.venv/Scripts/python -m pip install -r requirements-rerank.txt

# frontend deps + production build (outputs frontend/dist, served by FastAPI)
cd frontend && npm install && npm run build && cd ..
```

Copy `.env.example` to `.env` to override any defaults (all defaults are local/OSS).

## Run

**Single-origin (simplest):** build the frontend once (above), then run the API —
it serves the built app at the same origin.

```bash
.venv/Scripts/python -m uvicorn app.main:app        # NOTE: no --reload (see below)
# open http://localhost:8000
```

**Frontend dev mode (hot reload):** run the API and Vite side by side; Vite proxies
`/api` to the backend.

```bash
.venv/Scripts/python -m uvicorn app.main:app        # terminal 1  (:8000)
cd frontend && npm run dev                           # terminal 2  (:5173)
# open http://localhost:5173
```

> **Don't use `uvicorn --reload` with embedded Qdrant.** On restart the new worker
> tries to open the store before the old one releases its single-writer lock and
> crashes. Run without `--reload`, or point `QDRANT_URL` at a Qdrant server.

Upload a PDF in the Chat sidebar, wait for `ready`, then ask questions — or open the
**Chunks Explorer** tab to see what's indexed. A demo file is already indexed at
`data/raw/sample_financials.pdf`.

### Batch pre-indexing (offline)

Put PDFs in `data/raw/` and run — **with the API stopped** (embedded Qdrant is
single-writer):

```bash
.venv/Scripts/python scripts/ingest_corpus.py --path data/raw
```

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

## Notes / known limits

- **Embedded Qdrant is single-writer.** The API owns the store while running; run
  the batch script only when the API is stopped. Point `QDRANT_URL` at a real
  Qdrant server to lift this.
- **Performance.** `qwen2:7b` is RAM-heavy. Each follow-up does rewrite (LLM) →
  embed → generate; if Ollama has to swap `qwen2` and `nomic-embed-text` in and out
  of memory, latency spikes. On constrained machines, set `LLM_MODEL=llama3.2` for
  a snappier experience, or keep both models resident via Ollama `keep_alive`.
- **Streaming is off** (`STREAMING = false` in the frontend). `/api/chat` returns
  `{answer, citations}` in one response.
- **OCR** for scanned pages is not applied (needs a system Tesseract binary);
  low-text pages are logged, not silently dropped.
- **Reranking** falls back to RRF ordering if `requirements-rerank.txt` isn't
  installed — the app stays functional, just slightly less precise.
