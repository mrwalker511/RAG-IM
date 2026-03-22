"""Tests for document upload, status, delete, and index maintenance."""

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
    enqueue_args = mock_pool.enqueue_job.await_args.args
    assert enqueue_args[0] == "ingest_document"
    assert enqueue_args[1] == project_id
    assert enqueue_args[3]["document_id"] == data["document_id"]
    assert enqueue_args[3]["original_filename"] == "notes.txt"


@pytest.mark.asyncio
async def test_list_documents_returns_project_documents(api_client):
    proj_resp = await api_client.post("/projects", json={"name": "doc-list-project"})
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    mock_job = MagicMock()
    mock_job.job_id = "list-job-123"
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock(return_value=mock_job)

    with patch("api.routers.documents.create_pool", return_value=mock_pool):
        await api_client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("a.txt", BytesIO(b"alpha"), "text/plain")},
        )
        await api_client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("b.txt", BytesIO(b"beta"), "text/plain")},
        )

    resp = await api_client.get(f"/projects/{project_id}/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    filenames = {doc["filename"] for doc in data["documents"]}
    assert filenames == {"a.txt", "b.txt"}


@pytest.mark.asyncio
async def test_list_documents_project_not_found(api_client):
    resp = await api_client.get(f"/projects/{uuid.uuid4()}/documents")
    assert resp.status_code == 404


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
async def test_delete_document_runs_full_index_maintenance(api_client):
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

    with patch("api.routers.documents.maintain_project_indexes_for_document_delete", new_callable=AsyncMock) as mock_maintain:
        del_resp = await api_client.delete(
            f"/projects/{project_id}/documents/{document_id}"
        )
        assert del_resp.status_code == 204
        mock_maintain.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_document_not_found(api_client):
    proj_resp = await api_client.post("/projects", json={"name": "doc-delete-404-project"})
    project_id = proj_resp.json()["id"]

    resp = await api_client.delete(
        f"/projects/{project_id}/documents/{uuid.uuid4()}"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_project_scoped_api_key_cannot_access_other_project(api_client):
    project_a = (await api_client.post("/projects", json={"name": "scoped-doc-project-a"})).json()["id"]
    project_b = (await api_client.post("/projects", json={"name": "scoped-doc-project-b"})).json()["id"]

    key_resp = await api_client.post(
        f"/projects/{project_a}/api-keys",
        json={"label": "project-a-only"},
    )
    project_a_key = key_resp.json()["key"]

    resp = await api_client.get(
        f"/projects/{project_b}/documents",
        headers={"X-API-Key": project_a_key},
    )
    assert resp.status_code == 403
