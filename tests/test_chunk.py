from app.ingestion.chunk import CHILD_MAX_CHARS, chunk_pages


def test_children_respect_size_and_carry_parent():
    text = " ".join(f"Revenue grew in year {i} by several points." for i in range(60))
    chunks = chunk_pages([{"page": 1, "text": text}], doc_id="d1", doc="a.pdf")

    assert chunks, "expected at least one chunk"
    assert all(c.page == 1 and c.doc == "a.pdf" for c in chunks)
    # children are small-ish; parents are the larger enclosing context
    assert all(len(c.text) <= CHILD_MAX_CHARS + 200 for c in chunks)
    assert all(len(c.parent_text) >= len(c.text) for c in chunks)


def test_table_block_stays_intact():
    text = "Intro sentence.\n\n[TABLE]\n| Year | Revenue |\n| --- | --- |\n| 2022 | 100 |\n[/TABLE]"
    chunks = chunk_pages([{"page": 3, "text": text}], doc_id="d2", doc="b.pdf")
    joined = " ".join(c.text for c in chunks)
    assert "[TABLE]" in joined and "| 2022 | 100 |" in joined
