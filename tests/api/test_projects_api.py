import uuid

import pytest
from httpx import ASGITransport, AsyncClient


async def test_health():
    """Health endpoint is exempt from auth — test without api_client fixture."""
    from api.main import create_app
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_create_and_list_project(api_client):
    create_resp = await api_client.post("/projects", json={"name": "test-project"})
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["name"] == "test-project"

    list_resp = await api_client.get("/projects")
    assert list_resp.status_code == 200
    names = [p["name"] for p in list_resp.json()["projects"]]
    assert "test-project" in names


async def test_create_duplicate_project_returns_409(api_client):
    await api_client.post("/projects", json={"name": "dup-project"})
    resp = await api_client.post("/projects", json={"name": "dup-project"})
    assert resp.status_code == 409


async def test_delete_nonexistent_project_returns_404(api_client):
    resp = await api_client.delete(f"/projects/{uuid.uuid4()}")
    assert resp.status_code == 404
