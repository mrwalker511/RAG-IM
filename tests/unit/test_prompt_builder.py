import uuid

from ragcore.generation.prompt_builder import _MAX_CONTEXT_CHARS, build_prompt
from ragcore.retrieval.vector_search import ChunkResult


def _make_chunk(filename: str, idx: int, content: str = "text") -> ChunkResult:
    return ChunkResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        content=content,
        score=0.9,
        chunk_index=idx,
        filename=filename,
        metadata={},
    )


def test_prompt_includes_query():
    chunks = [_make_chunk("a.txt", 0)]
    prompt = build_prompt("What is X?", chunks)
    assert "What is X?" in prompt


def test_prompt_includes_source_citation():
    chunk = _make_chunk("report.pdf", 3)
    prompt = build_prompt("query", [chunk])
    assert "report.pdf" in prompt
    assert "chunk 3" in prompt


def test_prompt_truncates_excess_chunks():
    big_content = "a" * (_MAX_CONTEXT_CHARS // 2)
    chunks = [_make_chunk("doc.txt", i, big_content) for i in range(10)]
    prompt = build_prompt("query", chunks)
    # Should not include all 10 chunks — truncation should kick in
    assert prompt.count("[doc.txt") < 10


def test_prompt_no_chunks_shows_no_context():
    prompt = build_prompt("query", [])
    assert "(no context)" in prompt
