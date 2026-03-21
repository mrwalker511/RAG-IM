"""Tests for document upload, status, delete, and BM25 invalidation."""

import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_upload_document_project_not_found(api_client):
    fake_id = uuid.uuid4()
    resp = await api_client.post(
        f"/projects/{fake_id}/documents",
        files={"file": ("test.txt", BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_document_enqueues_job(api_client):
    proj_resp = await api_client.post("/projects", json={"name": "doc-upload-project"})
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    mock_job = MagicMock()
    mock_job.job_id = "test-job-123"
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=mock_job)

    with patch("api.routers.documents.create_pool", return_value=mock_pool):
        resp = await api_client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("notes.txt", BytesIO(b"some content"), "text/plain")},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["job_id"] == "test-job-123"
    assert data["filename"] == "notes.txt"
    assert "document_id" in data


@pytest.mark.asyncio
async def test_get_document_status(api_client):
    proj_resp = await api_client.post("/projects", json={"name": "doc-status-project"})
    project_id = proj_resp.json()["id"]

    mock_job = MagicMock()
    mock_job.job_id = "status-job-456"
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=mock_job)

    with patch("api.routers.documents.create_pool", return_value=mock_pool):
        upload_resp = await api_client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("report.pdf", BytesIO(b"%PDF"), "application/pdf")},
        )
    document_id = upload_resp.json()["document_id"]

    status_resp = await api_client.get(
        f"/projects/{project_id}/documents/{document_id}/status"
    )
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["document_id"] == document_id
    assert data["status"] == "pending"
    assert data["filename"] == "report.pdf"


@pytest.mark.asyncio
async def test_get_document_status_not_found(api_client):
    proj_resp = await api_client.post("/projects", json={"name": "doc-status-404-project"})
    project_id = proj_resp.json()["id"]

    resp = await api_client.get(
        f"/projects/{project_id}/documents/{uuid.uuid4()}/status"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_invalidates_bm25(api_client):
    proj_resp = await api_client.post("/projects", json={"name": "doc-delete-project"})
    project_id = proj_resp.json()["id"]

    mock_job = MagicMock()
    mock_job.job_id = "delete-job-789"
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=mock_job)

    with patch("api.routers.documents.create_pool", return_value=mock_pool):
        upload_resp = await api_client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("delete_me.txt", BytesIO(b"bye"), "text/plain")},
        )
    document_id = upload_resp.json()["document_id"]

    with patch("api.routers.documents.invalidate_bm25_index", new_callable=AsyncMock) as mock_invalidate:
        del_resp = await api_client.delete(
            f"/projects/{project_id}/documents/{document_id}"
        )
        assert del_resp.status_code == 204
        mock_invalidate.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_document_not_found(api_client):
    proj_resp = await api_client.post("/projects", json={"name": "doc-delete-404-project"})
    project_id = proj_resp.json()["id"]

    resp = await api_client.delete(
        f"/projects/{project_id}/documents/{uuid.uuid4()}"
    )
    assert resp.status_code == 404
