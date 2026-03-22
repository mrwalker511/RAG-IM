# RAG-IM

FastAPI + PostgreSQL/pgvector + Redis + ARQ. Multi-project, async-first, project-isolated.

## Key Files

| File | Purpose |
|---|---|
| `api/main.py` | App factory, root UI, and handbook pages |
| `api/middleware.py` | Auth and rate limiting |
| `ragcore/bootstrap.py` | Bootstrap project and key seeding |
| `ragcore/config.py` | All settings |
| `ragcore/query/pipeline.py` | Query flow and Redis cache |
| `tests/conftest.py` | Test DB fixtures and auth patching |

## Critical Rules

1. Middleware auth bypasses FastAPI DI; patch `api.middleware.AsyncSessionLocal` in tests.
2. `BOOTSTRAP_API_KEY` is special; `/projects` create/list is bootstrap-only.
3. Project-scoped keys must never cross project boundaries.
4. Cache and rate-limit Redis failures should not take the API down.
5. New behavior ships with tests in the same change.
6. Update `STATUS.md` at the end of a work session.

## Validation

```bash
pytest tests/unit -v
env TEST_DATABASE_URL=... pytest tests/api tests/integration -v
python -m compileall api ragcore tests
```

## Browser Surfaces

- `/` — Control Room
- `/handbook` — Markdown docs browser
- `/docs` — OpenAPI

## Prompting

Name the file, function, or route. Include the expected result. Include exact error text when debugging. For doc work, name the Markdown files explicitly.
