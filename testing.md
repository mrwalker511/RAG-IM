# Testing Guide — RAG-IM

A step-by-step guide to verifying every layer of the RAG framework, from unit tests
through live end-to-end smoke tests.

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11+ |
| Docker + Docker Compose | v2+ |
| LLM provider credentials | Current verified local stack uses `LLM_PROVIDER=litellm` with Mistral |

---

## 1. Environment Setup

### 1.1 Clone and install dependencies

```bash
git clone <repo-url>
cd RAG-IM
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 1.2 Create `.env`

```bash
cp .env.example .env             # if available, otherwise create manually
```

Minimum `.env` for local testing:

```ini
DATABASE_URL=postgresql+asyncpg://rag:rag@localhost:5433/rag_db
REDIS_URL=redis://localhost:6379
UPLOAD_TMP_DIR=/tmp
EMBEDDING_PROVIDER=sentence_transformer
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIM=384
LLM_PROVIDER=litellm
LLM_MODEL=mistral/mistral-small-latest
# Set the provider credential LiteLLM needs for your chosen model, e.g.
# MISTRAL_API_KEY=...
```

Current verified local stack:

- Compose project: `ragimdev`
- Embeddings: local SentenceTransformer
- LLM: LiteLLM + Mistral
- Docker Compose overrides `DATABASE_URL`, `REDIS_URL`, and `UPLOAD_TMP_DIR` inside `api` and `worker`

---

## 2. Unit Tests (no external services required)

Unit tests mock all I/O and run fully offline.

```bash
pytest tests/unit/ -v
```

Expected output - all of the following suites should pass:

| Test file | What it covers |
|---|---|
| `test_chunker.py` | Text splitting, overlap, size limits |
| `test_parsers.py` | PDF / Markdown text extraction |
| `test_docx_parser.py` | DOCX extraction, empty-doc returns `[]` |
| `test_prompt_builder.py` | Prompt construction, context truncation |
| `test_hybrid_search.py` | RRF fusion, score ordering |
| `test_bm25_index.py` | BM25 build and search logic |
| `test_deduplication.py` | Duplicate chunk filtering |
| `test_generation.py` | `GenerationResult` with real token count; zero-token fallback |
| `test_query_pipeline.py` | `run_query` result, cache hit, stream bypass; BM25 staleness (missing / stale / fresh) |
| `test_middleware.py` | `api_key_middleware` (401 on missing/invalid key, pass-through on valid); `rate_limit_middleware` (429 after limit, Retry-After header, per-key isolation, disabled at 0) |
| `test_redis_cache.py` | `_cache_key` (deterministic, uniqueness); `_get_cached` (TTL=0, miss, hit, Redis error); `_set_cached` (TTL=0, correct write, Redis error) |

### Run with coverage

```bash
pytest tests/unit/ --cov=ragcore --cov=api --cov-report=term-missing
```

Aim for ≥ 80 % coverage on `ragcore/`.

---

## 3. Infrastructure Setup

Start Postgres and Redis (required for API and integration tests):

```bash
docker compose -p ragimdev up -d postgres redis
```

Wait until healthy:

```bash
docker compose -p ragimdev ps   # both should show "healthy"
```

### 3.1 Run database migrations

```bash
docker compose -p ragimdev exec -T api alembic upgrade head
```

Verify all tables exist:

```bash
psql postgresql://rag:rag@localhost:5433/rag_db -c "\dt"
```

Expected tables: `projects`, `documents`, `chunks`, `bm25_indexes`,
`query_logs`, `api_keys`.

---

## 4. API Tests (requires Postgres + Redis)

These tests spin up the FastAPI app in-process with a dedicated test database.

### 4.1 Create the test database

```bash
psql postgresql://rag:rag@localhost:5433/postgres -c "CREATE DATABASE test_rag;"
```

### 4.2 Run API tests

```bash
pytest tests/api/ -v
```

| Test file | What it covers |
|---|---|
| `test_projects_api.py` | CRUD for projects (create, list, delete, 409 conflict, 404) |
| `test_api_keys.py` | Create key (raw key returned once), list keys (no raw key), delete key, 404 paths |

> **Note:** All API tests require `X-API-Key` to be sent. The `api_client` fixture in `conftest.py` handles this automatically — it seeds a test API key into the test DB and includes the header on every request. `api.middleware.AsyncSessionLocal` is patched to use the test engine so auth lookups resolve correctly.

---

## 5. Full Stack Manual Test

Start all services:

```bash
docker compose -p ragimdev up -d --build
```

Check the API is reachable:

```bash
curl -sS http://localhost:8000/health
# {"status":"ok"}
```

> **Note:** In this workspace, Docker-internal validation has been more reliable than host-side multipart/query requests to `localhost:8000`. The smoke commands below run from inside the `api` container for that reason.

### 5.1 Create a project

If this workspace already has a seeded bootstrap project/key, see `STATUS.md` and export those values. Otherwise seed one with §5.2.

Once a bootstrap API key exists, create additional projects through the API:

```bash
curl -s -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret-key" \
  -d '{"name": "another-project"}' | jq .
