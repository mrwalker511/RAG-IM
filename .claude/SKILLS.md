# RAG Framework — Skills & Conventions

## Abstract Interface Pattern

Inject interfaces, never instantiate concrete classes inside logic.

```python
# Good
async def run_query(embedder: BaseEmbedder, generator: BaseLLMGenerator, ...): ...

# Bad
embedder = OpenAIEmbedder()  # inside logic
```

## Async-First

- `async def` + `await` everywhere
- `AsyncSession` for all DB work
- Background tasks → ARQ workers, not `FastAPI.BackgroundTasks`
- Upload handlers enqueue ARQ job and return immediately

## Project Scoping

Every query on documents, chunks, query_logs, bm25_indexes **must** filter by `project_id`.

```python
stmt = select(Chunk).where(Chunk.project_id == project_id, ...)
```

## API Auth

`X-API-Key` required on all routes. SHA-256 hashed, stored in `api_keys`, scoped to `project_id`.
Exempt: `/`, `/docs`, `/openapi.json`, `/redoc`, `/health`
Missing/invalid key → 401. Valid → attached to `request.state.api_key`.

## Testing Conventions

| Fixture | Purpose |
|---|---|
| `test_engine` | Session-scoped; drops/recreates all tables |
| `db_session` | Function-scoped; rolls back after each test |
| `seeded_api_key` | Inserts `Project` + `APIKey` row; returns raw key string |
| `api_client` | Async HTTP client with `X-API-Key`; patches `api.middleware.AsyncSessionLocal` |
| `mock_embedder` | Returns zero vectors — no API call |

**Critical patterns:**
- Patch `api.middleware.AsyncSessionLocal` for any auth-gated route test
- Mock `_get_cached` + `_set_cached` in `run_query` unit tests (they attempt Redis connections)
- `stream=True` skips cache — no mock needed for streaming tests
- `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` decorators needed
- `asyncio_default_fixture_loop_scope = "session"` — session-scoped async fixtures share one event loop
