# RAG Framework — Skills & Conventions

## Abstract Interface Pattern

All pluggable components (parsers, embedders, LLMs) extend an ABC defined in a `base.py` file.
Tests run against the abstract interface via dependency injection — never against the concrete class directly.

```python
# Good: inject the interface
async def run_query(embedder: BaseEmbedder, generator: BaseLLMGenerator, ...):
    ...

# Bad: instantiate concrete class inside logic
embedder = OpenAIEmbedder()
```

## Async-First

- Use `async def` and `await` throughout
- SQLAlchemy sessions are `AsyncSession` everywhere
- Background tasks go through ARQ workers, not FastAPI `BackgroundTasks`
- API handlers for uploads must enqueue an ARQ job and return immediately

## Project Scoping

Every DB query involving documents, chunks, query logs, or BM25 indexes **must** filter by `project_id`.

```python
# Always include project_id filter
stmt = select(Chunk).where(Chunk.project_id == project_id, ...)
```

## BM25 Index Lifecycle

1. Built once after ingest or delete events (mark stale on change)
2. Serialized with `pickle` → stored as BYTEA in `bm25_indexes` table
3. Loaded from DB on query — **not rebuilt per query**
4. Rebuilt lazily before next query when stale flag is set

```python
# Correct pattern
index = await load_bm25_index(project_id, session)
if index is None or index.is_stale:
    index = await rebuild_bm25_index(project_id, session)
results = index.search(tokens, top_k)
```

## Embedding Batching

- OpenAI embedder batches requests and respects rate limits
- SentenceTransformer embedder runs locally — no API key required (local fallback)
- Both implement `BaseEmbedder`; swap via `EMBEDDING_PROVIDER` env var

## Chunking Guard

Chunk size must be validated against the embedding model's max token limit.
Raise `ConfigError` on violation.

```python
# Defaults (overridable per project via projects.config JSONB)
DEFAULT_CHUNK_SIZE = 512    # tokens
DEFAULT_CHUNK_OVERLAP = 64  # tokens
# text-embedding-3-small max: 8191 tokens
```

## API Auth

All API endpoints require `X-API-Key` header. Keys are:
- SHA-256 hashed on storage
- Stored in `api_keys` table, scoped to a `project_id`
- Validated in `api/middleware.py` (`api_key_middleware`) before reaching route handlers

```
Missing key  → 401 Unauthorized
Invalid key  → 401 Unauthorized
Valid key    → pass through; key object attached to request.state.api_key
```

Exempt paths (no auth required): `/`, `/docs`, `/openapi.json`, `/redoc`, `/health`

## Rate Limiting

Implemented in `api/middleware.py` (`rate_limit_middleware`), runs before auth middleware.

- Sliding-window algorithm: tracks request timestamps per API key hash in `_rate_windows` (in-process `defaultdict(deque)`)
- Window: 60 seconds; limit: `RATE_LIMIT_PER_MINUTE` (default 60)
- Exceeding limit → `429 Too Many Requests` with `Retry-After` header
- `RATE_LIMIT_PER_MINUTE=0` disables limiting entirely
- State is in-process only — resets on restart; not suitable for multi-process deployments

## Redis Query Cache

Implemented in `ragcore/query/pipeline.py` (`_get_cached`, `_set_cached`, `_cache_key`).

- Cache key: `query_cache:<sha256(project_id:query_text:top_k)>`
- Populated after successful LLM generation; TTL = `QUERY_CACHE_TTL` seconds (default 300)
- Cache lookup happens before any vector search or LLM call
- Streaming queries (`stream=True`) **bypass the cache entirely** — no read, no write
- Redis errors fail silently in both read and write — a Redis outage never breaks queries
- Shared Redis client via `ragcore/db/redis.py` (`get_redis()`, `get_redis_pool()`)

## Connection Pooling

**SQLAlchemy** (`ragcore/db/session.py`):
- `pool_size=DB_POOL_SIZE` (default 10)
- `max_overflow=DB_MAX_OVERFLOW` (default 20)
- `pool_timeout=DB_POOL_TIMEOUT` (default 30s)
- `pool_pre_ping=True` — validates connections before use

**Redis** (`ragcore/db/redis.py`):
- `ConnectionPool.from_url(REDIS_URL, max_connections=REDIS_MAX_CONNECTIONS)`
- Single shared pool; closed in app lifespan via `close_redis_pool()`

## Hybrid Search (RRF)

Reciprocal Rank Fusion combines vector and BM25 results:

```python
def reciprocal_rank_fusion(
    vector_results: list[ChunkResult],
    bm25_results: list[ChunkResult],
    k: int = 60,
) -> list[ChunkResult]:
    # score = sum(1 / (k + rank_i)) for each list
```

## Observability

- All query events logged async to `query_logs` with: latency_ms, tokens_used, top_scores, project_id
- Ingestion and query pipelines emit **structured JSON logs** (use stdlib `logging` with JSON formatter)
- Debug trace flag per query: dumps retrieved chunks + scores to stdout when enabled

## Testing Conventions

| Fixture / Pattern | Purpose |
|---|---|
| `test_engine` | Session-scoped async engine; drops/recreates all tables at start and teardown |
| `db_session` | Function-scoped session; rolls back after each test |
| `seeded_api_key` | Session-scoped; inserts a `Project` + `APIKey` row into test DB; returns raw key string |
| `api_client` | Async HTTP client with `X-API-Key` header set; patches `api.middleware.AsyncSessionLocal` to use test DB so auth middleware works |
| `mock_embedder` | Returns zero vectors of correct dimension — no API call |
| Integration tests | Seed DB with known data before asserting retrieval accuracy |

**Critical test patterns:**
- Always patch `api.middleware.AsyncSessionLocal` when testing auth-gated routes — the middleware bypasses DI
- Always mock `_get_cached` and `_set_cached` in `run_query` unit tests — they attempt Redis connections
- Streaming tests do not need cache mocks — `stream=True` skips the cache path entirely
- `asyncio_mode = "auto"` is set — `@pytest.mark.asyncio` decorators are redundant
- `asyncio_default_fixture_loop_scope = "session"` — session-scoped async fixtures share one event loop

## CLI Usage (Generic Examples)

```bash
docker compose up -d

rag project create "my-project"
rag project list
rag project delete "my-project"

rag ingest my-project ./docs/
rag ingest status <job_id>

rag query my-project "Summarize the key points in these documents."
rag query my-project "What does section 3 cover?" --top-k 10 --stream
```

## Adding a New Provider

To add a new embedder or LLM backend:
1. Create a new file in `ragcore/embeddings/` or `ragcore/generation/`
2. Subclass `BaseEmbedder` or `BaseLLMGenerator`
3. Implement all abstract methods
4. Add the provider name to `EMBEDDING_PROVIDER` / `LLM_PROVIDER` enum in `config.py`
5. Wire it in the factory function used by the query pipeline
6. Add unit tests using the abstract interface fixture
