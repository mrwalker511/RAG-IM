import pytest

from ragcore.ingestion.chunker import ConfigError, chunk_texts


def test_chunk_splits_long_text():
    long_text = " ".join(["word"] * 300)
    results = chunk_texts([long_text], chunk_size=100, chunk_overlap=10)
    assert len(results) > 1
    for i, r in enumerate(results):
        assert r.chunk_index == i


def test_chunk_preserves_overlap():
    text = "abc " * 200
    results = chunk_texts([text], chunk_size=100, chunk_overlap=20)
    assert len(results) >= 2


def test_chunk_multiple_sections():
    sections = ["Section one text. " * 10, "Section two text. " * 10]
    results = chunk_texts(sections, chunk_size=50, chunk_overlap=5)
    assert len(results) > 0
    indices = [r.chunk_index for r in results]
    assert indices == list(range(len(results)))


def test_chunk_size_exceeds_model_limit_raises():
    with pytest.raises(ConfigError):
        chunk_texts(["some text"], chunk_size=9000, embedding_model="text-embedding-3-small")


def test_empty_sections_returns_empty():
    results = chunk_texts(["   ", ""])
    assert results == []
