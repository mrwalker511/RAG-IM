# Architectural Decisions

## 001 — Redis-backed shared rate limiting

`rate_limit_middleware` stores request windows in Redis sorted sets so throttling stays consistent across multiple API workers.

Trade-off: Redis is on the request path for limiting, so the middleware fails open if Redis is unavailable.

## 002 — Auth stays in middleware, not route DI

Authentication and project-scope checks use `AsyncSessionLocal` directly in middleware because the policy must apply globally, outside FastAPI dependency injection.

Trade-off: tests must patch `api.middleware.AsyncSessionLocal` and bootstrap-key detection explicitly.

## 003 — Bootstrap admin key plus project-scoped keys

`BOOTSTRAP_API_KEY` is reserved for project creation and listing. Project routes accept either the bootstrap key or a key whose `project_id` matches the URL.

Trade-off: bootstrap key handling is now an operational responsibility.

## 004 — Cache failures do not break queries

Query-cache reads and writes fall back to uncached behavior if Redis errors.

Trade-off: without logging or metrics, cache outages are easy to miss.

## 005 — ARQ remains the ingestion boundary

Document ingestion stays in workers rather than FastAPI background tasks so uploads return quickly and ingestion failures stay isolated from the API process.

## 006 — Lightweight parser stack

Parsing stays on `pypdf`, `python-docx`, and `markdown-it-py` rather than heavier parser stacks.

## 007 — Handbook routes are public and repo-backed

`/handbook` and `/handbook/{doc}` are exempt from API-key auth and render the checked-in Markdown files directly from the repo.

Trade-off: the public docs surface must stay curated; only the published Markdown allowlist should be routable.
