# Roadmap

## Done

- Async ingestion for PDF, DOCX, Markdown, and text
- Hybrid retrieval with pgvector + BM25 + optional reranking
- Graph extraction plus `local`, `global`, and `mix` query modes
- Streaming and non-streaming query APIs
- Retrieval traces and eval payload generation for query responses
- Redis query cache
- Redis-backed shared rate limiting
- Index/cache maintenance on document ingest and delete
- Bootstrap admin key plus project-scoped key enforcement
- Shared upload handoff between API and worker
- Browser-based Control Room at `/`
- Browser-based docs handbook at `/handbook`
- Integration coverage for ingest -> query -> cache

## Next

1. Re-run `tests/api` and `tests/integration` against a reachable `test_rag` database from this workspace.
2. Add a one-command smoke helper so deployment verification does not depend on copied shell snippets.
3. Improve observability for cache failures, ingestion failures, and first-query warmup latency.
4. Add an operational bootstrap-key rotation workflow.

## Deferred

| Item | Reason |
|---|---|
| JWT / OAuth | API keys are sufficient for the current deployment model |
| Per-project chunk config wiring | Project config exists, but chunking still uses global defaults |
| Event-driven BM25 rebuilds | The current lazy rebuild is simpler and acceptable |
| `unstructured` parser support | Current parser set covers the target formats without heavy native deps |
