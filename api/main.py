import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from api.middleware import api_key_middleware, rate_limit_middleware
from api.routers import api_keys, documents, projects, query
from ragcore.bootstrap import ensure_bootstrap_project_api_key
from ragcore.config import settings
from ragcore.db.redis import close_redis_pool
from ragcore.db.session import engine

_WEBAPP_PATH = Path(__file__).resolve().parent / "static" / "index.html"

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


def _render_web_app() -> str:
    return _WEBAPP_PATH.read_text(encoding="utf-8").replace(
        "__BOOTSTRAP_API_KEY__",
        json.dumps(settings.BOOTSTRAP_API_KEY),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_embedding_dim()
    await ensure_bootstrap_project_api_key()
    yield
    await engine.dispose()
    await close_redis_pool()


def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG Framework API",
        description="Reusable multi-project Retrieval-Augmented Generation API",
        version="1.0.0",
        lifespan=lifespan,
    )

    cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["X-API-Key", "Content-Type", "Authorization"],
    )
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(api_key_middleware)

    app.include_router(projects.router)
    app.include_router(documents.router)
    app.include_router(query.router)
    app.include_router(api_keys.router)

    @app.get("/", include_in_schema=False)
    async def index():
        return HTMLResponse(_render_web_app())

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
