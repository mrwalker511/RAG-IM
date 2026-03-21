# RAG-IM — Claude Code Session Context

Production RAG framework: FastAPI + PostgreSQL/pgvector + Redis + ARQ workers.
Multi-project, per-project-isolated, async-first throughout.

---

## Branch Rule

Always develop on `claude/<description>-<sessionid>`. Never commit to `main` or `master`.
Push with: `git push -u origin claude/<branch>`

---

## Mandatory Logging — Every Session, Every Commit

All seven files must be current before any commit:

| File | Contains |
|---|---|
| `TOOL.md` | Every tool decision this session — what, why, correct? |
| `ERRORS.md` | Every mistake — one entry per error, root cause, correction |
| `GUIDE.md` | New prompting patterns, cost triggers, rule changes |
| `.claude/AGENTS.md` | New files, config settings, architectural rules |
| `.claude/SKILLS.md` | New system behaviors, implementation patterns, testing conventions |
| `README.md` | New env vars, architectural components |
| `testing.md` | New test files, fixture changes |
| `STATUS.md` | What was done this session; what's next |
| `DECISIONS.md` | Any new architectural decision made |

**One entry per error** in `ERRORS.md`. Never bundle distinct mistakes.

---

## Key Files

| File | Purpose |
|---|---|
| `ragcore/config.py` | All settings — check here before adding env vars |
| `ragcore/query/pipeline.py` | Query pipeline + Redis cache (`_get_cached`, `_set_cached`) |
| `api/middleware.py` | Auth (`api_key_middleware`) + rate limiting (`rate_limit_middleware`) |
| `ragcore/db/session.py` | SQLAlchemy engine (pool settings) |
| `ragcore/db/redis.py` | Shared Redis client + connection pool |
| `tests/conftest.py` | `seeded_api_key`, `api_client` (patches middleware, sends X-API-Key) |
| `GUIDE.md` | Strict prompt standards — read before prompting |
| `DECISIONS.md` | Why key choices were made — read before changing architecture |
| `STATUS.md` | What's in progress and what's next |

---

## Critical Rules

1. **Middleware bypasses DI.** `api.middleware.AsyncSessionLocal` must be patched in tests — `app.dependency_overrides` does not reach it.
2. **Redis errors are silent.** Cache helpers catch all exceptions. A Redis outage must never break queries.
3. **Tests ship with implementation.** New functions get tests in the same commit — never in a follow-up session.
4. **One task per prompt.** Bundled requests increase error rate and token cost.
5. **Read before Edit.** Always `Read` a file before calling `Edit` on it, even if it was read in a prior session.
6. **No force push.** Never push to `main`. Never use `--force` without explicit instruction.

---

## Testing Quick Reference

```bash
# Unit tests only (no services required)
pytest tests/unit/ -v

# All tests (requires Postgres + Redis + test_rag DB)
pytest tests/ -v

# With coverage
pytest tests/unit/ --cov=ragcore --cov=api --cov-report=term-missing
```

`asyncio_mode = "auto"` — `@pytest.mark.asyncio` decorators are not needed.

---

## Prompt Standards

See `GUIDE.md` for the full rule set. The one-line version:
> **Name the file and function. State the expected outcome. Say what not to change.**
