"""End-to-end upload -> ingest -> query -> cache integration test."""

import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from ragcore.embeddings.base import BaseEmbedder
from ragcore.generation.base import GenerationResult
from ragcore.ingestion.worker import ingest_document
from ragcore.query.pipeline import _cache_key


class TestEmbedder(BaseEmbedder):
    @property
    def dimension(self) -> int:
        return 384

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] * self.dimension for text in texts]


class EchoContextGenerator:
    def __init__(self):
        self.generate = AsyncMock(side_effect=self._generate)

    async def _generate(self, prompt: str, stream: bool = False):
        assert stream is False
        context = prompt.split("Context:\n", 1)[1].split("\n\nQuestion:", 1)[0]
        answer = "I do not know."
        if context != "(no context)":
            _, chunk_text = context.split("\n", 1)
            answer = chunk_text.split("\n\n---\n\n", 1)[0].strip()
        return GenerationResult(text=answer, tokens_used=max(1, len(answer.split())))


class FakeCacheRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        self.store[key] = value


@pytest.mark.asyncio
async def test_upload_ingest_query_and_cache(api_client, test_engine):
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    project_resp = await api_client.post("/projects", json={"name": "integration-upload-query"})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    mock_job = MagicMock()
    mock_job.job_id = "integration-job-123"
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=mock_job)

    with (
        patch("api.middleware._check_rate_limit", new=AsyncMock(return_value=(True, 0))),
        patch("api.routers.documents.create_pool", return_value=mock_pool),
    ):
        upload_resp = await api_client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("integration.txt", BytesIO(b"Deployment code phrase is teal-orbit.\n"), "text/plain")},
        )

    assert upload_resp.status_code == 202
    enqueue_args = mock_pool.enqueue_job.await_args.args
    _, enqueued_project_id, file_path, metadata = enqueue_args

    with (
        patch("ragcore.ingestion.worker.AsyncSessionLocal", factory),
        patch("ragcore.ingestion.worker.make_embedder", return_value=TestEmbedder()),
    ):
        ingest_result = await ingest_document({}, enqueued_project_id, file_path, metadata)

    assert ingest_result["status"] == "complete"

    fake_cache = FakeCacheRedis()
    generator = EchoContextGenerator()

    with (
        patch("api.middleware._check_rate_limit", new=AsyncMock(return_value=(True, 0))),
        patch("api.routers.query._make_embedder", return_value=TestEmbedder()),
        patch("api.routers.query._make_generator", return_value=generator),
        patch("ragcore.query.pipeline.get_redis", return_value=fake_cache),
    ):
        first_query = await api_client.post(
            f"/projects/{project_id}/query",
            json={"query": "What is the deployment code phrase?", "rerank": False, "mode": "naive"},
        )
        second_query = await api_client.post(
            f"/projects/{project_id}/query",
            json={"query": "What is the deployment code phrase?", "rerank": False, "mode": "naive"},
        )

    assert first_query.status_code == 200
    assert second_query.status_code == 200
    first_data = first_query.json()
    second_data = second_query.json()
    assert "teal-orbit" in first_data["answer"]
    assert first_data["sources"][0]["filename"] == "integration.txt"
    assert second_data == first_data
    assert generator.generate.await_count == 1

    expected_cache_key = _cache_key(
        uuid.UUID(project_id),
        "What is the deployment code phrase?",
        5,
        mode="naive",
    )
    assert expected_cache_key in fake_cache.store
