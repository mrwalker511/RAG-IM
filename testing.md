# Testing

## Fast Path

```bash
docker compose -p ragimdev up -d --build
docker compose -p ragimdev exec -T api alembic upgrade head
curl -sS http://localhost:8000/health
```

Open:

- `http://localhost:8000/`
- `http://localhost:8000/handbook`

## Unit Tests

```bash
pytest tests/unit -v
```

## DB-Backed Tests

Create the test DB once:

```bash
docker compose -p ragimdev up -d postgres redis
docker compose -p ragimdev exec -T postgres psql -U rag -d postgres -c 'CREATE DATABASE test_rag;'
```

Run from the host:

```bash
env TEST_DATABASE_URL=postgresql+asyncpg://rag:rag@localhost:5433/test_rag ./.venv/bin/pytest tests/api tests/integration -v
```

If host networking is flaky, run the same suites inside `api`:

```bash
docker compose -p ragimdev exec -T api env TEST_DATABASE_URL=postgresql+asyncpg://rag:rag@postgres:5432/test_rag pytest tests/api tests/integration -v
```

## Smoke Test

1. Open `/`.
2. Use the auto-filled bootstrap key to create or list a project.
3. Upload one or more documents and wait for the auto-poll to reach `complete`.
4. Run a query and confirm the response includes source filenames.

## Current Caveat

In this workspace, container-internal test and smoke commands have been more reliable than host-side access to `localhost:8000` and `localhost:5433`.
