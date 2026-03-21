from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import api_key_middleware
from api.routers import api_keys, documents, projects, query
from ragcore.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
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
