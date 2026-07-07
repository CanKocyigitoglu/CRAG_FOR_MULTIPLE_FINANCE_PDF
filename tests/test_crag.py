"""CRAG graph routing tests — fully offline.

The LLM/retrieval steps are monkeypatched, so these exercise the graph's wiring
and routing (correct -> straight to answer; poor docs -> expand/retry -> refuse
without fabricating) without needing Ollama or an index.
"""
from app.config import settings
from app.crag import graph as G


def _patch(monkeypatch, *, rewrite=None, docs=None, grade=None, generate=None, verify=None, expand=None):
    if rewrite is not None:
        monkeypatch.setattr(G.rewrite_mod, "rewrite_query", rewrite)
    if docs is not None:
        monkeypatch.setattr(G.hybrid_mod, "hybrid_search", lambda q, **k: docs)
        monkeypatch.setattr(G.rerank_mod, "rerank", lambda q, c, **k: c)
    if grade is not None:
        monkeypatch.setattr(G.grade_mod, "grade_documents", grade)
    if generate is not None:
        monkeypatch.setattr(G.generate_mod, "generate_answer", generate)
    if verify is not None:
        monkeypatch.setattr(G.verify_mod, "verify_answer", verify)
    if expand is not None:
        monkeypatch.setattr(G.expand_mod, "expand_query", expand)


def test_relevant_question_goes_straight_to_answer(monkeypatch):
    docs = [{"doc": "f.pdf", "page": 1, "text": "Tesla net income 2022 was $12.6B", "parent_text": "..."}]
    expands = {"n": 0}

    def fake_expand(q):
        expands["n"] += 1
        return q, 1

    _patch(
        monkeypatch,
        rewrite=lambda m, h: m,
        docs=docs,
        grade=lambda q, d: ("correct", docs, 1),
        generate=lambda q, d, h: ("Tesla net income was $12.6B [1]", [{"doc": "f.pdf", "page": 1, "snippet": "…", "match": 90.0}]),
        verify=lambda a, s, c: (True, 1),
        expand=fake_expand,
    )

    answer, citations = G.run_crag("What was Tesla's 2022 net income?", [])

    assert "[1]" in answer
    assert citations and citations[0]["doc"] == "f.pdf" and citations[0]["page"] == 1
    assert expands["n"] == 0  # 'correct' -> no correction loop


def test_out_of_corpus_expands_then_refuses_without_fabricating(monkeypatch):
    docs = [{"doc": "f.pdf", "page": 1, "text": "unrelated finance text", "parent_text": "unrelated"}]
    expands = {"n": 0}

    def fake_expand(q):
        expands["n"] += 1
        return q + " (expanded)", 1

    _patch(
        monkeypatch,
        rewrite=lambda m, h: m,
        docs=docs,
        grade=lambda q, d: ("incorrect", [], 1),  # nothing relevant, ever
        # refusal answer with no [n] markers -> node must blank citations
        generate=lambda q, d, h: ("I don't have that information in the documents.", [{"doc": "f.pdf", "page": 1}]),
        verify=lambda a, s, c: (True, 0),
        expand=fake_expand,
    )

    answer, citations = G.run_crag("What is the capital of France?", [])

    assert expands["n"] == settings.crag_max_attempts  # bounded correction rounds
    assert citations == []  # refusal must not carry fabricated citations
    assert "information" in answer.lower()


def test_verify_failure_triggers_bounded_retry(monkeypatch):
    docs = [{"doc": "f.pdf", "page": 2, "text": "some figure", "parent_text": "some figure"}]
    expands = {"n": 0}

    def fake_expand(q):
        expands["n"] += 1
        return q, 1

    _patch(
        monkeypatch,
        rewrite=lambda m, h: m,
        docs=docs,
        grade=lambda q, d: ("correct", docs, 1),  # correct -> generate immediately
        generate=lambda q, d, h: ("Revenue was $1B [1]", [{"doc": "f.pdf", "page": 2, "snippet": "…"}]),
        verify=lambda a, s, c: (False, 1),  # never verifies -> should retry until budget spent
        expand=fake_expand,
    )

    answer, citations = G.run_crag("What was revenue?", [])

    # verify keeps failing; expand runs up to the attempt budget, then we stop.
    assert expands["n"] == settings.crag_max_attempts
    assert "[1]" in answer  # best-effort answer still returned
