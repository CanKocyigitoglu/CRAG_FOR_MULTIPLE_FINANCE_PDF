from pathlib import Path

import pytest

from app.session import db


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "test.db")
    return db


def test_roundtrip_preserves_citations_and_match(tmp_db):
    db.add_message("c1", "user", "which year?", title_if_new="which year?")
    db.add_message(
        "c1", "assistant", "2020 [1]", citations=[{"doc": "d", "page": 3, "match": 78.0}]
    )

    conv = db.get_conversation("c1")
    assert conv["title"] == "which year?"
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]
    assert conv["messages"][0]["citations"] == []  # user turn has no citations
    assert conv["messages"][1]["citations"][0]["match"] == 78.0


def test_context_window_is_last_n_oldest_first(tmp_db):
    for i in range(5):
        db.add_message("c1", "user", f"q{i}", title_if_new="q0")
        db.add_message("c1", "assistant", f"a{i}")

    win = db.get_context_window("c1", 4)
    # last 4 of 10 messages, chronological (oldest first)
    assert [m["content"] for m in win] == ["q3", "a3", "q4", "a4"]


def test_list_search_and_delete(tmp_db):
    db.add_message("a", "user", "tesla profit by year", title_if_new="tesla profit by year")
    db.add_message("b", "user", "apple revenue", title_if_new="apple revenue")

    assert {c["id"] for c in db.list_conversations()} == {"a", "b"}
    # search matches message content
    assert [c["id"] for c in db.list_conversations("tesla")] == ["a"]

    assert db.delete_conversation("a") is True
    assert {c["id"] for c in db.list_conversations()} == {"b"}
    assert db.delete_conversation("missing") is False


def test_missing_conversation_returns_none(tmp_db):
    assert db.get_conversation("nope") is None
