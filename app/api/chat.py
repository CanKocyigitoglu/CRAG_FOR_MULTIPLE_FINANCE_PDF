"""POST /api/chat — the online query pipeline.

rewrite (history-aware) -> hybrid retrieve -> rerank -> grounded generate.
Non-streaming: returns {answer, citations}. (Frontend STREAMING = false.)
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.generation.generate import generate_answer
from app.query.rewrite import rewrite_query
from app.retrieval.hybrid import hybrid_search
from app.retrieval.rerank import rerank
from app.session.store import add_turn, get_history

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    message: str


class Citation(BaseModel):
    doc: str | None = None
    page: int | None = None
    snippet: str | None = None
    match: float | None = None  # semantic match % of this source to the question


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]


def _title(text: str, limit: int = 60) -> str:
    """Conversation title derived from its first question."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    history = get_history(req.session_id)

    if settings.crag_enabled:
        # Corrective RAG: rewrite -> retrieve -> grade -> (correct) generate /
        # (else) expand + retry -> verify. Rewrite happens inside the graph.
        from app.crag.graph import run_crag

        answer, citations = run_crag(req.message, history)
    else:
        # Linear fallback: rewrite -> hybrid retrieve -> rerank -> generate.
        query = rewrite_query(req.message, history)
        candidates = hybrid_search(query)
        top = rerank(query, candidates)
        answer, citations = generate_answer(query, top, history)

    # Persist both turns (title is only applied when the conversation is new).
    add_turn(req.session_id, "user", req.message, title=_title(req.message))
    add_turn(req.session_id, "assistant", answer, citations=citations)
    return ChatResponse(answer=answer, citations=[Citation(**c) for c in citations])
