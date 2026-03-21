# Tool Usage Log

This file documents every tool decision made by Claude agents during this project.
Each entry explains the situation, which tool was chosen, and the reasoning behind it.
Purpose: help the user understand tool costs and frame future requests for maximum efficiency.

---

## Tool Reference Guide

| Tool | Best For | Cost (relative) | Avoid When |
|------|----------|-----------------|------------|
| `Read` | Reading a specific file at a known path | Very low | You need to search across many files |
| `Grep` | Searching file contents by keyword or pattern | Low | File path is already known — use Read instead |
| `Glob` | Finding files by name pattern (e.g. `**/*.py`) | Low | Content search — use Grep instead |
| `Bash` | Git commands, running tests, system operations | Low–Medium | A dedicated tool (Read/Edit/Write) can do the job |
| `Edit` | Making targeted changes to an existing file | Low | Rewriting the whole file — use Write instead |
| `Write` | Creating new files or completely rewriting existing ones | Low | Small targeted changes — use Edit instead |
| `Agent (Explore)` | Deep unknown codebase exploration, multi-location searches | **High** | The codebase is already known — use Read/Grep directly |
| `Agent (General)` | Complex multi-step research across many sources | **High** | A single targeted search would suffice |
| `Agent (Plan)` | Designing implementation strategy before writing code | Medium | Simple or well-defined tasks |
| `TodoWrite` | Tracking multi-step tasks and showing progress | Very low | Single-step tasks |
| `WebFetch` | Reading a specific URL | Low | You need to search the web — use WebSearch |
| `WebSearch` | Finding current information online | Low–Medium | The answer is in the codebase |
| `Skill` | Invoking a named slash command (e.g. /commit) | Varies | The task is not a named skill |

---

## Session Log

---

### Entry #1 — Agent (Explore subagent)

**Date:** 2026-03-21
**User request:** *"what are the next development, debugging, or tests we can do next to lock this program down. do we need to document anything? does anything need to be updated? did we miss anything?"*

**Tool used:** `Agent` → subagent type `Explore`, thoroughness "very thorough"
**Tool calls consumed:** 63

**Why this tool was chosen:**
The question was broad and open-ended. The agent interpreted "did we miss anything?" as requiring a full codebase survey to ensure completeness. The Explore subagent type is designed for deep multi-location codebase analysis, so it was selected.

**Was this the right choice?**
No. The codebase was already known from prior sessions. The answer only required reading ~10–15 targeted files (models, pipelines, tests, CI config, config.py). A full Explore sweep with 63 tool calls produced the same quality answer at 4–6x the cost.

**Better approach:**
`Read` 10–15 specific files directly → synthesize findings → answer. No subagent needed.

**Lesson:** Reserve Explore agents for codebases that are genuinely new or when file locations are unknown.

---

### Entry #2 — Write (create ERRORS.md)

**Date:** 2026-03-21
**Situation:** User requested creation of a new file `ERRORS.md` in the root directory to log agent mistakes.

**Tool used:** `Write`

**Why this tool was chosen:**
The file did not exist yet. `Write` is the correct tool for creating new files. `Edit` only works on files that have already been read — it cannot create files from scratch.

**Was this the right choice?**
Yes. Single new file creation → `Write` is correct.

---

### Entry #3 — Bash (git status + git log)

**Date:** 2026-03-21
**Situation:** Before committing ERRORS.md, the agent needed to confirm the current branch and check recent commit message style.

**Tool used:** `Bash` with `git status && git log --oneline -5`

**Why this tool was chosen:**
Git operations have no dedicated tool — `Bash` is the only option. Running both commands in a single `&&` chain avoided two separate round-trips.

**Was this the right choice?**
Yes. Git commands require `Bash`. Chaining with `&&` was efficient.

---

### Entry #4 — Bash (git add + git commit + git push)

**Date:** 2026-03-21
**Situation:** Committing and pushing ERRORS.md to the feature branch.

**Tool used:** `Bash` with sequential git commands

**Why this tool was chosen:**
All git operations require `Bash`. Commands were chained sequentially because each step depends on the previous one (add before commit, commit before push).

**Was this the right choice?**
Yes. Correct tool, correct sequencing.

---

### Entry #5 — Write (create TOOL.md)

