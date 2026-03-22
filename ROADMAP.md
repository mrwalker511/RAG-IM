# Roadmap

## Done

- Async ingestion for PDF, DOCX, Markdown, and text
- Hybrid retrieval with pgvector + BM25 + optional reranking
- Streaming and non-streaming query APIs
- Redis query cache
- Redis-backed shared rate limiting
- Bootstrap admin key plus project-scoped key enforcement
- Docker upload handoff via shared temp storage
- API, CLI, CI, Alembic, and smoke-tested local stack
- Integration coverage for ingest → query → cache

## Next

### 1. Observability

- Emit warning-level logs or metrics for Redis cache failures
- Add structured logs around ingestion, cache hits, and first-query warmup

### 2. Dev Reliability

- Investigate intermittent host-side `localhost:8000` failures
- Add a one-command smoke helper script instead of relying on copied shell snippets

### 3. Auth / Ops

- Add an explicit bootstrap-key rotation workflow
- Decide whether project creation should remain bootstrap-only or move behind a separate admin surface

## Deferred

| Item | Reason |
|---|---|
| JWT / OAuth | API keys are enough for the current deployment model |
| Per-project chunk config wiring | Config column exists, but chunker still uses global defaults |
| Event-driven BM25 rebuilds | Current lazy rebuild is simpler and acceptable |
| `unstructured` parser support | Current parser set covers the target formats without heavy native deps |
