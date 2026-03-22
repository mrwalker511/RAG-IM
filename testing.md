# Testing

## Fastest Checks

```bash
pytest tests/unit/test_middleware.py -q
pytest tests/unit -q
```

DB-backed tests need a reachable `TEST_DATABASE_URL`.

## Stack Bring-Up

```bash
cp .env.example .env
# Set BOOTSTRAP_API_KEY, provider credentials, and explicit CORS origins.

docker compose -p ragimdev up -d --build
docker compose -p ragimdev exec -T api alembic upgrade head
curl -sS http://localhost:8000/health
```

## Full Smoke Test

In this workspace, multipart and query checks have been more reliable from inside the `api` container than from the host shell.

```bash
docker compose -p ragimdev exec -T api python - <<'PY'
import os
import time
import uuid
import httpx

base = "http://127.0.0.1:8000"
headers = {"X-API-Key": os.environ["BOOTSTRAP_API_KEY"]}
project_name = f"smoke-{uuid.uuid4().hex[:8]}"

with httpx.Client(timeout=120.0) as client:
    project = client.post(f"{base}/projects", headers=headers, json={"name": project_name})
    project.raise_for_status()
    project_id = project.json()["id"]
    print("PROJECT", project_id)

    upload = client.post(
        f"{base}/projects/{project_id}/documents",
        headers=headers,
        files={"file": ("smoke.txt", b"The deployment phrase is teal-orbit.\\n", "text/plain")},
    )
    upload.raise_for_status()
    payload = upload.json()
    document_id = payload["document_id"]
    print("UPLOAD", payload)

    status_url = f"{base}/projects/{project_id}/documents/{document_id}/status"
    deadline = time.time() + 180
    while time.time() < deadline:
        status = client.get(status_url, headers=headers)
        status.raise_for_status()
        body = status.json()
        print("STATUS", body)
        if body["status"] in {"complete", "failed"}:
            break
        time.sleep(2)

    query = client.post(
        f"{base}/projects/{project_id}/query",
        headers=headers,
        json={"query": "What is the deployment phrase?", "rerank": False},
    )
    query.raise_for_status()
    print("QUERY", query.json())
PY
```

Success criteria:

- Upload returns `202`
- Document reaches `complete`
- Query returns `200`
- Query `sources` includes `smoke.txt`
- Query `tokens_used` is not `0`

After the smoke test, create a project-scoped key for app traffic:

```bash
curl -s -X POST "http://localhost:8000/projects/<PROJECT_ID>/api-keys" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOOTSTRAP_API_KEY" \
  -d '{"label": "app"}'
```

## DB-Backed Suites

```bash
export TEST_DATABASE_URL=postgresql+asyncpg://rag:rag@localhost:5433/test_rag
pytest tests/api tests/integration -q
```

## Common Failures

| Symptom | Fix |
|---|---|
| `401 Missing X-API-Key` | Set `BOOTSTRAP_API_KEY` in `.env` and restart |
| `403 Bootstrap API key required` | Use the bootstrap key only for `/projects` create/list |
| Upload stays `pending` | Confirm both containers use `UPLOAD_TMP_DIR=/shared-tmp` and share the volume |
| First query is slow | Expected on cold start when local models warm up |
