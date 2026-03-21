"""Tests for API key management endpoints."""

import pytest


@pytest.mark.asyncio
async def test_create_api_key(api_client):
    # Create a project first
    proj_resp = await api_client.post("/projects", json={"name": "key-test-project"})
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    resp = await api_client.post(
        f"/projects/{project_id}/api-keys",
        json={"label": "my-key"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "key" in data  # raw key only returned at creation
    assert data["label"] == "my-key"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_api_keys(api_client):
    proj_resp = await api_client.post("/projects", json={"name": "key-list-project"})
    project_id = proj_resp.json()["id"]

    await api_client.post(f"/projects/{project_id}/api-keys", json={"label": "k1"})
    await api_client.post(f"/projects/{project_id}/api-keys", json={"label": "k2"})

    resp = await api_client.get(f"/projects/{project_id}/api-keys")
    assert resp.status_code == 200
    keys = resp.json()
    assert len(keys) == 2
    labels = {k["label"] for k in keys}
    assert labels == {"k1", "k2"}
    # Raw key must NOT be in list response
    for k in keys:
        assert "key" not in k


@pytest.mark.asyncio
async def test_delete_api_key(api_client):
    proj_resp = await api_client.post("/projects", json={"name": "key-delete-project"})
    project_id = proj_resp.json()["id"]

    create_resp = await api_client.post(f"/projects/{project_id}/api-keys", json={"label": "temp"})
    key_id = create_resp.json()["id"]

    del_resp = await api_client.delete(f"/projects/{project_id}/api-keys/{key_id}")
    assert del_resp.status_code == 204

    list_resp = await api_client.get(f"/projects/{project_id}/api-keys")
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_create_api_key_project_not_found(api_client):
    import uuid
    resp = await api_client.post(
        f"/projects/{uuid.uuid4()}/api-keys",
        json={"label": "x"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_api_key_not_found(api_client):
    import uuid
    proj_resp = await api_client.post("/projects", json={"name": "key-notfound-project"})
    project_id = proj_resp.json()["id"]

    resp = await api_client.delete(f"/projects/{project_id}/api-keys/{uuid.uuid4()}")
    assert resp.status_code == 404
