from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import api_key_middleware
from api.routers import api_keys, documents, projects, query
from ragcore.config import settings
from ragcore.db.session import engine

# Dimensions known to be produced by each supported model.
_KNOWN_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "all-MiniLM-L6-v2": 384,
}


def _validate_embedding_dim() -> None:
    expected = _KNOWN_DIMS.get(settings.EMBEDDING_MODEL)
    if expected is not None and settings.EMBEDDING_DIM != expected:
        raise RuntimeError(
            f"EMBEDDING_DIM={settings.EMBEDDING_DIM} does not match "
            f"model '{settings.EMBEDDING_MODEL}' which produces {expected}-dimensional vectors. "
            f"Set EMBEDDING_DIM={expected} in your .env or update the Alembic migration."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_embedding_dim()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG Framework API",
        description="Reusable multi-project Retrieval-Augmented Generation API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(api_key_middleware)

    app.include_router(projects.router)
    app.include_router(documents.router)
    app.include_router(query.router)
    app.include_router(api_keys.router)

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