```

> **Note:** The middleware enforces `X-API-Key` on all non-health routes, so the first bootstrap project/key must be seeded directly in the DB or created with auth temporarily bypassed.

### 5.2 Seed a bootstrap API key

```bash
python - <<'EOF'
import hashlib, asyncio
from ragcore.db.session import AsyncSessionLocal
from ragcore.db.models import APIKey, Project
import uuid

RAW_KEY = "dev-secret-key"
key_hash = hashlib.sha256(RAW_KEY.encode()).hexdigest()

async def seed():
    async with AsyncSessionLocal() as s:
        # Create project
        proj = Project(name="test-project", config={})
        s.add(proj)
        await s.flush()
        # Attach API key
        s.add(APIKey(project_id=proj.id, key_hash=key_hash, label="dev"))
        await s.commit()
        print(f"Project ID: {proj.id}")

asyncio.run(seed())
EOF
```

Now use `X-API-Key: dev-secret-key` in all subsequent requests.

### 5.3 Upload a document

```bash
export PROJECT_ID=<PROJECT_ID>
export API_KEY=dev-secret-key

docker compose -p ragimdev exec -T api python - <<'PY'
import os
import httpx

files = {
    "file": ("test.txt", b"The capital of France is Paris.\n", "text/plain"),
}
r = httpx.post(
    f"http://127.0.0.1:8000/projects/{os.environ['PROJECT_ID']}/documents",
    headers={"X-API-Key": os.environ["API_KEY"]},
    files=files,
    timeout=30.0,
)
print(r.status_code)
print(r.text)
PY
```

### 5.4 Check ingestion status (API)

```bash
export DOCUMENT_ID=<DOCUMENT_ID>

docker compose -p ragimdev exec -T api python - <<'PY'
import os
import time
import httpx

url = (
    "http://127.0.0.1:8000/projects/"
    f"{os.environ['PROJECT_ID']}/documents/{os.environ['DOCUMENT_ID']}/status"
)
headers = {"X-API-Key": os.environ["API_KEY"]}

with httpx.Client(timeout=10.0) as client:
    deadline = time.time() + 180
    while time.time() < deadline:
        r = client.get(url, headers=headers)
        print(r.status_code, r.text)
        if r.status_code == 200 and r.json()["status"] in {"complete", "failed"}:
            break
        time.sleep(2)
PY
```

### 5.5 Check ingestion status (CLI)

```bash
RAG_API_KEY=dev-secret-key python -m cli.main ingest status <JOB_ID>
```

Expected output:

```
Job <JOB_ID>: complete
Enqueued: 2026-03-21 ...
```

### 5.6 Run a query (non-streaming)

```bash
docker compose -p ragimdev exec -T api python - <<'PY'
import os
import httpx

r = httpx.post(
    f"http://127.0.0.1:8000/projects/{os.environ['PROJECT_ID']}/query",
    headers={"X-API-Key": os.environ["API_KEY"]},
    json={"query": "What is the capital of France?"},
    timeout=120.0,
)
print(r.status_code)
print(r.text)
PY
```

Expected shape:

```json
{
  "answer": "The capital of France is Paris.",
  "sources": [{"chunk_id": "...", "filename": "test.txt", "chunk_index": 0, "score": 0.95}],
  "latency_ms": 843,
  "tokens_used": 58
}
```

Verify:

- `tokens_used` is **not** 0
- `sources` contains `test.txt`
- The first query after a container restart may be slow because the sentence-transformer model warms on first use.

### 5.7 Run a query (streaming)

```bash
curl -sN "http://localhost:8000/projects/<PROJECT_ID>/query/stream?q=What+is+the+capital+of+France" \
  -H "X-API-Key: dev-secret-key"
```

Expected SSE output:

```
event: sources
data: [{"chunk_id":"...","filename":"test.txt","chunk_index":0,"score":0.95}]

data: The
data:  capital
data:  of
data:  France
data:  is
data:  Paris.

data: [DONE]
```

Verify the **first event** is `event: sources` with JSON — this confirms the streaming metadata fix.

### 5.8 CLI full workflow

```bash
export RAG_API_KEY=dev-secret-key
export RAG_API_URL=http://localhost:8000

# List projects
python -m cli.main project list

# Upload a document
python -m cli.main ingest run test-project /tmp/test.txt

# Query
python -m cli.main query test-project "What is the capital of France?"

# Streaming query
python -m cli.main query test-project "Summarise the document" --stream
```

---

## 6. API Key Management Endpoints

```bash
PROJECT_ID=<your-project-id>
API_KEY=dev-secret-key

