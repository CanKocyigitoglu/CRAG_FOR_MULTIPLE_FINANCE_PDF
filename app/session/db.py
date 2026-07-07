"""Durable conversation history in embedded SQLite (no server — mirrors the
on-disk Qdrant choice, stays £0/Docker-free).

Single source of truth for two things:
  - the chat UI's full history (list / read / search / delete past chats), and
  - the bounded last-N context window the LLM sees for multi-turn follow-ups.

Concurrency: FastAPI is async and SQLite serialises writes, so we open in WAL
mode (concurrent readers + one writer) with a busy timeout, using a short-lived
connection per call. Writes are tiny, so this stays ahead of a single-user
portfolio workload. The schema is created on every connect (IF NOT EXISTS,
cheap) so pointing _DB_PATH at a fresh file "just works" (used by tests).
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from app.config import settings

_DB_PATH = Path(settings.session_db_path)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    citations       TEXT,            -- JSON list; NULL for user turns
    created_at      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
"""


@contextmanager
def _db():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript(_SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    citations: list | None = None,
    title_if_new: str | None = None,
) -> None:
    """Append a turn, creating the conversation (with title) on first message."""
    now = time.time()
    payload = json.dumps(citations) if citations else None
    with _db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM conversations WHERE id=?", (conversation_id,)
        ).fetchone()
        if exists is None:
            conn.execute(
                "INSERT INTO conversations(id, title, created_at, updated_at) VALUES (?,?,?,?)",
                (conversation_id, title_if_new or "", now, now),
            )
        conn.execute(
            "INSERT INTO messages(conversation_id, role, content, citations, created_at) "
            "VALUES (?,?,?,?,?)",
            (conversation_id, role, content, payload, now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id)
        )


def get_context_window(conversation_id: str, limit: int) -> list[dict]:
    """Last `limit` messages as [{role, content}], oldest first — for LLM context."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id=? "
            "ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def get_conversation(conversation_id: str) -> dict | None:
    """Full conversation with parsed citations, or None if it doesn't exist."""
    with _db() as conn:
        conv = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id=?",
            (conversation_id,),
        ).fetchone()
        if conv is None:
            return None
        rows = conn.execute(
            "SELECT role, content, citations, created_at FROM messages "
            "WHERE conversation_id=? ORDER BY id",
            (conversation_id,),
        ).fetchall()
    return {
        "id": conv["id"],
        "title": conv["title"],
        "created_at": conv["created_at"],
        "updated_at": conv["updated_at"],
        "messages": [
            {
                "role": r["role"],
                "content": r["content"],
                "citations": json.loads(r["citations"]) if r["citations"] else [],
            }
            for r in rows
        ],
    }


def list_conversations(q: str | None = None, limit: int = 200) -> list[dict]:
    """Conversation summaries, newest-updated first. `q` matches title or any
    message content (case-insensitive substring)."""
    with _db() as conn:
        if q:
            like = f"%{q}%"
            rows = conn.execute(
                "SELECT DISTINCT c.id, c.title, c.created_at, c.updated_at "
                "FROM conversations c LEFT JOIN messages m ON m.conversation_id = c.id "
                "WHERE c.title LIKE ? OR m.content LIKE ? "
                "ORDER BY c.updated_at DESC LIMIT ?",
                (like, like, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation and its messages. Returns True if it existed."""
    with _db() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
        cur = conn.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
    return cur.rowcount > 0
