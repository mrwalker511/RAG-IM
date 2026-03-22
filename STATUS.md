# Project Status

## Current Branch

`main`

## Last Session — 2026-03-22

### Completed

- Kept the graph-aware query work in place: explicit query modes, retrieval traces, eval payloads, and query logging
- Wired document deletion and ingestion to maintain derived state: graph links, BM25 indexes, and Redis query cache invalidation
- Refreshed top-level docs to match the current host defaults, query surface, and maintenance behavior
- Cleaned disposable local artifacts (`__pycache__`, `.pytest_cache`, `.ruff_cache`) from the workspace

### Validation

- `python -m compileall api ragcore tests` passed
- `./.venv/bin/pytest tests/unit -q` passed (`83 passed`)

### Still Open

- DB-backed `tests/api` and `tests/integration` were not re-run from this sandbox against a reachable `test_rag` database
- Host-side requests to `localhost:5433` still require local services that were not reachable from this sandbox during the last attempted run

## Known Gaps

| Gap | Location | Priority |
|---|---|---|
| DB-backed suites are not yet part of the local validation loop from this sandbox | Test environment | High |
| `CORS_ORIGINS=*` is still allowed by code defaults; safe deployment depends on explicit env config | `ragcore/config.py` / `.env` | High |
| Bootstrap key is intentionally high-privilege and should not be used for normal app traffic | Auth / ops | High |
| Cache failures still fall back silently beyond debug logging | Query/cache path | Medium |
| First query after restart is slower while the local embedding model warms up | Query path | Medium |
