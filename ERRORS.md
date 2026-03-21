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

*Entries are appended as mistakes are identified. Format: date, context, what happened, root cause, correction.*
