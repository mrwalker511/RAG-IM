# Prompt Standards Guide

Strict rules for prompting Claude agents on this project.
Purpose: maximum quality at minimum token cost. Every wasted token is real money.

---

## The Core Rule

**Be specific. Name the file, the function, the behavior. Never ask broadly when you can ask narrowly.**

Vague prompts force the agent to scan the entire codebase to avoid missing something.
Specific prompts let it go directly to the right file and answer immediately.

---

## Prompt Rules

### 1. Name the file or module when you know it
| Instead of | Use |
|---|---|
| "Fix the bug in the query system" | "Fix the bug in `ragcore/query/pipeline.py` — `run_query` returns stale cache on TTL=0" |
| "Update the config" | "Add `MAX_RETRIES` to `ragcore/config.py` Settings class" |
| "Check the tests" | "Check `tests/unit/test_query_pipeline.py` — does it mock `_get_cached`?" |

### 2. State the expected outcome, not just the problem
| Instead of | Use |
|---|---|
| "The API is broken" | "POST /projects returns 401 — I'm sending X-API-Key but it's still rejected" |
| "Something is wrong with chunking" | "`chunk_texts` in `ragcore/ingestion/chunker.py` returns empty list on 200-word input" |

### 3. Scope the task explicitly
| Instead of | Use |
|---|---|
| "Clean up the tests" | "In `tests/unit/test_generation.py` — remove redundant assertions in the LiteLLM tests only" |
| "Improve the middleware" | "Add request logging to `api/middleware.py` — log method, path, and status code only" |

### 4. Separate multiple requests into separate messages
One task per message. Bundling tasks forces the agent to track multiple threads simultaneously, increasing error rate and token usage.

**Bad:** "Fix the rate limiter, add a new test for it, and update the README."
**Good:** Three separate messages, one per task.

### 5. Reference errors by exact text
When reporting a failure, paste the exact error line — not a paraphrase.

**Bad:** "The test is failing with some Redis error."
**Good:** "Test failing: `ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 6379)` in `test_redis_cache.py::test_get_cached_returns_none_on_cache_miss`"

### 6. Say what NOT to change
Prevents the agent from refactoring code adjacent to the target.

**Example:** "Update `_ensure_bm25_index` in `ragcore/query/pipeline.py` to log the stale threshold value. Do not change any other function."

### 7. For reviews, specify what to look for
| Instead of | Use |
|---|---|
| "Review the code" | "Review `api/middleware.py` for race conditions in `_rate_windows`" |
| "Is anything missing?" | "Does `tests/unit/test_middleware.py` cover the case where `RATE_LIMIT_PER_MINUTE=0`?" |

### 8. For new features, specify inputs, outputs, and constraints up front
Include: what function/file, what it takes in, what it returns, any constraints (no new dependencies, must be async, etc.).

**Example:** "Add a `clear_query_cache(project_id)` function to `ragcore/query/pipeline.py`. Takes a `uuid.UUID`. Deletes all Redis keys matching `query_cache:*` for that project. Async. No new imports beyond what's already in the file."

---

## What Triggers High Cost (avoid these)

| Pattern | Why it's expensive | What to do instead |
|---|---|---|
| "Did we miss anything?" | Forces a full codebase scan | Ask about a specific area: "Did we miss error handling in `ragcore/ingestion/pipeline.py`?" |
| "Analyze the whole project and tell me X" | Launches Explore subagent (50–100 tool calls) | "Read `ragcore/config.py` and tell me X" |
| "What's the best approach?" without context | Agent reads many files to establish context | Provide the relevant file paths and current behavior up front |
| Open-ended debugging without an error message | Agent guesses, reads widely, over-investigates | Always include the exact error, file, and line number |
| "Refactor X" without boundaries | Agent rewrites adjacent code unnecessarily | State exactly which function and what aspect to change |

---

## What Keeps Cost Low Without Losing Quality

- **The codebase is already known.** The agent doesn't need to re-read everything on every message. Name the target and it goes directly there.
- **One task = one message.** Keeps context tight, reduces error recovery.
- **Exact error text > paraphrase.** Eliminates the investigation phase.
- **"Only change X, leave Y alone."** Prevents unnecessary edits that add review burden.
- **"In `<file>`" anywhere in the prompt** cuts tool calls by 3–5x compared to a search-first approach.

---

## Template for Common Request Types

### Bug fix
```
Bug in `<file>` — `<function>`: <exact error or wrong behavior>.
Expected: <what should happen>.
Do not change <anything else>.
```

### New feature
```
Add `<function_name>` to `<file>`.
Input: <params and types>.
Output: <return type and value>.
Constraints: <async/sync, no new deps, etc.>.
```

### Test gap
```
`<test_file>` is missing a test for `<behavior>`.
The function under test is `<function>` in `<source_file>`.
Add the test. Do not modify existing tests.
```

### Review
```
Review `<file>` for <specific concern: race conditions / missing error handling / incorrect mock / etc.>.
Report findings only — do not make changes unless I confirm.
```

### Config/infra change
```
In `<file>`, change `<setting>` from <old> to <new>.
Reason: <one sentence>.
Update any tests that depend on the old value.
```

---

*Quality and cost are not opposites — they become opposites only when prompts are imprecise.*
