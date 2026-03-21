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

## Error #4 — Tests written without accounting for new middleware

**Date:** 2026-03-21
**Session context:** Infrastructure improvements added `api_key_middleware` and `rate_limit_middleware` to the app. Existing tests were not updated to match.

### What happened
After adding auth middleware in the infrastructure session, the existing API test suite was not updated. Specifically:
- `conftest.py` `api_client` fixture sent no `X-API-Key` header — every request to a gated route would return 401
- `test_projects_api.py` had its own `app` fixture and per-test `dependency_overrides` with no auth header — same result
- `test_api_keys.py` relied on `api_client` — all 5 tests would 401
- `test_query_pipeline.py` did not mock `_get_cached`/`_set_cached` — tests silently relied on Redis being unavailable (cache fails silently) rather than proper isolation

### Root cause
Infrastructure changes (middleware, Redis cache) were implemented and pushed without simultaneously updating the test suite to reflect the new requirements. The middleware and cache were added in a session that was interrupted, and the test review was a separate session. The gap between implementation and test update allowed multiple test failures to accumulate.

### What should have been done
When middleware that gates all API requests is added, the test fixtures that exercise those routes must be updated in the same commit. Specifically:
1. The `api_client` fixture must include the `X-API-Key` header and patch the middleware session factory to use the test DB
2. Any new hot-path function (like `_get_cached`) must be mocked in existing unit tests that call the containing function

### Correction applied
- `conftest.py`: removed deprecated `event_loop` fixture, added `seeded_api_key` session fixture, updated `api_client` to patch `api.middleware.AsyncSessionLocal` and include `X-API-Key` header
- `test_projects_api.py`: removed manual override boilerplate, all tests now use `api_client`
- `test_query_pipeline.py`: `_get_cached` and `_set_cached` mocked in existing test; added cache-hit and stream-bypass tests
- New `test_middleware.py` and `test_redis_cache.py` added for new infrastructure coverage

---

*Entries are appended as mistakes are identified. Format: date, context, what happened, root cause, correction.*
