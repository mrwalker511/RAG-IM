import pickle
import uuid

import pytest
from rank_bm25 import BM25Okapi


def _build_bm25_payload(texts: list[str]):
    """Helper: build and pickle a minimal BM25 payload."""
    tokenized = [t.lower().split() for t in texts]
    bm25 = BM25Okapi(tokenized)
    return bm25, pickle.dumps(bm25)


def test_bm25_serialization_round_trip():
    texts = ["the quick brown fox", "jumped over the lazy dog", "hello world"]
    bm25, serialized = _build_bm25_payload(texts)
    restored: BM25Okapi = pickle.loads(serialized)
    query = ["quick", "fox"]
    original_scores = bm25.get_scores(query)
    restored_scores = restored.get_scores(query)
    assert list(original_scores) == list(restored_scores)


def test_bm25_top_result_is_relevant():
    texts = [
        "machine learning models require data",
        "baking bread requires flour and yeast",
        "neural networks learn from examples",
    ]
    tokenized = [t.lower().split() for t in texts]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(["machine", "learning"])
    top_idx = int(scores.argmax())
    assert top_idx == 0


def test_bm25_empty_corpus():
    bm25 = BM25Okapi([["dummy"]])
    scores = bm25.get_scores(["query"])
    assert len(scores) == 1
