"""Before/after comparison: linear RAG vs Corrective RAG on the golden set.

Runs every golden-set question through BOTH pipelines and reports:
  - out_of_corpus: REFUSAL rate (higher is better — CRAG should refuse instead
    of inventing figures for companies not in the corpus).
  - in_corpus: ANSWERED-with-citation rate and RIGHT-DOC rate (a citation whose
    doc matches expect_doc).

This uses the real index and a real LLM, so:
  * Stop the API server first — embedded Qdrant keeps an exclusive lock on the
    store (same constraint as scripts/ingest_corpus.py).
  * Use a model that fits in memory (e.g. LLM_MODEL=llama3.2:latest).

Run:  python eval/compare_crag.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.crag.graph import run_crag  # noqa: E402
from app.generation.generate import generate_answer  # noqa: E402
from app.query.rewrite import rewrite_query  # noqa: E402
from app.retrieval.hybrid import hybrid_search  # noqa: E402
from app.retrieval.rerank import rerank  # noqa: E402

_GOLDEN = Path(__file__).with_name("golden_set.jsonl")

_REFUSAL = [
    "don't have", "do not have", "not have that information", "not in the documents",
    "no information", "cannot find", "can't find", "not enough info", "insufficient",
    "no indexed documents", "not provided in", "does not contain",
]


def _is_refusal(answer: str, citations: list) -> bool:
    a = answer.lower()
    if any(p in a for p in _REFUSAL):
        return True
    return not citations  # nothing cited -> treat as a (weak) refusal


def _right_doc(citations: list, expect_doc: str | None) -> bool:
    if not expect_doc:
        return False
    return any(expect_doc.lower() in (c.get("doc") or "").lower() for c in citations)


def _linear(message: str) -> tuple[str, list]:
    query = rewrite_query(message, [])
    top = rerank(query, hybrid_search(query))
    return generate_answer(query, top, [])


def main() -> None:
    rows = [json.loads(l) for l in _GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]
    pipelines = {"linear": _linear, "crag": lambda m: run_crag(m, [])}

    # metric accumulators: pipeline -> counters
    stats = {name: {"oo_refused": 0, "oo_total": 0, "in_answered": 0, "in_right": 0, "in_total": 0}
             for name in pipelines}

    for row in rows:
        print(f"\n### [{row['kind']}] {row['question']}")
        for name, fn in pipelines.items():
            t0 = time.time()
            answer, citations = fn(row["question"])
            dt = time.time() - t0
            refused = _is_refusal(answer, citations)
            docs = ", ".join(sorted({c.get("doc", "?") for c in citations})) or "-"
            s = stats[name]
            if row["kind"] == "out_of_corpus":
                s["oo_total"] += 1
                s["oo_refused"] += int(refused)
                ok = "OK" if refused == row["expect_refusal"] else "XX"
            else:
                s["in_total"] += 1
                answered = not refused
                right = _right_doc(citations, row.get("expect_doc"))
                s["in_answered"] += int(answered)
                s["in_right"] += int(right)
                ok = "OK" if (answered and right) else ".."
            print(f"  {name:7} {ok} refuse={refused} docs=[{docs}] {dt:4.1f}s :: {answer[:110].strip()}")

    print("\n" + "=" * 60)
    print("SUMMARY (higher is better)")
    for name, s in stats.items():
        oo = f"{s['oo_refused']}/{s['oo_total']}" if s["oo_total"] else "-"
        ans = f"{s['in_answered']}/{s['in_total']}" if s["in_total"] else "-"
        rd = f"{s['in_right']}/{s['in_total']}" if s["in_total"] else "-"
        print(f"  {name:7} | out-of-corpus refused: {oo:>5} | in-corpus answered: {ans:>5} | right-doc cited: {rd:>5}")
    print("=" * 60)
    print("Note: CRAG spends extra LLM calls (grading/expansion/verify); the per-question")
    print("count is logged by app.crag.graph at INFO level while running.")


if __name__ == "__main__":
    main()
