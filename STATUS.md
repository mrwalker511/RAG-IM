# Project Status

Updated at the end of every session. The next session reads this first.

---

## Current Branch

`main`

## Last Session — 2026-03-22

**Completed:**
- Rebuilt clean `ragimdev` images so `python-multipart` is baked into the image again
- Fixed Docker upload handoff by moving temp files onto a shared `api`/`worker` volume
- Fixed ingestion failure handling so failed jobs persist `failed` status and clean up temp files
- Fixed async ingestion update path by deleting old chunks with SQL instead of lazy-loading `doc.chunks`
- Fixed vector search distance typing so queries no longer crash in pgvector result decoding
- Verified end-to-end smoke test against the live stack:
  - project `9b5628a1-a2ea-4900-a7dd-8a05dfcbd2d4`
  - API key `local-dev-key`
  - uploaded document `f6e5f8af-3182-4a72-8841-7669a223c479`
  - query answer returned `cobalt-hippo` with source attribution from `ragimdev-smoke-final.txt`
- Updated repo docs to match the current local dev stack and verified smoke path

---

## In Progress

- Working tree contains runtime fixes and documentation updates from the 2026-03-22 smoke-test session

---

## Up Next

1. Add an automated integration test for upload → ingest → query → cache
2. Investigate intermittent host-side `localhost:8000` failures from the shell
3. Improve observability around first-query model warmup and cache hits

---

## Known Gaps

| Gap | Location | Priority |
|---|---|---|
| No automated integration test for full ingest → query flow | `tests/integration/` | High |
| Host-side requests to `localhost:8000` can be intermittently unreachable even while Docker health checks pass | Local dev environment | Medium |
| First query after container restart is slow because SentenceTransformer warms on first use | Query path / model startup | Medium |
| Rate limiter is in-process only — resets on restart | `api/middleware.py` | Medium |
| `CORS_ORIGINS=*` is the default — restrict before production | `ragcore/config.py` | High |
