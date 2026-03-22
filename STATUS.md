# Project Status

Updated at the end of every session. The next session reads this first.

---

## Current Branch

`main`

## Last Session — 2026-03-22

**Completed:**
- Added env-driven bootstrap seeding: `BOOTSTRAP_PROJECT_NAME`, `BOOTSTRAP_API_KEY`, `BOOTSTRAP_API_KEY_LABEL`
- Tightened auth so project-scoped keys can only access their own project routes
- Reserved `/projects` create/list for the bootstrap key
- Replaced the in-process limiter with a Redis-backed shared sliding window
- Exempted `OPTIONS` requests from auth/rate limiting so CORS preflight works cleanly
- Added coverage for bootstrap seeding, project-scope auth, CORS preflight, and rate limiting
- Added an integration test for ingest → query → cache
- Rewrote `README.md` and compressed `testing.md` to a short deployment/smoke runbook

**Validation:**
- `pytest tests/unit/test_middleware.py -q` passed locally in the sandbox
- Live stack smoke test previously passed for upload → ingest → query under `ragimdev`
- DB-backed pytest could not be re-run end-to-end from this sandbox because neither configured test DB host was reachable

---

## Up Next

1. Re-run DB-backed `tests/api` and `tests/integration` from a reachable test DB host or inside a dev image with pytest installed
2. Investigate intermittent host-side `localhost:8000` failures from the shell
3. Improve observability around cache failures and first-query model warmup

---

## Known Gaps

| Gap | Location | Priority |
|---|---|---|
| Host-side requests to `localhost:8000` can be intermittently unreachable even while Docker health checks pass | Local dev environment | Medium |
| First query after container restart is slow because SentenceTransformer warms on first use | Query path / model startup | Medium |
| `CORS_ORIGINS=*` is still permitted by code defaults; deployment safety depends on explicit env config | `ragcore/config.py` / `.env` | High |
| Bootstrap key is intentionally high-privilege and should not be used for normal app traffic | Auth model / ops | High |
