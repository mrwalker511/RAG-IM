"""Tests for non-streaming and SSE streaming query endpoints."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ragcore.generation.base import GenerationResult
from ragcore.retrieval.vector_search import ChunkResult


def _make_chunk_result(project_id: uuid.UUID) -> ChunkResult:
    return ChunkResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        project_id=project_id,
        content="Paris is the capital of France.",
        score=0.95,
        chunk_index=0,
        filename="france.txt",
        metadata={},
    )


@pytest.mark.asyncio
async def test_query_project_not_found(api_client):
    resp = await api_client.post(
        f"/projects/{uuid.uuid4()}/query",
        json={"query": "What is the capital of France?"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_query_returns_answer_and_sources(api_client):
    proj_resp = await api_client.post("/projects", json={"name": "query-test-project"})
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    mock_result = MagicMock()
    mock_result.answer = "Paris is the capital of France."
    mock_result.sources = [_make_chunk_result(uuid.UUID(project_id))]
    mock_result.latency_ms = 42
    mock_result.tokens_used = 100

    with patch("api.routers.query.run_query", new_callable=AsyncMock, return_value=mock_result):
        resp = await api_client.post(
            f"/projects/{project_id}/query",
            json={"query": "What is the capital of France?"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Paris is the capital of France."
    assert len(data["sources"]) == 1
    assert data["sources"][0]["filename"] == "france.txt"
    assert data["tokens_used"] == 100
    assert data["latency_ms"] == 42


@pytest.mark.asyncio
async def test_query_with_rerank_false(api_client):
    proj_resp = await api_client.post("/projects", json={"name": "query-norerank-project"})
    project_id = proj_resp.json()["id"]

    mock_result = MagicMock()
    mock_result.answer = "42"
    mock_result.sources = []
    mock_result.latency_ms = 10
    mock_result.tokens_used = 50

    with patch("api.routers.query.run_query", new_callable=AsyncMock, return_value=mock_result) as mock_run:
        resp = await api_client.post(
            f"/projects/{project_id}/query",
            json={"query": "What is the answer?", "rerank": False},
        )
        assert resp.status_code == 200
        # reranker should be None when rerank=False
        _, kwargs = mock_run.call_args
        assert kwargs.get("reranker") is None


@pytest.mark.asyncio
async def test_stream_query_project_not_found(api_client):
    resp = await api_client.get(
        f"/projects/{uuid.uuid4()}/query/stream",
        params={"q": "hello"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stream_query_emits_sources_then_tokens(api_client):
    proj_resp = await api_client.post("/projects", json={"name": "stream-test-project"})
    project_id = proj_resp.json()["id"]

    chunk = _make_chunk_result(uuid.UUID(project_id))

    async def mock_token_gen():
        for token in ["Paris", " is", " the", " capital."]:
            yield token

    with (
        patch("api.routers.query._make_embedder") as mock_embedder_factory,
        patch("api.routers.query._make_generator") as mock_generator_factory,
        patch("api.routers.query.vector_search", new_callable=AsyncMock, return_value=[chunk]),
        patch("api.routers.query._ensure_bm25_index", new_callable=AsyncMock),
        patch("api.routers.query.bm25_search", new_callable=AsyncMock, return_value=[]),
    ):
        mock_embedder = AsyncMock()
        mock_embedder.embed = AsyncMock(return_value=[[0.0] * 1536])
        mock_embedder_factory.return_value = mock_embedder

        mock_generator = AsyncMock()
        mock_generator.generate = AsyncMock(return_value=mock_token_gen())
        mock_generator_factory.return_value = mock_generator

        resp = await api_client.get(
            f"/projects/{project_id}/query/stream",
            params={"q": "What is the capital?"},
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    raw = resp.text
    assert "event: sources" in raw
    assert "france.txt" in raw
    assert "[DONE]" in raw


@pytest.mark.asyncio
async def test_stream_query_emits_error_event_on_generator_failure(api_client):
    proj_resp = await api_client.post("/projects", json={"name": "stream-error-project"})
    project_id = proj_resp.json()["id"]

    chunk = _make_chunk_result(uuid.UUID(project_id))

    async def failing_token_gen():
        yield "start"
        raise RuntimeError("LLM exploded")

    with (
        patch("api.routers.query._make_embedder") as mock_embedder_factory,
        patch("api.routers.query._make_generator") as mock_generator_factory,
        patch("api.routers.query.vector_search", new_callable=AsyncMock, return_value=[chunk]),
        patch("api.routers.query._ensure_bm25_index", new_callable=AsyncMock),
        patch("api.routers.query.bm25_search", new_callable=AsyncMock, return_value=[]),
    ):
        mock_embedder = AsyncMock()
        mock_embedder.embed = AsyncMock(return_value=[[0.0] * 1536])
        mock_embedder_factory.return_value = mock_embedder

        mock_generator = AsyncMock()
        mock_generator.generate = AsyncMock(return_value=failing_token_gen())
        mock_generator_factory.return_value = mock_generator

        resp = await api_client.get(
            f"/projects/{project_id}/query/stream",
            params={"q": "trigger error"},
        )

    assert resp.status_code == 200
    raw = resp.text
    assert "event: error" in raw
    assert "LLM exploded" in raw
