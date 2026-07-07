from app.retrieval.hybrid import _rrf


def _p(doc_id, page, text):
    return {"doc_id": doc_id, "page": page, "text": text}


def test_item_in_both_lists_outranks_item_in_one():
    a = _p("d", 1, "shared")
    b = _p("d", 2, "dense-only")
    c = _p("d", 3, "sparse-only")

    dense = [a, b]
    sparse = [a, c]
    fused = _rrf([dense, sparse])

    keys = [(x["doc_id"], x["page"], x["text"]) for x in fused]
    assert keys[0] == ("d", 1, "shared")  # appears in both -> highest fused score
    assert len(fused) == 3  # deduplicated across lists
