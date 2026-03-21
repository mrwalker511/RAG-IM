# RAG Framework — Agent Context

FastAPI + PostgreSQL/pgvector + Redis + ARQ. Multi-project, async-first.

## Stack

Python 3.11+, FastAPI, SQLAlchemy 2.x (async), asyncpg, PostgreSQL 16 + pgvector, Alembic, ARQ + Redis, LiteLLM, Typer + Rich CLI, pytest + httpx

## Design Contracts (Do Not Break)

```python
class BaseParser(ABC):
    def parse(self, path: Path) -> list[str]: ...        # list of text pages/sections

class BaseEmbedder(ABC):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...

class BaseLLMGenerator(ABC):
    async def generate(self, prompt: str, stream: bool = False) -> str | AsyncGenerator: ...
```

## Directory Layout

```
ragcore/        Core library
  db/
    models.py   ORM models
    session.py  Async SQLAlchemy engine + session factory (pool_size, max_overflow, pool_timeout)
    redis.py    Shared async Redis client (REDIS_MAX_CONNECTIONS)
  query/
    pipeline.py run_query — Redis result cache (QUERY_CACHE_TTL; bypassed when stream=True)
api/
  middleware.py api_key_middleware (SHA-256) + rate_limit_middleware (sliding-window, RATE_LIMIT_PER_MINUTE)
  main.py       CORS via CORS_ORIGINS; Redis pool closed in lifespan
worker/         ARQ worker
cli/            Typer CLI
tests/          unit/, integration/, api/
  conftest.py   seeded_api_key; api_client patches api.middleware.AsyncSessionLocal + sends X-API-Key
alembic/        DB migrations
```

## Database Schema

| Table | Key Columns |
|---|---|
| projects | id, name, config (JSONB) |
| documents | id, project_id, filename, content_hash, status, metadata (JSONB) |
| chunks | id, document_id, project_id, content, embedding (vector), chunk_index |
| bm25_indexes | id, project_id, index_data (BYTEA), updated_at |
| query_logs | id, project_id, query_text, latency_ms, tokens_used, top_scores (JSONB) |
| api_keys | id, project_id, key_hash, label |

## Dev Rules

1. No `unstructured` — use pypdf, python-docx, markdown-it-py
2. All ingestion is async — uploads enqueue ARQ jobs, never block request handlers
3. BM25 persisted as BYTEA — load from DB, rebuild only when stale
4. All queries scoped by `project_id` — no cross-project leakage
5. SHA-256 deduplication — skip re-ingesting unchanged files
6. Middleware uses `AsyncSessionLocal` directly — tests must patch `api.middleware.AsyncSessionLocal`
7. Redis cache errors fail silently — Redis outage must never break queries
