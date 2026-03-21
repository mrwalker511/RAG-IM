"""Unit tests for the ARQ ingest_document worker task."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ragcore.ingestion.worker import WorkerSettings


def test_worker_settings_has_redis_settings_object():
    """RedisSettings must be a proper object, not a raw string."""
    from arq.connections import RedisSettings
    assert isinstance(WorkerSettings.redis_settings, RedisSettings), (
        "WorkerSettings.redis_settings must be a RedisSettings instance, not a string. "
        "Use RedisSettings.from_dsn(settings.REDIS_URL)."
    )


def test_worker_settings_registers_ingest_document():
    from ragcore.ingestion.worker import ingest_document
    assert ingest_document in WorkerSettings.functions


@pytest.mark.asyncio
async def test_ingest_document_returns_document_id_and_status():
    from ragcore.ingestion.worker import ingest_document

    project_id = uuid.uuid4()
    file_path = "/tmp/test_doc.txt"

    mock_doc = MagicMock()
    mock_doc.id = uuid.uuid4()
    mock_doc.status = "completed"

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.commit = AsyncMock()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value = mock_session

    with (
        patch("ragcore.ingestion.worker.AsyncSessionLocal", mock_session_factory),
        patch("ragcore.ingestion.worker.OpenAIEmbedder") as mock_embedder_cls,
        patch("ragcore.ingestion.worker.run_ingestion", new_callable=AsyncMock, return_value=mock_doc),
    ):
        mock_embedder_cls.return_value = MagicMock()
        ctx = {}
        result = await ingest_document(ctx, str(project_id), file_path)

    assert result["document_id"] == str(mock_doc.id)
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_ingest_document_passes_metadata_to_pipeline():
    from ragcore.ingestion.worker import ingest_document

    project_id = uuid.uuid4()
    file_path = "/tmp/meta_doc.txt"
    metadata = {"original_filename": "meta_doc.txt", "source": "test"}

    mock_doc = MagicMock()
    mock_doc.id = uuid.uuid4()
    mock_doc.status = "completed"

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.commit = AsyncMock()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value = mock_session

    with (
        patch("ragcore.ingestion.worker.AsyncSessionLocal", mock_session_factory),
        patch("ragcore.ingestion.worker.OpenAIEmbedder"),
        patch("ragcore.ingestion.worker.run_ingestion", new_callable=AsyncMock, return_value=mock_doc) as mock_run,
    ):
        await ingest_document({}, str(project_id), file_path, metadata)
        _, kwargs = mock_run.call_args
        assert kwargs["metadata"] == metadata
        assert kwargs["project_id"] == project_id
        assert kwargs["file_path"] == Path(file_path)
