"""Unit tests for the query pipeline."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ragcore.generation.base import GenerationResult
from ragcore.query.pipeline import QueryResult, SourceAttribution, _ensure_bm25_index, run_query
from ragcore.retrieval.vector_search import ChunkResult


def _make_chunk(content: str = "context text") -> ChunkResult:
    pid = uuid.uuid4()
    return ChunkResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        project_id=pid,
        content=content,
        score=0.9,
        chunk_index=0,
        filename="doc.txt",
        metadata={},
    )


async def test_run_query_returns_result_with_tokens(mock_embedder):
    project_id = uuid.uuid4()
    mock_session = AsyncMock()

    mock_generator = AsyncMock()
    mock_generator.generate = AsyncMock(
        return_value=GenerationResult(text="The answer", tokens_used=99)
    )

    chunks = [_make_chunk("some context")]

    with (
        patch("ragcore.query.pipeline.vector_search", new=AsyncMock(return_value=chunks)),
        patch("ragcore.query.pipeline._ensure_bm25_index", new=AsyncMock()),
        patch("ragcore.query.pipeline.bm25_search", new=AsyncMock(return_value=[])),
        patch("ragcore.query.pipeline.reciprocal_rank_fusion", return_value=chunks),
        patch("ragcore.query.pipeline.log_query_event", new=AsyncMock()),
        patch("ragcore.query.pipeline._get_cached", new=AsyncMock(return_value=None)),
        patch("ragcore.query.pipeline._set_cached", new=AsyncMock()),
    ):
        result = await run_query(
            project_id=project_id,
            query_text="What is this?",
            session=mock_session,
            embedder=mock_embedder,
            generator=mock_generator,
        )

    assert isinstance(result, QueryResult)
    assert result.answer == "The answer"
    assert result.tokens_used == 99
    assert len(result.sources) == 1


async def test_run_query_returns_cached_result_without_hitting_llm(mock_embedder):
    """Cache hit: result returned immediately; vector search and LLM are never called."""
    project_id = uuid.uuid4()
    mock_session = AsyncMock()
    mock_generator = AsyncMock()

    cached = QueryResult(
        answer="cached answer",
        sources=[],
        latency_ms=1,
        tokens_used=0,
    )

    with (
        patch("ragcore.query.pipeline._get_cached", new=AsyncMock(return_value=cached)),
        patch("ragcore.query.pipeline.vector_search", new=AsyncMock()) as mock_vs,
    ):
        result = await run_query(
            project_id=project_id,
            query_text="cached query",
            session=mock_session,
            embedder=mock_embedder,
            generator=mock_generator,
        )

    assert result is cached
    mock_vs.assert_not_awaited()
    mock_generator.generate.assert_not_awaited()


async def test_run_query_stream_bypasses_cache(mock_embedder):
    """Streaming queries never touch the cache — lookup and write are both skipped."""
    project_id = uuid.uuid4()
    mock_session = AsyncMock()

    async def _fake_gen():
        yield "token1"
        yield "token2"

    mock_generator = AsyncMock()
    mock_generator.generate = AsyncMock(return_value=_fake_gen())

    with (
        patch("ragcore.query.pipeline._get_cached", new=AsyncMock()) as mock_cache_get,
        patch("ragcore.query.pipeline._set_cached", new=AsyncMock()) as mock_cache_set,
        patch("ragcore.query.pipeline.vector_search", new=AsyncMock(return_value=[])),
        patch("ragcore.query.pipeline._ensure_bm25_index", new=AsyncMock()),
        patch("ragcore.query.pipeline.bm25_search", new=AsyncMock(return_value=[])),
        patch("ragcore.query.pipeline.reciprocal_rank_fusion", return_value=[]),
    ):
        result = await run_query(
            project_id=project_id,
            query_text="stream?",
            session=mock_session,
            embedder=mock_embedder,
            generator=mock_generator,
            stream=True,
        )

    mock_cache_get.assert_not_awaited()
    mock_cache_set.assert_not_awaited()

    import inspect
    assert inspect.isasyncgen(result)


async def test_run_query_stream_returns_async_gen(mock_embedder):
    project_id = uuid.uuid4()
    mock_session = AsyncMock()

    async def _fake_gen():
        yield "token1"
        yield "token2"

    mock_generator = AsyncMock()
    mock_generator.generate = AsyncMock(return_value=_fake_gen())

    with (
        patch("ragcore.query.pipeline.vector_search", new=AsyncMock(return_value=[])),
        patch("ragcore.query.pipeline._ensure_bm25_index", new=AsyncMock()),
        patch("ragcore.query.pipeline.bm25_search", new=AsyncMock(return_value=[])),
        patch("ragcore.query.pipeline.reciprocal_rank_fusion", return_value=[]),
    ):
        result = await run_query(
            project_id=project_id,
            query_text="stream?",
            session=mock_session,
            embedder=mock_embedder,
            generator=mock_generator,
            stream=True,
        )

    import inspect
    assert inspect.isasyncgen(result)


async def test_ensure_bm25_index_builds_when_missing():
    mock_session = AsyncMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    project_id = uuid.uuid4()

    with patch("ragcore.query.pipeline.build_bm25_index", new=AsyncMock()) as mock_build:
        await _ensure_bm25_index(project_id, mock_session)
        mock_build.assert_awaited_once_with(project_id, mock_session)


async def test_ensure_bm25_index_rebuilds_when_stale():
    mock_session = AsyncMock()
    stale_time = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    index_row = MagicMock()
    index_row.updated_at = stale_time
    mock_session.execute.return_value.scalar_one_or_none.return_value = index_row
    project_id = uuid.uuid4()

    with patch("ragcore.query.pipeline.build_bm25_index", new=AsyncMock()) as mock_build:
        await _ensure_bm25_index(project_id, mock_session)
        mock_build.assert_awaited_once()


async def test_ensure_bm25_index_skips_when_fresh():
    mock_session = AsyncMock()
    fresh_time = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
    index_row = MagicMock()
    index_row.updated_at = fresh_time
    mock_session.execute.return_value.scalar_one_or_none.return_value = index_row
    project_id = uuid.uuid4()

    with patch("ragcore.query.pipeline.build_bm25_index", new=AsyncMock()) as mock_build:
        await _ensure_bm25_index(project_id, mock_session)
        mock_build.assert_not_awaited()
