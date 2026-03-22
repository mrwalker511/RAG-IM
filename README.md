# RAG Framework

Reusable FastAPI + PostgreSQL/pgvector + Redis RAG service with async ingestion, hybrid retrieval, source attribution, and project isolation.

## Web Surfaces

- `/` — Control Room for project creation, uploads, and queries
- `/handbook` — browser view of the checked-in Markdown docs
- `/docs` — OpenAPI

## What Ships

- PDF, DOCX, Markdown, and text ingestion
- pgvector + BM25 retrieval with optional reranking
- Streaming and non-streaming query endpoints
- Redis-backed query cache
- Redis-backed shared rate limiting
- Bootstrap admin key plus project-scoped API keys
- Docker Compose stack with API, worker, Postgres, and Redis

## Auth Model

- `BOOTSTRAP_API_KEY` is the admin key for `POST /projects` and `GET /projects`.
- Project-scoped keys can only access routes under their own `/projects/{project_id}/...`.
- Bootstrap access is for provisioning and operations, not normal app traffic.

## Quickstart

```bash
cp .env.example .env
# Set:
# - BOOTSTRAP_API_KEY
# - provider credentials
# - explicit CORS_ORIGINS

docker compose -p ragimdev up -d --build
docker compose -p ragimdev exec -T api alembic upgrade head
curl -sS http://localhost:8000/health
```

Then open:

- `http://localhost:8000/`
- `http://localhost:8000/handbook`

## Local Defaults

| Setting | Value |
|---|---|
| Compose project | `ragimdev` |
| Embeddings | `sentence_transformer` + `all-MiniLM-L6-v2` |
| Embedding dimension | `384` |
| LLM example | `litellm` + `mistral/mistral-small-latest` |
| Shared upload dir in Compose | `/shared-tmp` |

## Important Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://rag:rag@localhost:5432/rag_db` | Compose overrides this inside containers |
| `REDIS_URL` | `redis://localhost:6379` | Queue, cache, and rate limiting |
| `BOOTSTRAP_PROJECT_NAME` | empty | Auto-created when bootstrap seeding runs |
| `BOOTSTRAP_API_KEY` | empty | Required for first-run provisioning |
| `BOOTSTRAP_API_KEY_LABEL` | `bootstrap` | Label stored with the seeded key |
| `UPLOAD_TMP_DIR` | `/tmp` | Compose overrides to `/shared-tmp` |
| `CORS_ORIGINS` | `*` | Set explicit origins outside local dev |
| `RATE_LIMIT_PER_MINUTE` | `60` | Shared Redis-backed sliding window |
| `QUERY_CACHE_TTL` | `300` | `0` disables result caching |

## API Surface

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/projects` | Create project, bootstrap key only |
| `GET` | `/projects` | List projects, bootstrap key only |
| `GET` | `/projects/{id}` | Get project |
| `DELETE` | `/projects/{id}` | Delete project |
| `POST` | `/projects/{id}/api-keys` | Create project key |
| `GET` | `/projects/{id}/api-keys` | List project keys |
| `POST` | `/projects/{id}/documents` | Upload document |
| `GET` | `/projects/{id}/documents` | List documents |
| `GET` | `/projects/{id}/documents/{doc_id}/status` | Check ingestion status |
| `POST` | `/projects/{id}/query` | Query |
| `GET` | `/projects/{id}/query/stream?q=...` | Stream query |

## Testing

- Fast path: see [testing.md](testing.md)
- Unit-only: `pytest tests/unit -v`
- DB-backed: create `test_rag`, then run `env TEST_DATABASE_URL=postgresql+asyncpg://rag:rag@localhost:5433/test_rag ./.venv/bin/pytest tests/api tests/integration -v`
- CI now runs `tests/unit`, then `tests/api` and `tests/integration` against the dedicated `postgres_test` service on port `5433`

If host-side `localhost:5433` or `localhost:8000` is unreliable in your shell, run the DB-backed tests or smoke commands from inside the `api` container instead.

## Deployment Notes

- Set a unique `BOOTSTRAP_API_KEY` before first boot.
- Create project-scoped keys and use those for normal application traffic.
- Set explicit `CORS_ORIGINS`.
- Run both `api` and `worker`; uploads depend on the shared temp directory handoff.
- Expect a slower first query after restart when the local embedding model warms up.

## Repo Docs

- [STATUS.md](STATUS.md) — current state and known gaps
- [ROADMAP.md](ROADMAP.md) — next work
- [DECISIONS.md](DECISIONS.md) — architecture choices
- [GUIDE.md](GUIDE.md) — prompting standards
- [ERRORS.md](ERRORS.md) — notable implementation mistakes
