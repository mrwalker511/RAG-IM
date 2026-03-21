# RAG Framework — Agent Context

## Project Overview

A production-grade, reusable Retrieval-Augmented Generation (RAG) framework.
Each project gets its own isolated namespace (collection) within a shared PostgreSQL + pgvector database.
The framework is general-purpose — deployable across any internal initiative.

## Stack

- Python 3.11+, FastAPI, SQLAlchemy 2.x (async), asyncpg
- PostgreSQL 16 + pgvector, Alembic migrations
- ARQ + Redis for async task queue
- OpenAI / SentenceTransformers (pluggable via BaseEmbedder)
- LiteLLM for multi-provider LLM support (OpenAI, Anthropic, Azure, etc.)
- Typer + Rich CLI
- pytest + pytest-asyncio + httpx for testing

## Key Design Contracts (Do Not Break)

```python
# BaseParser
class BaseParser(ABC):
    @abstractmethod
    def parse(self, path: Path) -> list[str]:
        """Return list of text pages/sections."""

# BaseEmbedder
class BaseEmbedder(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return list of embedding vectors."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension."""

# BaseLLMGenerator
class BaseLLMGenerator(ABC):
    @abstractmethod
    async def generate(self, prompt: str, stream: bool = False) -> str | AsyncGenerator:
        """Generate answer from prompt."""
```

## Directory Layout

```
ragcore/          Core library (config, db, ingestion, embeddings, retrieval, generation, query, observability)
  db/
    models.py     ORM models
    session.py    Async SQLAlchemy engine + session factory (pool_size, max_overflow, pool_timeout configurable)
    redis.py      Shared async Redis client with connection pool (REDIS_MAX_CONNECTIONS configurable)
  query/
    pipeline.py   run_query — includes Redis result cache (QUERY_CACHE_TTL, skipped for streaming)
api/              FastAPI app (routers, middleware, dependencies)
  middleware.py   api_key_middleware (SHA-256 key auth) + rate_limit_middleware (sliding-window per-key, RATE_LIMIT_PER_MINUTE)
  main.py         CORS restricted via CORS_ORIGINS config; Redis pool closed in lifespan
worker/           ARQ worker entrypoint
cli/              Typer CLI
tests/            unit/, integration/, api/ test suites
  conftest.py     seeded_api_key fixture; api_client patches api.middleware.AsyncSessionLocal + sends X-API-Key header
alembic/          Versioned DB migrations
.github/          CI workflow
```

## Database Schema

| Table         | Key Columns                                                              |
|---------------|--------------------------------------------------------------------------|
| projects      | id, name, config (JSONB), created_at                                     |
| documents     | id, project_id, filename, content_hash, status, metadata (JSONB)        |
| chunks        | id, document_id, project_id, content, embedding (vector), chunk_index   |
| bm25_indexes  | id, project_id, index_data (BYTEA), updated_at                          |
| query_logs    | id, project_id, query_text, latency_ms, tokens_used, top_scores (JSONB) |
| api_keys      | id, project_id, key_hash, label, created_at, last_used_at               |

## Infrastructure Configuration (ragcore/config.py)

| Setting | Default | Purpose |
|---|---|---|
| `CORS_ORIGINS` | `"*"` | Comma-separated allowed origins; restrict in production |
| `RATE_LIMIT_PER_MINUTE` | `60` | Sliding-window per-API-key rate limit; `0` = disabled |
| `DB_POOL_SIZE` | `10` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Max connections above pool_size |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait for a connection |
| `REDIS_MAX_CONNECTIONS` | `20` | Redis connection pool cap |
| `QUERY_CACHE_TTL` | `300` | Query result cache TTL in seconds; `0` = disabled |

## Development Rules

1. **Never add `unstructured`** as a dependency — heavy native deps bloat Docker; use pypdf, python-docx, markdown-it-py
2. **All ingestion is async** — no sync ingestion in API request handlers; large files go through ARQ workers
3. **BM25 index is persisted** to DB as BYTEA; never rebuilt on every query — load from DB, rebuild only when stale
4. **All operations are scoped by `project_id`** — no cross-project data leakage
5. **SHA-256 deduplication** — skip re-ingesting unchanged documents (compare content_hash)
6. **Tests use abstract interfaces** via dependency injection, not concrete implementations directly
7. **Generic examples only** — no domain-specific language in code, docs, or examples
8. **Middleware uses `AsyncSessionLocal` directly** — not via DI; tests must patch `api.middleware.AsyncSessionLocal` to redirect auth lookups to the test DB
9. **Redis errors in cache helpers fail silently** — a Redis outage must never break queries; cache misses are acceptable
10. **Rate limiter state (`_rate_windows`) is in-process only** — resets on restart; not suitable for multi-worker deployments without an external store