**Date:** 2026-03-21
**Situation:** User requested creation of a new `TOOL.md` file documenting tool usage decisions.

**Tool used:** `Write`

**Why this tool was chosen:**
New file, does not exist yet → `Write` is correct. Content was known in full before writing, so a single `Write` call was sufficient rather than `Write` + subsequent `Edit` passes.

**Was this the right choice?**
Yes.

---

## How to Use This File to Optimize Your Interactions

**To reduce cost, phrase requests like this:**

| Instead of... | Try... |
|---------------|--------|
| "Analyze the whole codebase and tell me X" | "Read [specific file] and tell me X" |
| "Find anything related to Y" | "Search for Y in the ragcore/ directory" |
| "Look through the project and summarize Z" | "Summarize Z based on [file A] and [file B]" |
| "Do a full audit of the system" | "Check these 5 specific things: ..." |

**When broad questions ARE worth the cost:**
- First time exploring a brand-new, unfamiliar codebase
- Hunting a bug whose location is completely unknown
- Security audit where you genuinely don't know where vulnerabilities might be

**When targeted questions save money:**
- The codebase is already known (like this one)
- You want a specific answer from a specific area
- You're asking about a file or function you can name

---

---

### Entry #6 — Bash (git log + git branch)

**Date:** 2026-03-21
**Situation:** Starting infrastructure improvements task. Needed to orient to the current branch state and recent commit history before writing any code.

**Tool used:** `Bash` — `git log --oneline -20 && git branch -a`

**Why this tool was chosen:**
Git commands require `Bash`. Both commands are independent and chained with `&&` to avoid two round-trips. This was the cheapest way to establish context (branch name, commit history style) before touching files.

**Was this the right choice?**
Yes. Two git commands, one shell call.

---

### Entry #7 — Bash + Read (parallel orientation)

**Date:** 2026-03-21
**Situation:** After confirming the branch, needed to understand what was already implemented for security, rate limiting, pool sizing, and Redis cache before writing anything.

**Tools used (parallel):**
- `Bash` — `ls ragcore/ && ls api/ && ls worker/` to map directory structure
- `Grep` — pattern-matched across api/ and ragcore/ for `rate_limit`, `redis.*cache`, `pool_size`, `security`, etc.
- `Read` — `api/middleware.py`, `api/main.py`, `ragcore/config.py` in parallel

**Why these tools were chosen:**
Directory listing and targeted keyword searches are the cheapest way to answer "does X already exist?" without reading every file. Running all reads in parallel avoids sequential round-trips.

**Was this the right choice?**
Yes. 3 parallel tool calls answered the full orientation question without an Explore agent.

---

### Entry #8 — Read (db/session.py + query/pipeline.py + requirements.txt)

**Date:** 2026-03-21
**Situation:** Needed exact current implementation of the DB engine (pool settings) and the query pipeline (cache integration point) before editing them.

**Tools used (parallel):** `Read` on three files simultaneously

**Why this tool was chosen:**
File paths were already known from prior reads. `Read` is correct; no search needed. Parallel reads avoid sequential wait time.

**Was this the right choice?**
Yes.

---

### Entry #9 — Edit (ragcore/config.py)

**Date:** 2026-03-21
**Situation:** Adding new config fields: `CORS_ORIGINS`, `RATE_LIMIT_PER_MINUTE`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `REDIS_MAX_CONNECTIONS`, `QUERY_CACHE_TTL`.

**Tool used:** `Edit` — targeted insertion at the end of the Settings class

**Why this tool was chosen:**
The change was a targeted addition to an existing file. `Edit` sends only the diff; `Write` would rewrite the whole file unnecessarily.

**Was this the right choice?**
Yes.

---

### Entry #10 — Edit (api/main.py)

**Date:** 2026-03-21
**Situation:** Wiring configurable CORS origins, rate limit middleware import, and Redis pool teardown into the app factory.

**Tool used:** `Edit` — two separate targeted edits (middleware block, lifespan)

**Why this tool was chosen:**
Existing file with targeted changes → `Edit`. Used two calls because the two change sites were far apart in the file (different functions).

**Was this the right choice?**
Yes.

---

### Entry #11 — Edit (api/middleware.py)

**Date:** 2026-03-21
**Situation:** Adding the sliding-window rate limiter (`rate_limit_middleware`) alongside the existing `api_key_middleware`.