# Create a new key
curl -s -X POST "http://localhost:8000/projects/$PROJECT_ID/api-keys" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"label": "ci-key"}' | jq .
# Verify "key" field is present in the response

# List keys (raw "key" must NOT appear)
curl -s "http://localhost:8000/projects/$PROJECT_ID/api-keys" \
  -H "X-API-Key: $API_KEY" | jq .

# Delete a key
KEY_ID=<key-id-from-create>
curl -s -X DELETE "http://localhost:8000/projects/$PROJECT_ID/api-keys/$KEY_ID" \
  -H "X-API-Key: $API_KEY" -o /dev/null -w "%{http_code}"
# Expect: 204
```

---

## 7. Provider Switching

### 7.1 Switch to local embeddings (no API key required)

In `.env`:

```ini
EMBEDDING_PROVIDER=sentence_transformer
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIM=384
```

Restart the API and worker, then repeat §5.6. The model will be downloaded on first use.
Verify there are no timeouts caused by a blocking `encode()` call — the fix runs it
in a thread executor.

### 7.2 Switch to LiteLLM generator

In `.env`:

```ini
LLM_PROVIDER=litellm
LLM_MODEL=mistral/mistral-small-latest   # or any other LiteLLM-supported model
```

Restart and repeat §5.6. `tokens_used` must still be non-zero.

---

## 8. BM25 Staleness Check

Verify the staleness rebuild triggers correctly:

```bash
# Set a very short stale window
BM25_STALE_AFTER_MINUTES=0  # in .env or environment

# Query — first query builds the index
curl -s -X POST ".../query" -H "..." -d '{"query":"test"}' | jq .latency_ms

# Query again immediately — index is stale (0-minute window), must rebuild
curl -s -X POST ".../query" -H "..." -d '{"query":"test"}' | jq .latency_ms
```

Check worker logs for:

```
INFO  BM25 index for project <id> is stale; rebuilding
```

---

## 9. DOCX Parser Edge Cases

```bash
python - <<'EOF'
from pathlib import Path
from unittest.mock import MagicMock, patch
from ragcore.ingestion.parsers.docx import DocxParser

# Empty document
mock_doc = MagicMock()
mock_doc.paragraphs = []
with patch("ragcore.ingestion.parsers.docx.docx.Document", return_value=mock_doc):
    result = DocxParser().parse(Path("x.docx"))
assert result == [], f"Expected [], got {result!r}"
print("PASS: empty document returns []")
EOF
```

---

## 10. Database Migration Check

```bash
# Start from scratch
alembic downgrade base
alembic upgrade head

# Verify no errors, then check tables
psql postgresql://rag:rag@localhost:5433/rag_db -c "\dt"
```

Expected tables (6):

```
 api_keys
 bm25_indexes
 chunks
 documents
 projects
 query_logs
```

---

## 11. Full Test Suite

Run everything at once (requires Postgres + Redis running and `test_rag` database to exist):

```bash
pytest tests/ -v --cov=ragcore --cov=api --cov-report=term-missing
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `tokens_used: 0` in response | Old code path / non-OpenAI provider with `usage=None` | Verify generator returns `GenerationResult`; check `response.usage` |
| First SSE event is a token, not sources | Old streaming router | Confirm `event: sources` line appears first in the stream |
| `asyncio.TimeoutError` during embedding | Blocking `encode()` on event loop | Confirm `run_in_executor` is in `sentence_transformer_embedder.py` |
| Upload stays `pending` and worker logs `FileNotFoundError` for `/tmp/...` | API and worker are not sharing upload temp storage | Confirm Compose mounts the shared temp volume and `UPLOAD_TMP_DIR=/shared-tmp` is set for both services |
| Upload fails with `MissingGreenlet` in ingestion | Async lazy-load on `doc.chunks` | Confirm `run_ingestion` deletes chunks with an explicit SQL query, not by iterating `doc.chunks` |
| Query fails with `TypeError: 'float' object is not subscriptable` | pgvector distance expression typed as `Vector` instead of numeric | Confirm `ragcore/retrieval/vector_search.py` uses `return_type=Float` for `<=>` |
| Temp file left in `/tmp` after upload failure | Old worker cleanup path | Confirm `ingest_document` deletes temp files in `finally` |
| `alembic upgrade head` → `relation does not exist` | Migration file missing | Confirm `alembic/versions/0001_initial_schema.py` exists |
| BM25 index never rebuilds | Staleness check absent | Confirm `_ensure_bm25_index` compares `updated_at` to `BM25_STALE_AFTER_MINUTES` |
| `ingest status` prints stub message | Old CLI | Confirm ARQ `Job.status()` is called in `cli/main.py` |
| `401 Missing X-API-Key` on all routes | No key seeded | Run the bootstrap seed script in §5.2 |
