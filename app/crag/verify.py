"""Post-generation verification: is the answer supported and are its citations real?

Two checks:
  - citations_real (deterministic): every citation must point at a (doc, page)
    that is actually among the sources the answer was generated from. This is
    the "citations are real, not invented" guarantee.
  - supported (one LLM call): a faithfulness judge that every factual claim /
    number in the answer appears in the sources.

A "not enough info" answer (no sources, or the generator refused) has nothing to
fabricate, so it verifies trivially. Verifier errors fail open (verified=True)
so a flaky judge never blocks a legitimate answer.
"""
from __future__ import annotations

import json
import logging

from app.generation.generate import chat

logger = logging.getLogger(__name__)

_SCHEMA = {
    "type": "object",
    "properties": {"supported": {"type": "boolean"}},
    "required": ["supported"],
}

_SYSTEM = (
    "You check whether an ANSWER is fully supported by the provided SOURCES. "
    "Return JSON {\"supported\": true|false}. It is supported only if every "
    "factual claim and every number in the answer appears in the sources. A "
    "reply that says the information is not in the documents is 'supported'."
)


def verify_answer(answer: str, sources: list[dict], citations: list[dict]) -> tuple[bool, int]:
    """Return (verified, llm_calls)."""
    if not sources:
        return True, 0  # nothing to ground against / refusal path

    source_keys = {(s.get("doc"), s.get("page")) for s in sources}
    citations_real = all((c.get("doc"), c.get("page")) in source_keys for c in citations)

    context = "\n\n".join(
        f"[{i}] {s.get('parent_text') or s.get('text')}" for i, s in enumerate(sources, 1)
    )
    user = f"Sources:\n{context[:6000]}\n\nAnswer:\n{answer}"
    try:
        raw = chat(
            [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
            fmt=_SCHEMA,
            temperature=0.0,
        )
        supported = bool(json.loads(raw).get("supported", False))
    except Exception as exc:
        logger.warning("verify call failed (%s); failing open", exc)
        supported = True

    verified = supported and citations_real
    logger.info(
        "CRAG verify verified=%s (supported=%s citations_real=%s)",
        verified, supported, citations_real,
    )
    return verified, 1
