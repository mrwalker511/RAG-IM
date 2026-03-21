# RAG-IM

FastAPI + PostgreSQL/pgvector + Redis + ARQ. Multi-project, per-project-isolated, async-first.

## Branch

`llm/<description>-<sessionid>` — never `main`. Push: `git push -u origin llm/<branch>`

## Key Files

| File | Purpose |
|---|---|
| `ragcore/config.py` | All settings — check before adding env vars |
| `ragcore/query/pipeline.py` | Query pipeline + Redis cache (`_get_cached`, `_set_cached`) |
| `api/middleware.py` | Auth (`api_key_middleware`) + rate limiting (`rate_limit_middleware`) |
| `ragcore/db/session.py` | SQLAlchemy engine (pool settings) |
| `ragcore/db/redis.py` | Redis client + connection pool |
| `tests/conftest.py` | `seeded_api_key`, `api_client` (patches middleware, sends X-API-Key) |

## Critical Rules

1. **Middleware bypasses DI.** Patch `api.middleware.AsyncSessionLocal` in tests — `app.dependency_overrides` doesn't reach it.
2. **Redis errors are silent.** Cache helpers catch all exceptions. Redis outage must never break queries.
3. **Tests ship with implementation.** New functions get tests in the same commit.
4. **Read before Edit.** Always `Read` a file before `Edit`, even if read in a prior session.
5. **No force push.** Never push to `main`. Never `--force` without explicit instruction.

## Tests

```bash
pytest tests/unit/ -v                                                      # unit only (no services)
pytest tests/ -v                                                           # all (needs Postgres + Redis)
pytest tests/unit/ --cov=ragcore --cov=api --cov-report=term-missing
```

`asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed.

## Prompting

Name the file and function. State the expected outcome. Say what not to change.
Exact error text > paraphrase. One task per message. See `GUIDE.md` for templates.

## Session End

Update `STATUS.md`. Append `ERRORS.md` only if mistakes were made. That's it.
