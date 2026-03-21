# Agent Error Log

This file documents mistakes made by Claude agents during development of this project.
Each entry records the initial thought process, root cause, and correction applied.
Purpose: understand failure patterns to reduce cost and improve accuracy over time.

---

## Error #1 — Wasteful Subagent Delegation for Synthesis Question

**Date:** 2026-03-21
**Session context:** User asked: *"what are the next development, debugging, or tests we can do next to lock this program down. do we need to document anything? does anything need to be updated? did we miss anything?"*

### What happened
The agent launched a full `Explore` subagent with thoroughness level "very thorough" to re-scan the entire codebase before answering. The subagent executed **63 tool calls** (file reads, greps, globs across every directory) before returning a report. The main agent then synthesized that report into the final response.

### Initial thought process (why the agent made this choice)
The question was broad and open-ended ("did we miss anything?"), which triggered a conservative instinct to do a complete survey before answering. The agent assumed that without a full codebase scan it might miss something important, so it defaulted to maximum thoroughness.

### Why this caused the error
The codebase was already loaded in context from prior sessions, and the project structure is well-defined (known files, known architecture). A synthesis question about "what to do next" does not require re-reading every source file from scratch. The correct approach was to:
1. Read 10–15 key files directly (models, pipelines, tests, config, CI)
2. Note gaps and inconsistencies
3. Answer from that targeted read

Using a "very thorough" Explore agent multiplied the token cost by roughly 4–6x versus direct file reads, with no improvement in answer quality. This directly increases the user's API costs without benefit.

### What should have been done
- Use `Read`, `Grep`, and `Glob` directly on specific files
- Reserve `Explore` subagents for genuinely unknown codebases or open-ended searches where file locations are not predictable
- For synthesis questions on a known repo, a targeted 10–15 file read is sufficient

### Correction applied
Acknowledged the mistake to the user. Created this log file. Going forward, subagent delegation will be reserved for cases where the codebase is unfamiliar, the file locations are unknown, or the search space genuinely requires many parallel lookups.

---

---

## Error #2 — Cache write missing from query pipeline

**Date:** 2026-03-21
**Session context:** Implementing Redis query cache as part of infrastructure improvements.

### What happened
The cache lookup (`_get_cached`) was wired into `run_query` at the start of the function. The cache write (`_set_cached`) after generation was never added — the session was interrupted before that step completed. The function would return results without ever populating the cache.

### Initial thought process (why the agent made this mistake)
The implementation was interrupted mid-task. After adding the helpers and the lookup, the agent context-switched to TOOL.md logging before completing the write-back. The missing second half of the cache contract was left out.

### Why this caused the error
Without `_set_cached`, the cache key is checked on every request but never written. Every query pays the full DB + LLM cost on every call with zero cache benefit, while appearing to have caching configured. Silent permanent cache miss.

### What should have been done
Complete both sides of the cache contract (read + write) in the same edit pass before context-switching to any other task. When `_get_cached` is added at the top of a function, the matching `_set_cached` at the bottom must be added in the same sitting.

### Correction applied
User flagged the omission. Added `await _set_cached(cache_key, query_result)` immediately before `return query_result` in `ragcore/query/pipeline.py`.

---

---

## Error #3 — Edit attempted on unread file

**Date:** 2026-03-21
**Session context:** Updating ERRORS.md to log error #2 during the infrastructure improvements session.

### What happened
The agent called `Edit` on `ERRORS.md` without having called `Read` on it first in the same session. The tool rejected the call with: `File has not been read yet. Read it first before writing to it.`

### Initial thought process (why the agent made this mistake)
The agent had read ERRORS.md in a prior session and treated that as sufficient. When context switches between sessions, prior reads do not carry over — the tool requires a fresh `Read` in the current session before any `Edit` is permitted.

### Why this caused the error
`Edit` enforces a read-before-write contract per session to prevent blind overwrites. Skipping the `Read` caused the call to fail, adding an unnecessary round-trip.

### What should have been done
Always `Read` a file before calling `Edit` on it, even if the file's contents are known from prior sessions or earlier context.

### Correction applied
Called `Read` on `ERRORS.md` immediately, then re-issued the `Edit` successfully.

---

---

## Error #4 — api_client fixture missing X-API-Key header

**Date:** 2026-03-21
**Session context:** `api_key_middleware` was added to the app factory in the infrastructure session. The `api_client` fixture in `conftest.py` was not updated.

### What happened
The `api_client` fixture in `conftest.py` sent no `X-API-Key` header. Every request to a non-exempt route returned 401. All tests in `test_api_keys.py` (5 tests) and `test_projects_api.py` (3 tests) would fail silently with wrong status codes rather than meaningful assertion errors.

### Root cause
Middleware was added in a separate session from the test review. The fixture was not updated at the same time as the middleware implementation.

### What should have been done
When auth middleware is added to `create_app()`, the `api_client` fixture must be updated in the same commit — seed a valid API key in the test DB and include the header on every request.

