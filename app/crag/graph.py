"""Corrective RAG as a LangGraph StateGraph.

Flow:
    START -> rewrite -> retrieve -> grade -> (route_grade)
        correct                    -> generate
        ambiguous/incorrect + budget -> expand -> retrieve (loop)
        ambiguous/incorrect + no budget -> generate (best effort)
    generate -> verify -> (route_verify)
        verified              -> END
        not verified + budget -> expand -> retrieve (loop)
        not verified + no budget -> END (best effort)

This module is orchestration only. The rewrite, hybrid retrieval + reranking,
and grounded generation steps are the EXISTING modules, wrapped as nodes — not
reimplemented. `expand` shares one `attempts` budget with both routers, so the
whole graph terminates within `crag_max_attempts` correction rounds (with the
recursion_limit as a hard backstop).

Node functions call their dependencies via the imported modules (rewrite_mod,
etc.) so tests can monkeypatch a single attribute to stub out any LLM/retrieval
step and exercise routing offline.
"""
from __future__ import annotations

import logging
import re

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.crag import expand as expand_mod
from app.crag import grade as grade_mod
from app.crag import verify as verify_mod
from app.generation import generate as generate_mod
from app.query import rewrite as rewrite_mod
from app.retrieval import hybrid as hybrid_mod
from app.retrieval import rerank as rerank_mod

logger = logging.getLogger(__name__)

_MARKER = re.compile(r"\[\d+\]")


class CRAGState(TypedDict):
    message: str          # original user message
    history: list         # prior turns [{role, content}]
    query: str            # current standalone / expanded query
    documents: list       # reranked candidates for the current round
    relevant: list        # docs graded relevant
    used: list            # docs actually passed to generation (for verification)
    grade: str            # 'correct' | 'ambiguous' | 'incorrect'
    answer: str
    citations: list
    attempts: int         # correction rounds consumed (bumped in expand)
    llm_calls: int        # cumulative LLM calls, for logging
    verified: bool


# --- nodes -----------------------------------------------------------------

def n_rewrite(state: CRAGState) -> dict:
    query = rewrite_mod.rewrite_query(state["message"], state["history"])
    calls = 1 if state["history"] else 0  # rewrite only calls the LLM with history
    return {"query": query, "llm_calls": state["llm_calls"] + calls}


def n_retrieve(state: CRAGState) -> dict:
    candidates = hybrid_mod.hybrid_search(state["query"])
    docs = rerank_mod.rerank(state["query"], candidates)  # cross-encoder/RRF, no LLM
    return {"documents": docs}


def n_grade(state: CRAGState) -> dict:
    verdict, relevant, calls = grade_mod.grade_documents(state["query"], state["documents"])
    return {"grade": verdict, "relevant": relevant, "llm_calls": state["llm_calls"] + calls}


def n_expand(state: CRAGState) -> dict:
    new_q, calls = expand_mod.expand_query(state["query"])
    return {
        "query": new_q,
        "attempts": state["attempts"] + 1,
        "llm_calls": state["llm_calls"] + calls,
    }


def n_generate(state: CRAGState) -> dict:
    docs = state["relevant"] or state["documents"]
    answer, citations = generate_mod.generate_answer(state["query"], docs, state["history"])
    # An answer with no [n] markers is a refusal / "not enough info" — carry no
    # citations so we never attach sources to a non-grounded reply.
    if not _MARKER.search(answer):
        citations = []
    return {
        "answer": answer,
        "citations": citations,
        "used": docs,
        "llm_calls": state["llm_calls"] + 1,
    }


def n_verify(state: CRAGState) -> dict:
    verified, calls = verify_mod.verify_answer(state["answer"], state["used"], state["citations"])
    return {"verified": verified, "llm_calls": state["llm_calls"] + calls}


# --- routers (read-only; return the next node name) ------------------------

def route_grade(state: CRAGState) -> str:
    if state["grade"] == "correct":
        return "generate"
    if state["attempts"] < settings.crag_max_attempts:
        return "expand"
    return "generate"  # budget exhausted -> best-effort grounded answer


def route_verify(state: CRAGState) -> str:
    if state["verified"]:
        return END
    if state["attempts"] < settings.crag_max_attempts:
        return "expand"
    return END  # budget exhausted -> return the best-effort answer as-is


def _build_graph():
    g = StateGraph(CRAGState)
    g.add_node("rewrite", n_rewrite)
    g.add_node("retrieve", n_retrieve)
    g.add_node("grade", n_grade)
    g.add_node("expand", n_expand)
    g.add_node("generate", n_generate)
    g.add_node("verify", n_verify)

    g.add_edge(START, "rewrite")
    g.add_edge("rewrite", "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", route_grade, {"expand": "expand", "generate": "generate"})
    g.add_edge("expand", "retrieve")
    g.add_edge("generate", "verify")
    g.add_conditional_edges("verify", route_verify, {"expand": "expand", END: END})
    return g.compile()


_graph = _build_graph()


def run_crag(message: str, history: list[dict] | None) -> tuple[str, list[dict]]:
    """Entry point used by /api/chat. Returns (answer, citations)."""
    initial: CRAGState = {
        "message": message,
        "history": history or [],
        "query": "",
        "documents": [],
        "relevant": [],
        "used": [],
        "grade": "",
        "answer": "",
        "citations": [],
        "attempts": 0,
        "llm_calls": 0,
        "verified": False,
    }
    # recursion_limit is a hard backstop; `attempts` is the real bound.
    final = _graph.invoke(initial, config={"recursion_limit": 30})
    logger.info(
        "CRAG done: llm_calls=%d attempts=%d grade=%s verified=%s citations=%d msg=%r",
        final["llm_calls"], final["attempts"], final["grade"],
        final["verified"], len(final["citations"]), message,
    )
    return final["answer"], final["citations"]
