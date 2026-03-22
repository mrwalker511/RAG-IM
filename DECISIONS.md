# Architectural Decisions

## 001 — Redis-backed shared rate limiting

**Decision:** `rate_limit_middleware` stores per-key request windows in Redis sorted sets.

**Why:**

- Works correctly across multiple API workers
- Reuses infrastructure already required for ARQ and query caching
- Keeps rate-limit behavior consistent after horizontal scaling

**Trade-off:** Redis is now on the request path for limiting. The middleware fails open if Redis is unavailable so availability wins over strict throttling.

## 002 — Middleware still uses `AsyncSessionLocal` directly

**Decision:** Auth remains in FastAPI middleware and uses `AsyncSessionLocal` instead of route DI.

**Why:**

- Middleware runs outside FastAPI dependency injection
- The auth and project-scope check should apply globally, not router-by-router

**Trade-off:** Tests must patch `api.middleware.AsyncSessionLocal` and bootstrap-key detection explicitly.

## 003 — Bootstrap admin key plus project-scoped keys

**Decision:** `/projects` create/list is reserved for `BOOTSTRAP_API_KEY`; project routes require either the bootstrap key or a key bound to the matching `project_id`.

**Why:**

- Fixes the previous cross-project authorization hole
- Preserves a simple first-run bootstrap path for fresh deployments
- Keeps normal runtime access scoped to one project

**Trade-off:** Bootstrap key management is now an operational responsibility and should be rotated out of normal traffic.

## 004 — Redis cache failures do not break queries

**Decision:** Query-cache reads and writes catch exceptions and fall back to uncached behavior.

**Why:** Cache availability must not determine query availability.

**Trade-off:** Without external monitoring, a cache outage is easy to miss.

## 005 — ARQ for ingestion

**Decision:** Document ingestion remains in ARQ workers, not FastAPI background tasks.

**Why:** Uploads should return immediately and ingestion failures should be isolated from the API process.

## 006 — Lightweight parser stack

**Decision:** Parsing stays on `pypdf`, `python-docx`, and `markdown-it-py`, not `unstructured`.

**Why:** The current format set is sufficient and avoids heavy native dependencies.