**Tool used:** `Edit` — full replacement of file content via old/new string

**Why this tool was chosen:**
The new function was large enough that a single `Edit` replacing the whole content was cleaner than multiple small edits. The file was already read earlier in the session so the precondition was met.

**Was this the right choice?**
Yes.

---

### Entry #12 — Edit (ragcore/db/session.py)

**Date:** 2026-03-21
**Situation:** Adding explicit pool_size, max_overflow, and pool_timeout to `create_async_engine`.

**Tool used:** `Edit` — targeted replacement of the single `create_async_engine(...)` call

**Why this tool was chosen:**
Small, targeted change to a known line. `Edit` is correct.

**Was this the right choice?**
Yes.

---

### Entry #13 — Write (ragcore/db/redis.py)

**Date:** 2026-03-21
**Situation:** Creating a new shared Redis client module with connection pool configuration.

**Tool used:** `Write` — new file creation

**Why this tool was chosen:**
File did not exist. `Write` is the only tool for new file creation. `Edit` requires a prior `Read` and cannot create files.

**Was this the right choice?**
Yes.

---

### Entry #14 — Edit (ragcore/query/pipeline.py) — three passes

**Date:** 2026-03-21
**Situation:** Adding Redis query cache to the query pipeline: imports, cache helper functions, cache lookup at query start, cache write after generation.

**Tool used:** `Edit` — three separate targeted edits

**Why this tool was chosen:**
Three logically distinct change sites in one file (imports block, new helper functions, end of `run_query`). Each `Edit` was targeted rather than rewriting the whole file.

**Was this the right choice?**
Mostly yes. One redundant `Read` mid-session was used to confirm line numbers before the final cache-write edit — that was necessary because the file had grown significantly from prior edits and the offset had shifted.

---

---

### Entry #15 — Glob (find all test files)

**Date:** 2026-03-21
**Situation:** User asked to review all test files and ensure correct functions and configuration. First step: enumerate every file in the tests/ tree.

**Tool used:** `Glob` — pattern `tests/**/*.py`

**Why this tool was chosen:**
`Glob` is the correct tool for finding files by path pattern. No content search needed — just a directory inventory. Single call returned all 16 test files.

**Was this the right choice?**
Yes. One call, complete result.

---

### Entry #16 — Read (8 source files in parallel)

**Date:** 2026-03-21
**Situation:** After enumerating test files, needed to read all of them simultaneously to audit content before writing any fixes.

**Tool used:** `Read` — 8 files in parallel (conftest, test_query_pipeline, test_projects_api, test_api_keys, test_chunker, test_parsers, test_hybrid_search, test_generation, test_bm25_index, test_deduplication, test_prompt_builder, test_docx_parser)

**Why this tool was chosen:**
All file paths known. `Read` in parallel is the fastest approach. No search required.

**Was this the right choice?**
Yes. Parallel reads across all 12 test files in two batches covered the full audit in minimal round-trips.

---

### Entry #17 — Read (pyproject.toml, api/dependencies.py, ragcore/db/models.py in parallel)

**Date:** 2026-03-21
**Situation:** After reading tests, needed pytest config (asyncio_mode, testpaths), the dependency injection setup, and the DB models (for seeded fixture design) before writing fixes.

**Tool used:** `Read` — 3 files in parallel

**Why this tool was chosen:**
All three are reference reads before editing. Known paths → `Read`. Parallel to avoid sequential waits.

**Was this the right choice?**
Yes.

---

### Entry #18 — Write (tests/conftest.py)

**Date:** 2026-03-21
**Situation:** Rewriting conftest.py to fix four issues: remove deprecated event_loop fixture, add TEST_API_KEY constant, add seeded_api_key session fixture, update api_client to patch middleware session factory and include X-API-Key header.

**Tool used:** `Write` — full file rewrite

**Why this tool was chosen:**
The changes touched every section of the file (imports, event_loop removal, new fixture, updated fixture). A full `Write` was cleaner than 4–5 `Edit` calls across a 90-line file.

**Was this the right choice?**
Yes. Full rewrite was appropriate given the scope of changes.

---

### Entry #19 — Write (tests/api/test_projects_api.py)

