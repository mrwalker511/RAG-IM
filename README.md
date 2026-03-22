# RAG Framework

A production-grade, reusable Retrieval-Augmented Generation (RAG) framework. Each project gets its own isolated namespace within a shared PostgreSQL + pgvector database.

## Features

- **Document ingestion**: PDF, DOCX, Markdown, plain text
- **Pluggable chunking**: fixed-size and recursive strategies with token-limit guard
- **Pluggable embedders**: OpenAI (default) or SentenceTransformers (local, no API key)
- **Hybrid search**: pgvector cosine similarity + BM25, fused via Reciprocal Rank Fusion
- **CrossEncoder re-ranking** of top candidates
- **LLM answer synthesis** with source attribution (document, chunk index)
- **Streaming responses** via SSE
- **Async ingestion** via ARQ + Redis — uploads never block HTTP requests
- **SHA-256 deduplication** — unchanged documents are skipped on re-ingest
- **Per-project isolation** — every query is scoped by `project_id`
- **API key auth** per project
- **Alembic migrations**, **Docker Compose**, **GitHub Actions CI**

## Stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.11+ |
| API | FastAPI |
| Database | PostgreSQL 16 + pgvector |
| ORM | SQLAlchemy 2.x (async) + asyncpg |
| Migrations | Alembic |
| Task queue | ARQ + Redis |
| Embeddings | OpenAI / SentenceTransformers |
| LLM | OpenAI (default) + LiteLLM |
| Parsing | pypdf, python-docx, markdown-it-py |
| CLI | Typer + Rich |

## Quickstart

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — set OPENAI_API_KEY at minimum

# 2. Start services
docker compose up -d

# 3. Run migrations
docker compose exec api alembic upgrade head

# 4. Install CLI locally
pip install -r requirements.txt
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://rag:rag@localhost:5433/rag_db` | Async PostgreSQL URL |
| `REDIS_URL` | `redis://localhost:6379` | Redis for ARQ task queue |
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `sentence_transformer` |
| `OPENAI_API_KEY` | — | Required for OpenAI embeddings and LLM |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model name |
| `EMBEDDING_DIM` | `1536` | Embedding vector dimension |
| `LLM_PROVIDER` | `openai` | `openai` or `litellm` |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model name |
| `DEFAULT_CHUNK_SIZE` | `512` | Default chunk size in tokens |
| `DEFAULT_CHUNK_OVERLAP` | `64` | Default chunk overlap in tokens |
| `DEFAULT_TOP_K` | `5` | Default retrieval top-k |
| `RERANK_TOP_N` | `20` | Candidates sent to CrossEncoder |
| `BM25_STALE_AFTER_MINUTES` | `60` | BM25 index rebuild threshold |
| `API_HOST` | `0.0.0.0` | API bind host |
| `API_PORT` | `8000` | API bind port |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins; restrict in production |
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-API-key sliding-window rate limit; `0` = disabled |
| `DB_POOL_SIZE` | `10` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Max connections above pool size |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait for a DB connection |
| `REDIS_MAX_CONNECTIONS` | `20` | Redis connection pool cap |
| `QUERY_CACHE_TTL` | `300` | Query result cache TTL in seconds; `0` = disabled |

## CLI Usage

```bash
# Set API key if auth is enabled
export RAG_API_KEY=your-key
export RAG_API_URL=http://localhost:8000

# Projects
rag project create "my-project"
rag project list
rag project delete "my-project"

# Ingest
rag ingest run my-project ./docs/
rag ingest status <job_id>

# Query
rag query my-project "Summarize the key points in these documents."
rag query my-project "What does section 3 cover?" --top-k 10 --stream
```

Run the CLI directly:
```bash
python -m cli.main --help
```

## API

OpenAPI docs available at `http://localhost:8000/docs` after starting the server.

Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/projects` | Create project |
| `GET` | `/projects` | List projects |
| `DELETE` | `/projects/{id}` | Delete project |
| `POST` | `/projects/{id}/documents` | Upload document (async) |
| `GET` | `/projects/{id}/documents/{doc_id}/status` | Ingestion status |
| `POST` | `/projects/{id}/query` | Query (non-streaming) |
| `GET` | `/projects/{id}/query/stream?q=...` | Query (SSE streaming) |

## Architecture

```
ragcore/
├── config.py          # Pydantic Settings — all env vars
├── db/
│   ├── models.py      # ORM: Project, Document, Chunk, BM25Index, QueryLog, APIKey
│   └── session.py     # Async engine + session factory
├── projects/          # Project CRUD service + schemas
├── ingestion/         # parse → dedup → chunk → embed → store
│   ├── parsers/       # BaseParser + PDF/DOCX/Markdown/Text
│   ├── chunker.py     # Fixed + recursive, token-limit guard
│   └── worker.py      # ARQ task definition
├── embeddings/        # BaseEmbedder + OpenAI + SentenceTransformer
├── retrieval/         # vector_search, bm25_search, hybrid RRF, reranker
├── generation/        # BaseLLMGenerator + OpenAI + LiteLLM
├── query/             # End-to-end query pipeline (includes Redis result cache)
└── observability/     # Async query event logger
```

## Development

```bash
pip install -r requirements-dev.txt

# Lint
ruff check .

# Type check
mypy ragcore api --ignore-missing-imports

# Test (unit only, no DB required)
pytest tests/unit -v

# Test with coverage
pytest tests/unit --cov=ragcore --cov=api --cov-report=term-missing
```

## Adding a New Embedding Provider

1. Create `ragcore/embeddings/my_embedder.py`, subclass `BaseEmbedder`
2. Implement `embed()` and `dimension`
3. Add the provider name to `EMBEDDING_PROVIDER` choices in `config.py`
4. Wire it in the factory used by the query pipeline

Same pattern applies for LLM providers via `BaseLLMGenerator`.
