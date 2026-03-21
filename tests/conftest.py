import hashlib
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ragcore.db.models import APIKey, Base, Project
from ragcore.embeddings.base import BaseEmbedder

TEST_DATABASE_URL = "postgresql+asyncpg://rag:rag@localhost:5432/test_rag"

# Raw key inserted into the test DB once per session; sent in every api_client request.
TEST_API_KEY = "test-api-key-for-pytest"
TEST_API_KEY_HASH = hashlib.sha256(TEST_API_KEY.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Seeded API key — created once per session, reused by all api_client tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def seeded_api_key(test_engine) -> str:
    """Insert a test Project + APIKey into the test DB. Returns the raw key string."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        project = Project(name="__test_auth_project__")
        session.add(project)
        await session.flush()
        key = APIKey(
            project_id=project.id,
            key_hash=TEST_API_KEY_HASH,
            label="pytest",
        )
        session.add(key)
        await session.commit()
    return TEST_API_KEY


# ---------------------------------------------------------------------------
# Mock embedder
# ---------------------------------------------------------------------------

class MockEmbedder(BaseEmbedder):
    """Returns zero vectors of the configured dimension — no API call."""

    @property
    def dimension(self) -> int:
        return 1536

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dimension for _ in texts]


@pytest.fixture
def mock_embedder() -> MockEmbedder:
    return MockEmbedder()


# ---------------------------------------------------------------------------
# API client — X-API-Key included; middleware uses test DB session factory
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def api_client(test_engine, seeded_api_key) -> AsyncGenerator[AsyncClient, None]:
    from api.dependencies import get_db_session
    from api.main import create_app

    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session

    # Patch the middleware's session factory so auth lookups hit the test DB,
    # not the production DATABASE_URL.
    with patch("api.middleware.AsyncSessionLocal", factory):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-API-Key": seeded_api_key},
        ) as client:
            yield client
