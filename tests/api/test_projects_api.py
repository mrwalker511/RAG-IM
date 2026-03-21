import pytest
from httpx import ASGITransport, AsyncClient

from api.main import create_app
from ragcore.db.session import AsyncSessionLocal


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_and_list_project(app, db_session):
    from api.dependencies import get_db_session
    from collections.abc import AsyncGenerator
    from sqlalchemy.ext.asyncio import AsyncSession

    async def override():
        yield db_session

    app.dependency_overrides[get_db_session] = override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/projects", json={"name": "test-project"})
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert data["name"] == "test-project"

        list_resp = await client.get("/projects")
        assert list_resp.status_code == 200
        names = [p["name"] for p in list_resp.json()["projects"]]
        assert "test-project" in names

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_duplicate_project_returns_409(app, db_session):
    from api.dependencies import get_db_session

    async def override():
        yield db_session

    app.dependency_overrides[get_db_session] = override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/projects", json={"name": "dup-project"})
        resp = await client.post("/projects", json={"name": "dup-project"})
        assert resp.status_code == 409

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_nonexistent_project_returns_404(app, db_session):
    import uuid
    from api.dependencies import get_db_session

    async def override():
        yield db_session

    app.dependency_overrides[get_db_session] = override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(f"/projects/{uuid.uuid4()}")
        assert resp.status_code == 404

    app.dependency_overrides.clear()
