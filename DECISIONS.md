# Architectural Decisions

Each entry explains a key choice, why it was made, and what would trigger revisiting it.
Read this before changing any of the systems described here.

---

## 001 — In-process rate limiting (not Redis-backed)

**Decision:** `rate_limit_middleware` uses an in-process `defaultdict(deque)` keyed by API key hash.

**Why:**
- Zero additional infrastructure — Redis is already used for the task queue and query cache, but adding rate limit state there adds latency on every request
- Acceptable for single-worker deployments
- State resets on restart, which is acceptable for a per-minute sliding window

**Trade-off:** In a multi-worker deployment, each worker tracks its own window independently — a client could make `N * workers` requests per minute before being limited.

**Revisit when:** Multi-worker deployment is needed. Switch to Redis sorted sets (`ZRANGEBYSCORE` + `ZADD` + `EXPIRE`) for a shared window.

---

## 002 — Middleware uses AsyncSessionLocal directly (not DI)

**Decision:** `api_key_middleware` and `rate_limit_middleware` import `AsyncSessionLocal` directly from `ragcore.db.session` rather than using FastAPI's dependency injection.

**Why:**
- FastAPI middleware runs outside the DI graph — route-level dependencies are not available in middleware
- Using `Depends()` in middleware is not supported by FastAPI's middleware protocol
- The alternative (converting auth to a route dependency) would require decorating every router individually

**Trade-off:** Tests must patch `api.middleware.AsyncSessionLocal` rather than using `app.dependency_overrides`. This is documented in `conftest.py`, `AGENTS.md`, and `SKILLS.md`.

**Revisit when:** If a cleaner pattern (e.g., a FastAPI security dependency applied globally via a router) is adopted.

---

## 003 — Redis cache fails silently on errors

**Decision:** `_get_cached` and `_set_cached` in `ragcore/query/pipeline.py` catch all exceptions and return `None` / continue without raising.

**Why:**
- A Redis outage must not degrade query availability — cache is an optimization, not a requirement
- Silent failure means the system gracefully degrades to uncached behavior

**Trade-off:** Cache errors are only visible in debug logs — a persistent Redis failure will go unnoticed without monitoring.

**Revisit when:** Observability tooling is added. Consider emitting a metric or structured log event on cache failure rather than silently passing.

---

## 004 — ARQ for background ingestion (not FastAPI BackgroundTasks)

**Decision:** Document ingestion is queued via ARQ (Redis-backed task queue), not FastAPI's built-in `BackgroundTasks`.

**Why:**
- `BackgroundTasks` run in the same process as the API server — a slow or failing ingestion blocks the worker thread pool and can crash the API under load
- ARQ provides retry logic, task status tracking, and worker isolation
- Ingest jobs can be monitored via job ID returned to the client

**Revisit when:** ARQ adds operational overhead that isn't justified (e.g., very small deployments with tiny documents).

---

## 005 — pypdf / python-docx / markdown-it-py (not `unstructured`)

**Decision:** Document parsers use lightweight, pure-Python libraries.

**Why:**
- `unstructured` pulls in heavy native dependencies (tesseract, libmagic, poppler) that significantly bloat the Docker image and complicate CI
- The supported formats (PDF, DOCX, Markdown, plain text) cover the vast majority of use cases
- Each parser is a small, testable class implementing `BaseParser`

**Revisit when:** A new format is needed that these libraries cannot handle (e.g., PowerPoint, Excel, HTML with complex layout).

---

## 006 — Hybrid search with RRF (not pure vector or pure BM25)

**Decision:** Retrieval combines pgvector cosine similarity and BM25 via Reciprocal Rank Fusion, with optional CrossEncoder re-ranking.

**Why:**
- Pure vector search misses exact keyword matches (e.g., product codes, names, acronyms)
- Pure BM25 misses semantic similarity
- RRF is parameter-free (no score normalization needed) and consistently outperforms individual methods
- CrossEncoder re-ranking is optional and adds latency — disabled by default

**Revisit when:** Retrieval quality metrics indicate one method consistently dominates; or if latency constraints make hybrid retrieval untenable.

---

## 007 — Per-project isolation via project_id scoping

**Decision:** Every DB query across documents, chunks, BM25 indexes, query logs, and API keys filters by `project_id`.

**Why:**
- The framework is designed for multi-tenant use — multiple independent projects share one DB
- Row-level isolation by `project_id` is simpler and more performant than separate schemas or databases per project
- All queries are indexed on `project_id`

**Revisit when:** A project requires strict data residency or regulatory isolation that row-level scoping cannot guarantee.

---

## 008 — SHA-256 deduplication on content hash

**Decision:** Documents are deduplicated by `sha256(file_bytes)` before ingestion.

**Why:**
- Prevents re-embedding identical documents on re-upload (expensive API call)
- Hash is computed before parsing, so it's format-agnostic
- 64-char hex string stored in `documents.content_hash` with a unique index

**Revisit when:** Partial document updates are needed (e.g., re-ingest only changed pages). Would require a chunk-level hash strategy.

---

*Add a new entry whenever a non-obvious architectural choice is made. Format: ID, decision, why, trade-off, revisit trigger.*
