# Project Status

Updated at the end of every session. The next session reads this first.

---

## Current Branch

`claude/infrastructure-improvements-qwsX3`

## Last Session — 2026-03-21

**Completed:**
- Framework optimisation: slashed context overhead by ~60%
  - `CLAUDE.md` rewritten: 82 → 42 lines (lean, auto-loaded, zero waste)
  - `.claude/AGENTS.md` rewritten: 113 → 55 lines
  - `.claude/SKILLS.md` rewritten: 175 → 55 lines
  - `GUIDE.md` trimmed: removed 20-line redundant logging reminder
  - `TOOL.md` deleted (547 lines, zero remaining value)
- New session rule: update `STATUS.md` + `ERRORS.md` only if mistakes made. That's it.

**Prior session (2026-03-21):**
- Infrastructure hardening: configurable CORS, per-key rate limiting, pool sizing, Redis query cache
- Test suite overhaul: auth fixtures, middleware tests (7), Redis cache tests (11)

---

## In Progress

- PR open against `main` from `claude/infrastructure-improvements-qwsX3`

---

## Up Next

1. Merge infrastructure PR
2. Integration tests — full ingest → query → cache flow against live services
3. Document management endpoints — list + delete documents
4. Observability — structured JSON logs; warn-level log on Redis cache failure

---

## Known Gaps

| Gap | Location | Priority |
|---|---|---|
| No integration test for full ingest → query flow | `tests/integration/` | High |
| Rate limiter is in-process only — resets on restart | `api/middleware.py` | Medium |
| `CORS_ORIGINS=*` is the default — restrict before production | `ragcore/config.py` | High |
