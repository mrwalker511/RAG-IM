"""Unit tests for ingestion pipeline document continuity."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ragcore.db.models import Document
from ragcore.ingestion.pipeline import run_ingestion


@pytest.mark.asyncio
async def test_run_ingestion_updates_pending_document_from_metadata(tmp_path):
    file_path = tmp_path / "tmp-upload.txt"
    file_path.write_text("hello world", encoding="utf-8")
    project_id = uuid.uuid4()

    pending_doc = Document(
        project_id=project_id,
        filename="old-name.txt",
        content_hash="stale-hash",
        status="pending",
        meta={"job_id": "job-123"},
    )
    pending_doc.id = uuid.uuid4()
    pending_doc.chunks = []

    mock_session = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = pending_doc
    mock_session.execute = AsyncMock(return_value=execute_result)
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.delete = AsyncMock()

    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[[0.0] * 1536])

    chunk_result = MagicMock(content="hello world", chunk_index=0)
    parser = MagicMock()
    parser.parse.return_value = ["hello world"]

    with (
        patch("ragcore.ingestion.pipeline._get_parser", return_value=parser),
        patch("ragcore.ingestion.pipeline.chunk_texts", return_value=[chunk_result]),
    ):
        result = await run_ingestion(
            project_id=project_id,
            file_path=Path(file_path),
            session=mock_session,
            embedder=embedder,
            metadata={
                "document_id": str(pending_doc.id),
                "original_filename": "report.txt",
            },
        )

    assert result is pending_doc
    assert result.filename == "report.txt"
    assert result.status == "complete"
    assert result.meta["job_id"] == "job-123"
    assert result.meta["document_id"] == str(pending_doc.id)
    assert result.meta["original_filename"] == "report.txt"
    assert mock_session.add.call_count == 1
