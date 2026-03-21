# Roadmap

What's done, what's next, and what's deliberately deferred.

---

## Done

### Foundation (Phase 1–3)
- Project scaffold, DB models, Alembic migrations, Docker Compose
- Ingestion pipeline: parsers (PDF, DOCX, Markdown, text), chunker, deduplication, embeddings, ARQ worker
- Retrieval: vector search (pgvector), BM25, hybrid RRF, CrossEncoder reranker

### API & CLI (Phase 4–5)
- FastAPI routers: projects, documents, query, API keys
- API key auth middleware
- Typer CLI: project CRUD, ingest, query (streaming + non-streaming)
- Streaming SSE responses with source attribution

### Hardening (Phase 6)
- Local fallback embedder (SentenceTransformers)
- LiteLLM multi-provider LLM support
- GitHub Actions CI workflow
- 10-point audit fixes: migrations, tokens, providers, BM25 staleness, streaming, event loop, temp file, DOCX, CLI status, API keys

### Infrastructure (Current)
- Configurable CORS origins
- Per-API-key sliding-window rate limiting (in-process)
- SQLAlchemy + Redis connection pool sizing
- Redis query result cache with TTL
- Test suite overhaul: auth fixtures, middleware tests, Redis cache tests

### Project Scaffold
- `CLAUDE.md` auto-loaded session context
- `STATUS.md` session handoff
- `DECISIONS.md` architectural decisions log
- `GUIDE.md` strict prompt standards
- `TOOL.md` + `ERRORS.md` agent accountability logs
- `.pre-commit-config.yaml` code quality gates
- `.env.example` fully updated

---

## Up Next (prioritised)

### 1. Integration Tests
Full ingest → query → cache flow tested against live Postgres + Redis.
- Upload a document, wait for worker completion, run a query, assert answer + sources
- Verify cache hit on second identical query (latency drops, Redis has the key)
- Target: `tests/integration/`

### 2. CORS Hardening
- Set `CORS_ORIGINS` to an explicit origin list in staging/production env
- Add a test verifying CORS headers on OPTIONS preflight

### 3. Observability Improvements
- Structured JSON log output from ingestion and query pipelines (stdlib `logging` + JSON formatter)
- Emit a warning-level log event when Redis cache read/write fails (currently silent)

### 4. Document Management
- List documents per project endpoint
- Delete document endpoint (removes chunks, invalidates BM25 index)

---

## Deferred (deliberate)

| Feature | Reason deferred |
|---|---|
| Redis-backed rate limiting | Only needed for multi-worker deployment; current in-process approach is sufficient |
| JWT / OAuth authentication | API key auth covers current use case; JWT adds complexity without clear benefit yet |
| Per-project chunk size config | Config JSONB column exists on `projects` table but is not yet wired to the chunker |
| Async BM25 staleness invalidation | Currently lazy (rebuilt before next query); an event-driven rebuild (on ingest/delete) would reduce first-query latency |
| `unstructured` parser support | Heavy native deps; add only if a required format cannot be handled by current parsers |
| Multi-tenant auth (org-level keys) | Current model: one key per project. Org-level keys would require a new DB table and middleware change |

---

*Update this file when a feature moves from Up Next → Done, or when a new priority is identified.*