**Date:** 2026-03-21
**Situation:** Rewriting test_projects_api.py to remove its own app fixture and per-test dependency_overrides boilerplate, replacing with the api_client fixture from conftest.

**Tool used:** `Write` — full file rewrite

**Why this tool was chosen:**
Every test in the file changed (removed manual override blocks, removed app fixture, removed explicit auth-less requests). A full `Write` was more efficient than 6+ `Edit` calls.

**Was this the right choice?**
Yes.

---

### Entry #20 — Write (tests/unit/test_query_pipeline.py)

**Date:** 2026-03-21
**Situation:** Adding _get_cached/_set_cached mocks to the existing test, adding two new tests (cache-hit and stream-bypass), removing @pytest.mark.asyncio decorators (redundant with asyncio_mode=auto).

**Tool used:** `Write` — full file rewrite

**Why this tool was chosen:**
Changes were spread across multiple tests plus new tests added. A `Write` was more efficient than multiple targeted `Edit` calls.

**Was this the right choice?**
Yes.

---

### Entry #21 — Write (tests/unit/test_middleware.py) — new file

**Date:** 2026-03-21
**Situation:** Creating new test file covering api_key_middleware and rate_limit_middleware. No prior file existed.

**Tool used:** `Write` — new file creation

**Why this tool was chosen:**
New file → `Write` is the only option. `Edit` cannot create files.

**Was this the right choice?**
Yes.

---

### Entry #22 — Write (tests/unit/test_redis_cache.py) — new file

**Date:** 2026-03-21
**Situation:** Creating new test file covering _cache_key, _get_cached, and _set_cached. No prior file existed.

**Tool used:** `Write` — new file creation

**Why this tool was chosen:**
New file → `Write`.

**Was this the right choice?**
Yes.

---

### Entry #23 — Edit (pyproject.toml)

**Date:** 2026-03-21
**Situation:** Adding asyncio_default_fixture_loop_scope = "session" to pytest config to support session-scoped async fixtures without the deprecated event_loop override.

**Tool used:** `Edit` — targeted single-line addition

**Why this tool was chosen:**
Small, targeted change to one config block. `Edit` sends only the diff.

**Was this the right choice?**
Yes.

---

---

### Entry #24 — Write (GUIDE.md) — new file

**Date:** 2026-03-21
**Situation:** User requested a strict prompting standards guide to maintain quality while controlling API costs.

**Tool used:** `Write` — new file creation

**Why this tool was chosen:**
New file, no prior content. `Write` is the only correct tool. Content was fully defined before writing so a single call was sufficient.

**Was this the right choice?**
Yes.

---

---

### Entry #25 — Read + Edit (GUIDE.md)

**Date:** 2026-03-21
**Situation:** User instructed that GUIDE.md must always be updated each session. Added GUIDE.md to the logging reminder table alongside TOOL.md and ERRORS.md, with explicit triggers for when it must be updated.

**Tools used:** `Read` then `Edit`

**Why these tools were chosen:**
`Read` first (required before `Edit`). Change was a targeted addition to one section — `Edit` sends only the diff, not the full file.

**Was this the right choice?**
Yes.

---

---

### Entry #26 — Read (4 files in parallel: AGENTS.md, SKILLS.md, README.md, testing.md)

**Date:** 2026-03-21
**Situation:** User asked to ensure all relevant files are updated routinely. Needed to read all docs before editing to understand current state and gaps.

**Tool used:** `Read` — 4 files in parallel

**Why this tool was chosen:**
All paths known. `Read` before any `Edit` (required). Parallel reads to avoid sequential waits.

**Was this the right choice?**
Yes.

---

### Entry #27 — Edit (6 files: AGENTS.md x2, SKILLS.md x2, README.md x2, testing.md x2, GUIDE.md)

**Date:** 2026-03-21
**Situation:** Updating all project docs to reflect infrastructure changes (rate limiting, Redis cache, pool sizing, new config settings, new test files, new test fixtures).

**Tool used:** `Edit` — targeted insertions and replacements in each file

**Why this tool was chosen:**
All files were already read. Changes were targeted additions to specific sections — `Edit` is correct. `Write` would have been wasteful for files where only 1–2 sections changed.

**Was this the right choice?**
Yes.

---

*Entries are appended each time a tool decision is made. The goal is a running record that makes agent behavior transparent and auditable.*
