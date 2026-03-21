# RAG Framework — Skills & Conventions

## Abstract Interface Pattern

All pluggable components (parsers, embedders, LLMs) extend an ABC defined in a `base.py` file.
Tests run against the abstract interface via dependency injection — never against the concrete class directly.

```python
# Good: inject the interface
async def run_query(embedder: BaseEmbedder, generator: BaseLLMGenerator, ...):
    ...

# Bad: instantiate concrete class inside logic
embedder = OpenAIEmbedder()
```

## Async-First

- Use `async def` and `await` throughout
- SQLAlchemy sessions are `AsyncSession` everywhere
- Background tasks go through ARQ workers, not FastAPI `BackgroundTasks`
- API handlers for uploads must enqueue an ARQ job and return immediately

## Project Scoping

Every DB query involving documents, chunks, query logs, or BM25 indexes **must** filter by `project_id`.

```python
# Always include project_id filter
stmt = select(Chunk).where(Chunk.project_id == project_id, ...)
```

## BM25 Index Lifecycle

1. Built once after ingest or delete events (mark stale on change)
2. Serialized with `pickle` → stored as BYTEA in `bm25_indexes` table
3. Loaded from DB on query — **not rebuilt per query**
4. Rebuilt lazily before next query when stale flag is set

```python
# Correct pattern
index = await load_bm25_index(project_id, session)
if index is None or index.is_stale:
    index = await rebuild_bm25_index(project_id, session)
results = index.search(tokens, top_k)
```

## Embedding Batching

- OpenAI embedder batches requests and respects rate limits
- SentenceTransformer embedder runs locally — no API key required (local fallback)
- Both implement `BaseEmbedder`; swap via `EMBEDDING_PROVIDER` env var

## Chunking Guard

Chunk size must be validated against the embedding model's max token limit.
Raise `ConfigError` on violation.

```python
# Defaults (overridable per project via projects.config JSONB)
DEFAULT_CHUNK_SIZE = 512    # tokens
DEFAULT_CHUNK_OVERLAP = 64  # tokens
# text-embedding-3-small max: 8191 tokens
```

## API Auth

All API endpoints require `X-API-Key` header. Keys are:
- SHA-256 hashed on storage
- Stored in `api_keys` table, scoped to a `project_id`
- Validated in `api/middleware.py` before reaching route handlers

```
Missing key   → 401 Unauthorized
Wrong project → 403 Forbidden
Valid key     → pass through
```

## Hybrid Search (RRF)

Reciprocal Rank Fusion combines vector and BM25 results:

```python
def reciprocal_rank_fusion(
    vector_results: list[ChunkResult],
    bm25_results: list[ChunkResult],
    k: int = 60,
) -> list[ChunkResult]:
    # score = sum(1 / (k + rank_i)) for each list
```

## Observability

- All query events logged async to `query_logs` with: latency_ms, tokens_used, top_scores, project_id
- Ingestion and query pipelines emit **structured JSON logs** (use stdlib `logging` with JSON formatter)
- Debug trace flag per query: dumps retrieved chunks + scores to stdout when enabled

## Testing Conventions

| Fixture / Pattern        | Purpose                                                         |
|--------------------------|-----------------------------------------------------------------|
| `async_test_engine`      | Creates fresh async DB per test session; drops/recreates tables |
| `mock_embedder`          | Returns random vectors of correct dimension (no API call)       |
| `mock_llm`               | Returns deterministic string for assertion                      |
| `sample_docs/`           | 1-page PDF, simple DOCX, .md, .txt fixture files                |
| Integration tests        | Seed DB with known data before asserting retrieval accuracy     |

## CLI Usage (Generic Examples)

```bash
docker compose up -d

rag project create "my-project"
rag project list
rag project delete "my-project"

rag ingest my-project ./docs/
rag ingest status <job_id>

rag query my-project "Summarize the key points in these documents."
rag query my-project "What does section 3 cover?" --top-k 10 --stream
```

## Adding a New Provider

To add a new embedder or LLM backend:
1. Create a new file in `ragcore/embeddings/` or `ragcore/generation/`
2. Subclass `BaseEmbedder` or `BaseLLMGenerator`
3. Implement all abstract methods
4. Add the provider name to `EMBEDDING_PROVIDER` / `LLM_PROVIDER` enum in `config.py`
5. Wire it in the factory function used by the query pipeline
6. Add unit tests using the abstract interface fixture
