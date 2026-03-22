# Project Status

## Current Branch

`main`

## Last Session — 2026-03-22

### Completed

- Added a public handbook at `/handbook` that renders the checked-in Markdown docs as browser pages
- Linked the Control Room at `/` to the handbook and OpenAPI
- Refreshed the Markdown docs to match the current auth model, web surfaces, and test workflow
- Kept `testing.md` to a short bring-up and verification runbook

### Validation

- `python -m compileall api ragcore tests` passed
- `pytest tests/unit/test_middleware.py -q` passed
- `pytest tests/api/test_projects_api.py -k 'health or root_serves_web_app_without_auth or handbook or cors_preflight' -q` passed

### Still Open

- DB-backed `tests/api` and `tests/integration` were not re-run from this sandbox against a reachable `test_rag` database
- Attempting the DB-backed project API tests against `10.146.91.103:5433` still failed with `OSError: [Errno 113] Connect call failed`
- Host-side requests to `localhost:8000` and `localhost:5433` can still be intermittently unreliable in this workspace

## Known Gaps

| Gap | Location | Priority |
|---|---|---|
| DB-backed suites are not yet part of the local validation loop from this sandbox | Test environment | High |
| `CORS_ORIGINS=*` is still allowed by code defaults; safe deployment depends on explicit env config | `ragcore/config.py` / `.env` | High |
| Bootstrap key is intentionally high-privilege and should not be used for normal app traffic | Auth / ops | High |
| First query after restart is slower while the local embedding model warms up | Query path | Medium |
