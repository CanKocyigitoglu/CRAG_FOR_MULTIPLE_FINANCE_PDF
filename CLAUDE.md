# CLAUDE.md

Context and working guide for this repository. Claude Code reads this file at the
project root to understand the project before generating or editing code.

> **Accuracy note for whoever maintains this file:** tool names, model names, library
> APIs, and prices below reflect planning decisions and may be out of date. **Verify
> current versions, model availability, and pricing against each tool's official
> documentation before relying on them.** Do not treat any number here as a guaranteed
> fact.

---

## 1. What this project is

A **production-grade Retrieval-Augmented Generation (RAG) system over a large corpus of
financial PDFs**, with a web interface to:

- ingest/query a pre-indexed finance-document corpus,
- ask questions and get **grounded, cited** answers,
- ask **multiple questions in one session** (follow-ups keep earlier context).

It is a **portfolio project shaped like production infrastructure**: the goal is to
implement every meaningful layer of a real RAG system (not a notebook demo) and to be
able to justify each design decision. Differentiators to prioritise: **evaluation,
guardrails, and observability**.

## 2. Guiding principles / scope

- **Local / open-source first.** Target running cost ≈ £0 for development. Prefer
  self-hosted OSS over paid managed services. Paid services are **optional toggles**,
  not defaults. **Do not add a paid dependency without asking.**
- **Separate the two pipelines.** Offline **indexing** and online **query** must be
  distinct code paths / services, not one monolith.
- **Finance data caveat.** Financial PDFs are table- and layout-heavy. **Parsing quality
  is the highest-leverage correctness factor** — bad table extraction silently produces
  wrong numbers. Treat layout/table-aware parsing as a priority, not an afterthought.
- **Citations are first-class.** Every answer should carry verifiable source references
  (document + page). The frontend already renders these.
- **Keep the frontend API contract stable** (see §5). The frontend in `frontend/index.html`
  already depends on it.
