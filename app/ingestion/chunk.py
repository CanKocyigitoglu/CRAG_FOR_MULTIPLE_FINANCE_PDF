"""Sentence-aware, parent-child chunking.

We split each page on sentence boundaries (not fixed character windows) and pack
sentences into small *child* chunks — these get embedded + BM25-indexed for
precise retrieval. Each child also carries its larger *parent* block, which is
what we feed the LLM so it sees enough surrounding context to answer well.

(True embedding-boundary "semantic" chunking is a future enhancement; this is the
practical, structure-respecting version.)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CHILD_MAX_CHARS = 800
PARENT_MAX_CHARS = 2400
CHILD_OVERLAP_SENTENCES = 1

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


@dataclass
class Chunk:
    id: str          # stable "{doc_id}:{page}:{idx}"
    doc_id: str
    doc: str         # source filename
    page: int
    text: str        # child text — embedded + BM25-indexed
    parent_text: str # larger block fed to the LLM for context


def _split_sentences(text: str) -> list[str]:
    # Keep table blocks intact — never split a markdown table across sentences.
    parts: list[str] = []
    for block in re.split(r"(\[TABLE\].*?\[/TABLE\])", text, flags=re.DOTALL):
        block = block.strip()
        if not block:
            continue
        if block.startswith("[TABLE]"):
            parts.append(block)
        else:
            parts.extend(s.strip() for s in _SENTENCE_SPLIT.split(block) if s.strip())
    return parts


def _split_long(unit: str, max_chars: int) -> list[str]:
    """Break a single oversized unit (e.g. a huge financial table kept intact by
    _split_sentences) into <= max_chars pieces, preferring whitespace boundaries.
    Without this, one giant table becomes one chunk that overflows the embedding
    model's context window and the whole document fails to index."""
    if len(unit) <= max_chars:
        return [unit]
    pieces: list[str] = []
    while len(unit) > max_chars:
        cut = unit.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars  # dense content with no break point -> hard cut
        pieces.append(unit[:cut].strip())
        unit = unit[cut:].strip()
    if unit:
        pieces.append(unit)
    return [p for p in pieces if p]


def _pack(sentences: list[str], max_chars: int, overlap: int) -> list[str]:
    """Greedily pack sentences into blocks up to max_chars, with sentence overlap.
    Any single unit longer than max_chars is hard-split first, so no block — and
    therefore no embedded child chunk — can exceed the embedding context limit."""
    blocks: list[str] = []
    cur: list[str] = []
    size = 0
    for s in sentences:
        for part in _split_long(s, max_chars):
            if cur and size + len(part) + 1 > max_chars:
                blocks.append(" ".join(cur))
                cur = cur[-overlap:] if overlap else []
                size = sum(len(x) + 1 for x in cur)
            cur.append(part)
            size += len(part) + 1
    if cur:
        blocks.append(" ".join(cur))
    return blocks


def chunk_pages(pages: list[dict], doc_id: str, doc: str) -> list[Chunk]:
    """Turn parsed pages into parent-child chunks."""
    chunks: list[Chunk] = []
    idx = 0
    for page in pages:
        sentences = _split_sentences(page["text"])
        if not sentences:
            continue
        parents = _pack(sentences, PARENT_MAX_CHARS, overlap=0)
        for parent in parents:
            children = _pack(_split_sentences(parent), CHILD_MAX_CHARS, CHILD_OVERLAP_SENTENCES)
            for child in children:
                chunks.append(
                    Chunk(
                        id=f"{doc_id}:{page['page']}:{idx}",
                        doc_id=doc_id,
                        doc=doc,
                        page=page["page"],
                        text=child,
                        parent_text=parent,
                    )
                )
                idx += 1
    return chunks
