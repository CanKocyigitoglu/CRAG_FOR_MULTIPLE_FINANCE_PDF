"""History-aware query rewriting.

Follow-ups like "what about 2023?" are meaningless to a retriever on their own.
When there's conversation history, we ask the LLM to rewrite the latest message
into a standalone query before retrieval. With no history, we pass it through.
"""
from __future__ import annotations

from app.generation.generate import complete

_PROMPT = (
    "Given the conversation and a follow-up question, rewrite the follow-up as a "
    "standalone question that includes any needed context from the conversation. "
    "Return ONLY the rewritten question, nothing else.\n\n"
    "Conversation:\n{history}\n\nFollow-up: {question}\n\nStandalone question:"
)


def rewrite_query(message: str, history: list[dict] | None) -> str:
    if not history:
        return message
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    try:
        rewritten = complete(_PROMPT.format(history=convo, question=message)).strip()
    except Exception:
        return message  # never let rewriting break retrieval
    return rewritten or message