- **Multi-turn needs history-aware query rewriting.** Follow-up questions (e.g. "what about
  2023?") must be rewritten using conversation history before retrieval, or retrieval fails.

## 3. Architecture

**Offline indexing pipeline** (batch, run ahead of time — see `scripts/ingest_corpus.py`):
`ingest → parse (layout/table-aware) → chunk (semantic + parent-child) → embed → index
(dense + sparse) → freshness/incremental updates`

**Online query pipeline** (per request, under a latency budget):
`query understanding (history-aware rewrite + input guardrails) → hybrid retrieval
(dense + BM25 + RRF + metadata filter) → rerank → context assembly (prompt + grounding +
citations + access checks) → generate → output guardrails (citation/faithfulness check)`

**Cross-cutting:** evaluation harness, observability/tracing, semantic caching, async
ingestion, security/access control, deployment.

## 4. Tech stack (chosen defaults + rationale)

All defaults are local/OSS. Each is swappable via env config (see §7). **Confirm current
versions/models before installing.**

| Layer | Default (local/OSS, ~£0) | Optional paid toggle | Notes |
|---|---|---|---|
| Backend API | **FastAPI** (Python) | — | async, StreamingResponse for SSE |
| Parsing | layout/table-aware parser (e.g. **Unstructured**) + OCR fallback | — | finance = tables; verify best current parser |
| Chunking | semantic + **parent-child** | — | avoid naive fixed-size splitting |
| Embeddings | local **sentence-transformers / BGE** (confirm current model) | OpenAI / Cohere embeddings | keep model swappable |
| Vector store | **Qdrant** (self-hosted, Docker) — *default choice for a large corpus + hybrid* | Pinecone / Qdrant Cloud | **pgvector is an acceptable simpler swap if <~1M vectors; decide before scaffolding** |
| Sparse / keyword | **BM25** (via Qdrant sparse vectors — confirm current API) | — | combined with dense via RRF |
| Reranking | local **cross-encoder** (sentence-transformers) | **Cohere Rerank** (free trial; verify pricing) | over-retrieve then rerank to top 3–5 |
| Generation | local **Ollama** (confirm current model, e.g. a Llama variant) | OpenAI / Anthropic / Cohere | low temperature for factual Q&A; streaming |
| Input guardrails | OSS PII / prompt-injection checks | — | run before retrieval |
| Output guardrails | citation checking / faithfulness verification | — | verify claims against retrieved chunks |
| Evaluation | **RAGAS** + **DeepEval** | — | golden set of 50–200 Q&A; CI gate |
| Observability | **Langfuse** or **Arize Phoenix** (self-host) | LangSmith (free tier) | trace latency, cost, retrieval quality |
| Semantic cache | **Redis** | — | cache frequent/similar queries |
| Async ingestion | **RabbitMQ** | — | background processing for slow indexing |
| Deploy | **Docker + docker-compose** | Kubernetes / Azure | K8s + Azure are stretch goals |
| Frontend | **vanilla HTML/CSS/JS** (`frontend/index.html`) | React (Vite) as future showcase | zero build; served static |

> Orchestration: LangChain/LlamaIndex may be used as glue where helpful, but keep hot
> paths (embedding, retrieval) as direct calls to avoid latency overhead. Confirm current
> library behaviour before committing to a framework layer.

## 5. Frontend API contract (must stay stable)

`frontend/index.html` calls these. Build the backend to match exactly. Base URL is set in
the frontend as `API_BASE` (default `http://localhost:8000`); enable CORS for that origin.

```
POST /api/upload
  multipart/form-data, field name: "files" (one or more PDFs)
  -> 200: [ { "doc_id": str, "filename": str, "status": "indexing" | "ready" | "error" } ]

GET /api/status/{doc_id}
  -> 200: { "status": "indexing" | "ready" | "error", "chunks": int | null }

POST /api/chat
  application/json: { "session_id": str, "message": str }
  Non-streaming -> 200: {
      "answer": str,
      "citations": [ { "doc": str, "page": int | null, "snippet": str | null } ]
  }
  Streaming (if enabled): text/event-stream, SSE lines:
      data: { "token": "..." }         # incremental tokens
      data: { "citations": [ ... ] }   # optional, near the end
      data: [DONE]
```

Notes:
- `session_id` is generated by the frontend per browser session. The backend should keep
  conversation history keyed by `session_id` (frontend state is in-memory and resets on reload).
- The frontend toggles streaming via a `STREAMING` constant; support one mode and document which.

## 6. Repository structure (target)

```
finance-rag/
├─ CLAUDE.md
├─ README.md
├─ docker-compose.yml          # qdrant, redis, rabbitmq, api
├─ .env.example
├─ requirements.txt            # or pyproject.toml
├─ frontend/
│  └─ index.html               # existing static UI (do not break API contract)
├─ app/
│  ├─ main.py                  # FastAPI app, CORS, router wiring
│  ├─ config.py                # settings loaded from env
│  ├─ api/
│  │  ├─ upload.py             # POST /api/upload, GET /api/status/{id}
│  │  └─ chat.py               # POST /api/chat (+ optional streaming)
│  ├─ ingestion/
│  │  ├─ parse.py              # layout/table-aware PDF parsing (+OCR fallback)
│  │  ├─ chunk.py              # semantic + parent-child chunking
│  │  ├─ embed.py              # embedding model (local default, swappable)
│  │  └─ index.py              # write dense + sparse vectors to the store
│  ├─ retrieval/
│  │  ├─ hybrid.py             # dense + BM25 + RRF + metadata filtering
│  │  └─ rerank.py             # cross-encoder (local) / Cohere toggle
│  ├─ query/
│  │  ├─ rewrite.py            # history-aware query rewriting
│  │  └─ guardrails_in.py      # PII / prompt-injection checks
│  ├─ generation/
│  │  ├─ generate.py           # LLM call, prompt assembly, citation extraction
│  │  └─ guardrails_out.py     # citation / faithfulness verification
│  ├─ session/
│  │  └─ store.py              # session_id -> conversation history
│  ├─ cache/
│  │  └─ semantic_cache.py     # Redis semantic cache
│  └─ observability/
│     └─ tracing.py            # Langfuse / Phoenix hooks
├─ scripts/
│  └─ ingest_corpus.py         # BATCH pre-index the finance PDF corpus
├─ eval/
│  ├─ golden_set.jsonl         # 50–200 Q&A pairs (curated)
│  ├─ run_ragas.py
│  └─ run_deepeval.py
├─ data/
│  ├─ raw/                     # source finance PDFs (gitignored)
│  └─ processed/
└─ tests/
```

## 7. Configuration (`.env.example`)

```
# --- models / providers (swappable) ---
EMBEDDING_PROVIDER=local            # local | openai | cohere
EMBEDDING_MODEL=<confirm-current>   # e.g. a BGE / sentence-transformers model
LLM_PROVIDER=ollama                 # ollama | openai | anthropic | cohere
LLM_MODEL=<confirm-current>         # e.g. a local Ollama model
RERANKER=local                      # local | cohere

# --- optional paid (leave blank to stay free) ---
OPENAI_API_KEY=
COHERE_API_KEY=
ANTHROPIC_API_KEY=

# --- infra ---
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# --- observability (optional) ---
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=

# --- api ---
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:5500
```

## 8. Commands (proposed — implement/adjust as you build)

```bash
# infra (qdrant, redis, rabbitmq)
docker compose up -d

# pre-index the finance corpus (run once / on corpus change)
python scripts/ingest_corpus.py --path data/raw

# dev API server (http://localhost:8000)
uvicorn app.main:app --reload

# serve the frontend (or serve frontend/ as FastAPI static files)
# e.g. open frontend/index.html, or a static server on :5500

# evaluation
python eval/run_ragas.py
python eval/run_deepeval.py

# tests
pytest
```

## 9. Build order (milestones)

1. **Retrieval core (highest value first):** corpus pre-indexing + layout/table-aware
   parsing → semantic/parent-child chunking → Qdrant (dense + BM25) → hybrid + RRF →
   cross-encoder reranking. Get `/api/upload`, `/api/status`, `/api/chat` returning
   grounded, cited answers end-to-end.
2. **Evaluation:** curate a 50–200 Q&A golden set on the finance corpus; wire RAGAS +
   DeepEval; record before/after metrics for each retrieval change; add a CI gate.
3. **Guardrails + observability:** input (PII/injection) and output (citation/faithfulness)
   guardrails; Langfuse or Phoenix tracing (latency, cost, retrieval quality).
4. **Serving + ops:** split indexing/query services; RabbitMQ async ingestion; Redis
   semantic cache; docker-compose. Stretch: Kubernetes / Azure deploy.

> Fine-tuning is **out of scope** for this project — it is a separate topic from RAG.

## 10. Working conventions for Claude Code in this repo

- **Local/OSS-first.** Do not introduce paid services or API keys as defaults; add them
  only as optional, env-gated toggles, and confirm with the maintainer first.
- **Keep the §5 API contract stable.** Changing it breaks `frontend/index.html`.
- **Separate indexing and query** code paths; don't merge them into one script.
- **Prioritise finance parsing correctness.** When unsure whether a table was parsed
  correctly, prefer surfacing/logging it over silently proceeding.
- **Write tests** alongside features; keep the golden eval set updated.
- **Never fabricate data, sources, or citations** in code or docs. If a source/metric is
  unknown, mark it clearly rather than inventing it.
- **Do not commit** the finance PDFs, `.env`, or secrets. Keep `data/raw/` gitignored.
- When adding a library or model, **note that its version/availability should be verified**
  rather than assuming this file is current.
```
