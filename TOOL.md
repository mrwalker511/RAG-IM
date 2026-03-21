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

*Entries are appended each time a tool decision is made. The goal is a running record that makes agent behavior transparent and auditable.*
