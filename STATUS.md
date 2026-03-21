# Project Status

Updated at the end of every session. The next session reads this first.

---

## Current Branch

`claude/infrastructure-improvements-qwsX3`

## Last Session — 2026-03-21

**Completed:**
- Infrastructure hardening: configurable CORS, per-key sliding-window rate limiter, SQLAlchemy + Redis connection pool sizing, Redis query result cache with TTL
- Test suite overhaul: fixed auth failures in all API tests (seeded API key, middleware patched to test DB), added `test_middleware.py` (7 tests) and `test_redis_cache.py` (11 tests), mocked cache helpers in query pipeline tests
- Project docs fully synced: `AGENTS.md`, `SKILLS.md`, `README.md`, `testing.md`, `GUIDE.md`, `ERRORS.md`, `TOOL.md`
- Session scaffold files created: `CLAUDE.md`, `STATUS.md`, `DECISIONS.md`, `ROADMAP.md`, `.pre-commit-config.yaml`, `.env.example` updated

**Errors logged:** #2–8 in `ERRORS.md`

---

## In Progress

- PR open against `main` from `claude/infrastructure-improvements-qwsX3`
- Pre-commit hooks added but not yet installed locally (`pre-commit install`)

---

## Up Next

1. Merge infrastructure PR
2. Integration tests — full ingest → query → cache flow against live services
3. Tighten CORS in staging: set `CORS_ORIGINS` to explicit origin list
4. Consider Redis-backed rate limiting if multi-worker deployment is needed (see `DECISIONS.md`)

---

## Known Gaps

| Gap | Location | Priority |
|---|---|---|
| No integration test for full ingest → query flow | `tests/integration/` | High |
| Rate limiter is in-process only — resets on restart | `api/middleware.py` | Medium |
| `CORS_ORIGINS=*` is the default — must be restricted before production | `ragcore/config.py` | High |
| No test for CORS header behavior | `tests/` | Low |
