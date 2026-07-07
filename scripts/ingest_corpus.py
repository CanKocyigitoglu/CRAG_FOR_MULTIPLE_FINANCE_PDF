"""Batch pre-index the finance PDF corpus (OFFLINE indexing pipeline).

Run this with the API server STOPPED — embedded Qdrant allows a single writer.
Deterministic doc_ids (derived from filename) make re-runs idempotent.

    python scripts/ingest_corpus.py --path data/raw
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingestion.pipeline import ingest_pdf  # noqa: E402

_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000042")


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch-index finance PDFs into Qdrant.")
    ap.add_argument("--path", default="data/raw", help="directory of PDFs to index")
    args = ap.parse_args()

    pdfs = sorted(Path(args.path).glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {args.path}")
        return

    total = 0
    for pdf in pdfs:
        doc_id = uuid.uuid5(_NAMESPACE, pdf.name).hex[:12]
        try:
            n = ingest_pdf(str(pdf), doc_id, pdf.name)
            total += n
            print(f"  ✓ {pdf.name} -> {n} chunks (doc_id={doc_id})")
        except Exception as exc:
            print(f"  ✗ {pdf.name} FAILED: {exc}")

    print(f"\nIndexed {len(pdfs)} file(s), {total} chunks total.")


if __name__ == "__main__":
    main()
