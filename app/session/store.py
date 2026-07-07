"""Conversation history adapter.

Durable storage lives in app.session.db (SQLite). This thin layer keeps the
existing (get_history / add_turn) surface the chat endpoint already uses, and
draws the line between the two views of history:
  - get_history -> the bounded last-N window fed to the LLM for multi-turn
    rewriting (must stay small: full history would blow up context + latency).
  - the full, unbounded history for display is read directly via db.* by the
    conversations API.

Because history is now persisted, multi-turn context also survives an API
restart (it used to be RAM-only and reset on restart).
"""
from __future__ import annotations

from app.session import db

_MAX_TURNS = 12  # messages fed back to the LLM as multi-turn context


def get_history(session_id: str) -> list[dict]:
    return db.get_context_window(session_id, _MAX_TURNS)


def add_turn(
    session_id: str,
    role: str,
    content: str,
    citations: list | None = None,
    title: str | None = None,
) -> None:
    db.add_message(session_id, role, content, citations=citations, title_if_new=title)
