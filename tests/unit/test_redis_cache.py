"""Unit tests for the Redis query cache helpers in ragcore.query.pipeline."""

import json
import uuid
from unittest.mock import AsyncMock, patch

from ragcore.query.pipeline import (
    QueryResult,
    SourceAttribution,
    _cache_key,
    _get_cached,
    _set_cached,
)


def _make_result() -> QueryResult:
    return QueryResult(
        answer="test answer",
        sources=[
            SourceAttribution(
                chunk_id=str(uuid.uuid4()),
                filename="doc.txt",
                chunk_index=0,
                score=0.9,
            )
        ],
        latency_ms=100,
        tokens_used=42,
    )


# ---------------------------------------------------------------------------
# _cache_key
# ---------------------------------------------------------------------------

def test_cache_key_is_deterministic():
    pid = uuid.uuid4()
    assert _cache_key(pid, "query", 5) == _cache_key(pid, "query", 5)


def test_cache_key_differs_for_different_queries():
    pid = uuid.uuid4()
    assert _cache_key(pid, "query A", 5) != _cache_key(pid, "query B", 5)


def test_cache_key_differs_for_different_top_k():
    pid = uuid.uuid4()
    assert _cache_key(pid, "query", 5) != _cache_key(pid, "query", 10)


def test_cache_key_differs_for_different_projects():
    assert _cache_key(uuid.uuid4(), "query", 5) != _cache_key(uuid.uuid4(), "query", 5)


def test_cache_key_has_expected_prefix():
    k = _cache_key(uuid.uuid4(), "query", 5)
    assert k.startswith("query_cache:")


# ---------------------------------------------------------------------------
# _get_cached
# ---------------------------------------------------------------------------

async def test_get_cached_returns_none_when_ttl_zero():
    with patch("ragcore.query.pipeline.settings") as s:
        s.QUERY_CACHE_TTL = 0
        result = await _get_cached("any-key")
    assert result is None


async def test_get_cached_returns_none_on_cache_miss():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    with (
        patch("ragcore.query.pipeline.settings") as s,
        patch("ragcore.query.pipeline.get_redis", return_value=mock_redis),
    ):
        s.QUERY_CACHE_TTL = 300
        result = await _get_cached("missing-key")

    assert result is None
    mock_redis.get.assert_awaited_once_with("missing-key")


async def test_get_cached_deserializes_result_on_hit():
    expected = _make_result()
    payload = json.dumps({
        "answer": expected.answer,
        "sources": [
            {
                "chunk_id": s.chunk_id,
                "filename": s.filename,
                "chunk_index": s.chunk_index,
                "score": s.score,
            }
            for s in expected.sources
        ],
        "latency_ms": expected.latency_ms,
        "tokens_used": expected.tokens_used,
    })
    mock_redis = AsyncMock()
    mock_redis.get.return_value = payload

    with (
        patch("ragcore.query.pipeline.settings") as s,
        patch("ragcore.query.pipeline.get_redis", return_value=mock_redis),
    ):
        s.QUERY_CACHE_TTL = 300
        result = await _get_cached("hit-key")

    assert isinstance(result, QueryResult)
    assert result.answer == expected.answer
    assert result.tokens_used == expected.tokens_used
    assert len(result.sources) == 1
    assert result.sources[0].filename == "doc.txt"


async def test_get_cached_returns_none_on_redis_error():
    """Redis connection failure must not propagate — returns None silently."""
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = ConnectionError("Redis down")

    with (
        patch("ragcore.query.pipeline.settings") as s,
        patch("ragcore.query.pipeline.get_redis", return_value=mock_redis),
    ):
        s.QUERY_CACHE_TTL = 300
        result = await _get_cached("error-key")

    assert result is None


# ---------------------------------------------------------------------------
# _set_cached
# ---------------------------------------------------------------------------

async def test_set_cached_skips_when_ttl_zero():
    mock_redis = AsyncMock()

    with (
        patch("ragcore.query.pipeline.settings") as s,
        patch("ragcore.query.pipeline.get_redis", return_value=mock_redis),
    ):
        s.QUERY_CACHE_TTL = 0
        await _set_cached("key", _make_result())

    mock_redis.setex.assert_not_awaited()


async def test_set_cached_writes_correct_key_ttl_and_payload():
    result = _make_result()
    mock_redis = AsyncMock()

    with (
        patch("ragcore.query.pipeline.settings") as s,
        patch("ragcore.query.pipeline.get_redis", return_value=mock_redis),
    ):
        s.QUERY_CACHE_TTL = 60
        await _set_cached("test-key", result)

    mock_redis.setex.assert_awaited_once()
    args = mock_redis.setex.call_args[0]
    assert args[0] == "test-key"
    assert args[1] == 60
    data = json.loads(args[2])
    assert data["answer"] == result.answer
    assert data["tokens_used"] == result.tokens_used
    assert len(data["sources"]) == 1


async def test_set_cached_survives_redis_error():
    """Redis write failure must not propagate — continues silently."""
    mock_redis = AsyncMock()
    mock_redis.setex.side_effect = ConnectionError("Redis down")

    with (
        patch("ragcore.query.pipeline.settings") as s,
        patch("ragcore.query.pipeline.get_redis", return_value=mock_redis),
    ):
        s.QUERY_CACHE_TTL = 60
        await _set_cached("key", _make_result())  # must not raise
