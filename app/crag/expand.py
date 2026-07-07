"""Query expansion — the corrective action when documents grade poorly.

We rewrite the query into a broader, more retrievable form and re-search the
SAME corpus. We deliberately do NOT pull external/web results by default:
financial numbers must stay first-party, and a wrong figure from the open web
is worse than "not enough info". Web search sits behind an off-by-default env
flag and is intentionally left unimplemented (wiring a provider is a separate,
approval-gated change), so enabling the flag only logs and falls back to corpus.
"""
from __future__ import annotations

import logging

from app.config import settings
from app.generation.generate import complete

logger = logging.getLogger(__name__)

_PROMPT = (
    "The following search query returned weak results on a financial-document "
    "corpus. Rewrite it into a broader, more retrievable query that keeps the "
    "same intent — add synonyms and expand finance terms (e.g. 'net income' / "
    "'profit' / 'earnings', spell out fiscal years). Return ONLY the rewritten "
    "query.\n\nQuery: {q}\n\nRewritten query:"
)


def _maybe_web_search() -> None:
    if settings.crag_web_search:
        logger.warning(
            "CRAG_WEB_SEARCH is enabled but no web provider is configured; "
            "re-searching the local corpus only (finance data stays first-party)."
        )


def expand_query(query: str) -> tuple[str, int]:
    """Return (expanded_query, llm_calls). Falls back to the original on error."""
    _maybe_web_search()
    try:
        new_q = complete(_PROMPT.format(q=query)).strip()
    except Exception as exc:
        logger.warning("query expansion failed (%s); keeping original query", exc)
        return query, 1
    logger.info("CRAG expanded query: %r -> %r", query, new_q)
    return (new_q or query), 1
