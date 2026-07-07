"""Layout/table-aware PDF parsing.

Finance PDFs are table-heavy, and bad table extraction silently produces wrong
numbers, so we extract tables explicitly (pdfplumber) in addition to the page
text (PyMuPDF), and label them so the LLM can see the structure.

Returns one record per page: {"page": <1-indexed int>, "text": <str>}.
"""
from __future__ import annotations

import logging

import fitz  # PyMuPDF
import pdfplumber

logger = logging.getLogger(__name__)

# Pages with less text than this are likely scanned/image-only. We log them
# rather than silently returning an empty page. True OCR (Tesseract) is a
# deliberate follow-up — it needs a system binary we don't assume is present.
_LOW_TEXT_THRESHOLD = 40


def _table_to_markdown(table: list[list[str | None]]) -> str:
    """Render a pdfplumber table (list of rows) as a GitHub-style markdown table."""
    rows = [[(cell or "").strip().replace("\n", " ") for cell in row] for row in table]
    rows = [r for r in rows if any(cell for cell in r)]
    if not rows:
        return ""
    header, *body = rows
    width = len(header)
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for r in body:
        r = (r + [""] * width)[:width]  # pad/truncate ragged rows
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def parse_pdf(path: str) -> list[dict]:
    """Parse a PDF into per-page text with extracted tables appended as markdown."""
    pages: list[dict] = []

    text_by_page: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            text_by_page.append(page.get_text("text").strip())

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            body = text_by_page[i] if i < len(text_by_page) else ""

            try:
                tables = page.extract_tables() or []
            except Exception as exc:  # pdfplumber can choke on odd layouts
                logger.warning("table extraction failed on %s p%d: %s", path, i + 1, exc)
                tables = []

            for t in tables:
                md = _table_to_markdown(t)
                if md:
                    body += f"\n\n[TABLE]\n{md}\n[/TABLE]"

            if len(body.strip()) < _LOW_TEXT_THRESHOLD:
                logger.warning(
                    "page %d of %s has little extractable text (%d chars) — "
                    "may be scanned; OCR not applied",
                    i + 1, path, len(body.strip()),
                )

            pages.append({"page": i + 1, "text": body.strip()})

    return pages
