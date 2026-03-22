# RAG Framework

Reusable FastAPI + PostgreSQL/pgvector + Redis RAG service with async document ingestion, hybrid retrieval, source attribution, and project isolation.

## What Ships

- Async document ingestion for PDF, DOCX, Markdown, and text
- pgvector + BM25 hybrid retrieval with optional reranking
- Streaming and non-streaming query endpoints
- Redis-backed query cache
- Redis-backed shared rate limiting
- Project-scoped API keys
- Env-driven bootstrap admin key for first-run project management
- Docker Compose, Alembic, CI, CLI, and test coverage

## Auth Model

- `BOOTSTRAP_API_KEY` is the admin key used to create and list projects.
- Project-scoped keys can only access their own project routes.
- Bootstrap access is meant for provisioning and operations, not normal app traffic.

## Quickstart

```bash
cp .env.example .env
# Set:
# - BOOTSTRAP_API_KEY
# - provider credentials
# - explicit CORS origins for your frontend

docker compose -p ragimdev up -d --build
docker compose -p ragimdev exec -T api alembic upgrade head
curl -sS http://localhost:8000/health
```

For the shortest end-to-end smoke test, use [testing.md](/home/matticus/code/RAG-IM/RAG-IM/testing.md).

## Local Dev Defaults

- Compose project: `ragimdev`
- Embeddings: `sentence_transformer` / `all-MiniLM-L6-v2` / `384` dims
- LLM: `litellm` / `mistral/mistral-small-latest`
- Upload handoff: shared temp volume via `UPLOAD_TMP_DIR=/shared-tmp`
- Health: `http://localhost:8000/health`

## Important Settings

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://rag:rag@localhost:5432/rag_db` | Async PostgreSQL URL |
| `REDIS_URL` | `redis://localhost:6379` | Queue, cache, and rate limiting |
| `BOOTSTRAP_PROJECT_NAME` | empty | Project auto-created for the bootstrap key |
| `BOOTSTRAP_API_KEY` | empty | Required for first-run project management |
| `BOOTSTRAP_API_KEY_LABEL` | `bootstrap` | Label stored with the seeded key |
| `EMBEDDING_PROVIDER` | `sentence_transformer` | `openai` or `sentence_transformer` |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Must match `EMBEDDING_DIM` |
| `EMBEDDING_DIM` | `384` | Guarded at startup for known models |
| `LLM_PROVIDER` | `openai` | `openai` or `litellm` |
| `LLM_MODEL` | `gpt-4o-mini` | Generator model |
| `UPLOAD_TMP_DIR` | `/tmp` | Compose overrides to `/shared-tmp` |
| `CORS_ORIGINS` | `*` | Set explicit origins outside dev |
| `RATE_LIMIT_PER_MINUTE` | `60` | Shared Redis-backed sliding window |
| `QUERY_CACHE_TTL` | `300` | `0` disables result caching |

## API Surface

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/projects` | Create project, bootstrap key only |
| `GET` | `/projects` | List projects, bootstrap key only |
| `GET` | `/projects/{id}` | Get project, matching project key or bootstrap |
| `DELETE` | `/projects/{id}` | Delete project, matching project key or bootstrap |
| `POST` | `/projects/{id}/api-keys` | Create project key |
| `GET` | `/projects/{id}/api-keys` | List project keys |
| `POST` | `/projects/{id}/documents` | Upload document |
| `GET` | `/projects/{id}/documents/{doc_id}/status` | Check ingestion status |
| `POST` | `/projects/{id}/query` | Query |
| `GET` | `/projects/{id}/query/stream?q=...` | SSE query |

OpenAPI docs are at `http://localhost:8000/docs`.

## CLI

```bash
export RAG_API_URL=http://localhost:8000
export RAG_API_KEY=<bootstrap-or-project-key>

python -m cli.main project list
python -m cli.main ingest run <project-name> ./docs
python -m cli.main query <project-name> "Summarize the documents"
```

## Development

```bash
pip install -r requirements-dev.txt

ruff check .
mypy ragcore api --ignore-missing-imports
pytest tests/unit -v
```

DB-backed suites need a reachable `TEST_DATABASE_URL`. In this workspace, Docker-internal smoke validation has been more reliable than host-side DB access.

## Deployment Notes

- Set a unique `BOOTSTRAP_API_KEY` before first startup.
- Rotate away from the bootstrap key for normal traffic by creating project-scoped keys.
- Set explicit `CORS_ORIGINS`.
- Run API and worker together so uploads can hand off through the shared temp directory.
- Expect slower first-query latency after restart when local transformer models warm up.
