import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ragcore.db.models import Base
from ragcore.embeddings.base import BaseEmbedder

TEST_DATABASE_URL = "postgresql+asyncpg://rag:rag@localhost:5432/test_rag"

# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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
# API client (populated in Phase 5)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def api_client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    from api.main import create_app
    from api.dependencies import get_db_session
    from ragcore.db.session import AsyncSessionLocal

    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
