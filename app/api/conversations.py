"""Conversation history API — list / read / search / delete past chats.

Additive to the §5 contract; the chat flow is unchanged. Single-user local
assumption: there is no auth, so every stored conversation is visible and
deletable here. Do not expose this API publicly as-is.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.session import db

router = APIRouter()


@router.get("/api/conversations")
async def list_conversations(q: str | None = None) -> list[dict]:
    """Summaries (id, title, timestamps), newest first. `q` searches title +
    message content."""
    return db.list_conversations(q)


@router.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict:
    conv = db.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return conv


@router.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict:
    if not db.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"deleted": conversation_id}