### Correction applied
Added `seeded_api_key` session fixture (inserts real `Project`+`APIKey` row into test DB). Updated `api_client` to include `headers={"X-API-Key": seeded_api_key}`.

---

## Error #5 — api_client middleware hitting production DB instead of test DB

**Date:** 2026-03-21
**Session context:** Same session as error #4. Even with an X-API-Key header added, `api_key_middleware` uses `AsyncSessionLocal` directly — hardcoded to `settings.DATABASE_URL` — not the test DB engine wired through `get_db_session` dependency overrides.

### What happened
`api_key_middleware` performs its own DB lookup via `AsyncSessionLocal()`. The test `api_client` fixture only overrides the `get_db_session` FastAPI dependency, which the middleware bypasses. Even with a seeded test API key, the auth check would hit the production/configured DB and return 401.

### Root cause
The middleware was implemented using a direct `AsyncSessionLocal` import rather than the dependency injection system. This is a valid design choice for middleware, but it creates a testing gap: DI overrides don't reach the middleware layer.

### What should have been done
The `api_client` fixture must patch `api.middleware.AsyncSessionLocal` with the test engine's session factory so the middleware's DB lookup resolves against the test DB.

### Correction applied
Added `with patch("api.middleware.AsyncSessionLocal", factory):` wrapping the `AsyncClient` context in the `api_client` fixture.

---

## Error #6 — Deprecated event_loop fixture left in conftest

**Date:** 2026-03-21
**Session context:** `pyproject.toml` had `asyncio_mode = "auto"` configured since Phase 5. The `event_loop` fixture override in `conftest.py` is deprecated with this mode in pytest-asyncio ≥0.21 and causes warnings or failures depending on version.

### What happened
The `conftest.py` defined a `scope="session"` `event_loop` fixture. With `asyncio_mode = "auto"`, pytest-asyncio manages the event loop itself. The manual override conflicts with this and is flagged as deprecated, potentially causing test collection warnings or hard failures on newer library versions.

### Root cause
The `event_loop` fixture was added in an earlier phase when manual loop management was needed. When `asyncio_mode = "auto"` was added to `pyproject.toml`, the fixture was not removed.

### What should have been done
Remove the `event_loop` fixture when `asyncio_mode = "auto"` is set. Add `asyncio_default_fixture_loop_scope = "session"` to `pyproject.toml` so session-scoped async fixtures share the correct event loop.

### Correction applied
Removed `event_loop` fixture from `conftest.py`. Added `asyncio_default_fixture_loop_scope = "session"` to `pyproject.toml`.

---

## Error #7 — _get_cached and _set_cached not mocked in query pipeline test

**Date:** 2026-03-21
**Session context:** Redis query cache was added to `run_query` in the infrastructure session. `test_run_query_returns_result_with_tokens` was not updated.

### What happened
`run_query` now calls `_get_cached` at entry and `_set_cached` after generation. The test did not mock either. With `QUERY_CACHE_TTL=300` (default), `_get_cached` tries to connect to Redis. The `try/except` in the helper swallows the connection error and returns `None`, so the test accidentally passes when Redis is down — but would produce a different execution path if Redis is up. The test outcome depended on external infrastructure state rather than controlled mocks.

### Root cause
Cache helpers were added to `run_query` without updating the unit test that exercises that function. The silent failure mode of the helpers masked the gap.

### What should have been done
Any time a function under test gains a new dependency (Redis, DB, external API), that dependency must be mocked in the existing unit tests. The pattern is: add helper → immediately update all tests that call the containing function.

### Correction applied
Added `patch("ragcore.query.pipeline._get_cached", new=AsyncMock(return_value=None))` and `patch("ragcore.query.pipeline._set_cached", new=AsyncMock())` to `test_run_query_returns_result_with_tokens`. Added explicit tests for cache-hit and stream-bypass behavior.

---

## Error #8 — No test coverage added for new infrastructure in the same session it was written

**Date:** 2026-03-21
**Session context:** Infrastructure session added rate limiting, CORS hardening, pool sizing, Redis cache. No tests were added.

### What happened
The entire infrastructure improvement session produced zero new tests. `rate_limit_middleware`, `_get_cached`, `_set_cached`, and `_cache_key` were all shipped with no unit coverage. The test review session (separate) had to reconstruct intent and write coverage retroactively.

### Root cause
Implementation and testing were treated as separate phases rather than simultaneous work. The infrastructure session was also interrupted mid-task, which reduced the chance of looping back to add tests.

### What should have been done
New functions (especially middleware and cache helpers) should have tests written in the same commit. At minimum: one happy-path test and one failure/edge-case test per new function, in the same session.

### Correction applied
Added `tests/unit/test_middleware.py` (7 tests) and `tests/unit/test_redis_cache.py` (11 tests) in the follow-up test review session.

---

*Entries are appended as mistakes are identified. Format: date, context, what happened, root cause, correction.*
