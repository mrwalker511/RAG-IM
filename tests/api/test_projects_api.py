import uuid
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient


async def test_health():
    """Health endpoint is exempt from auth — test without api_client fixture."""
    from api.main import create_app
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_root_serves_web_app_without_auth():
    from api.main import create_app

    with patch("api.main.settings.BOOTSTRAP_API_KEY", "bootstrap-test-key"):
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "RAG Control Room" in resp.text
    assert "bootstrap-test-key" in resp.text


async def test_handbook_index_serves_doc_browser_without_auth():
    from api.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/handbook")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Project Handbook" in resp.text
    assert "README.md" in resp.text


async def test_handbook_doc_serves_rendered_markdown_without_auth():
    from api.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/handbook/README.md")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "RAG Framework" in resp.text
    assert "<h1>RAG Framework</h1>" in resp.text


async def test_handbook_missing_doc_returns_404():
    from api.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/handbook/not-real.md")

    assert resp.status_code == 404
    assert "Document not found" in resp.text


async def test_cors_preflight_returns_expected_headers():
    from api.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.options(
            "/projects",
            headers={
                "Origin": "http://frontend.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "*"
    assert "POST" in resp.headers["access-control-allow-methods"]


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


async def test_project_scoped_key_cannot_list_all_projects(api_client):
    project_id = (await api_client.post("/projects", json={"name": "bootstrap-only-project"})).json()["id"]
    key_resp = await api_client.post(
        f"/projects/{project_id}/api-keys",
        json={"label": "scoped"},
    )
    scoped_key = key_resp.json()["key"]

    resp = await api_client.get("/projects", headers={"X-API-Key": scoped_key})
    assert resp.status_code == 403
