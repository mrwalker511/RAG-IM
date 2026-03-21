from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.config import settings
from ragcore.db.models import BM25Index
from ragcore.db.redis import get_redis
from ragcore.embeddings.base import BaseEmbedder
from ragcore.generation.base import BaseLLMGenerator, GenerationResult
from ragcore.generation.prompt_builder import build_prompt
from ragcore.observability.logger import log_query_event
from ragcore.retrieval.bm25_search import bm25_search, build_bm25_index
from ragcore.retrieval.hybrid import reciprocal_rank_fusion
from ragcore.retrieval.reranker import CrossEncoderReranker
from ragcore.retrieval.vector_search import ChunkResult, vector_search

logger = logging.getLogger(__name__)


def _cache_key(project_id: uuid.UUID, query_text: str, top_k: int) -> str:
    digest = hashlib.sha256(f"{project_id}:{query_text}:{top_k}".encode()).hexdigest()
    return f"query_cache:{digest}"


async def _get_cached(key: str) -> QueryResult | None:
    """Return a cached QueryResult or None."""
    if settings.QUERY_CACHE_TTL == 0:
        return None
    try:
        redis = get_redis()
        raw = await redis.get(key)
        if raw is None:
            return None
        data = json.loads(raw)
        return QueryResult(
            answer=data["answer"],
            sources=[SourceAttribution(**s) for s in data["sources"]],
            latency_ms=data["latency_ms"],
            tokens_used=data["tokens_used"],
        )
    except Exception:
        logger.debug("Redis cache read failed; proceeding without cache", exc_info=True)
        return None


async def _set_cached(key: str, result: QueryResult) -> None:
    if settings.QUERY_CACHE_TTL == 0:
        return
    try:
        redis = get_redis()
        payload = json.dumps(
            {
                "answer": result.answer,
                "sources": [asdict(s) for s in result.sources],
                "latency_ms": result.latency_ms,
                "tokens_used": result.tokens_used,
            }
        )
        await redis.setex(key, settings.QUERY_CACHE_TTL, payload)
    except Exception:
        logger.debug("Redis cache write failed; continuing without caching", exc_info=True)


@dataclass
class SourceAttribution:
    chunk_id: str
    filename: str
    chunk_index: int
    score: float


@dataclass
class QueryResult:
    answer: str
    sources: list[SourceAttribution]
    latency_ms: int
    tokens_used: int


async def _ensure_bm25_index(project_id: uuid.UUID, session: AsyncSession) -> None:
    """Build BM25 index if missing or stale."""
    result = await session.execute(select(BM25Index).where(BM25Index.project_id == project_id))
    index_row = result.scalar_one_or_none()
    if hasattr(index_row, "__await__"):
        index_row = await index_row

    if index_row is None:
        await build_bm25_index(project_id, session)
        return

    stale_threshold = timedelta(minutes=settings.BM25_STALE_AFTER_MINUTES)
    now = datetime.now(tz=timezone.utc)
    updated_at = index_row.updated_at
    # Ensure updated_at is timezone-aware for comparison
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    if now - updated_at > stale_threshold:
        logger.info("BM25 index for project %s is stale; rebuilding", project_id)
        await build_bm25_index(project_id, session)


async def run_query(
    project_id: uuid.UUID,
    query_text: str,
    session: AsyncSession,
    embedder: BaseEmbedder,
    generator: BaseLLMGenerator,
    top_k: int | None = None,
    reranker: CrossEncoderReranker | None = None,
    filter_dict: dict | None = None,
    stream: bool = False,
    debug: bool = False,
) -> QueryResult | AsyncGenerator[str, None]:
    k = top_k or settings.DEFAULT_TOP_K
    rerank_n = settings.RERANK_TOP_N

    # Cache lookup (skip for streaming — responses can't be cached mid-stream)
    if not stream:
        cache_key = _cache_key(project_id, query_text, k)
        cached = await _get_cached(cache_key)
        if cached is not None:
            logger.debug("Cache hit for query '%s' project %s", query_text[:60], project_id)
            return cached

    start = time.monotonic()

    # 1. Embed query
    query_vectors = await embedder.embed([query_text])
    query_vector = query_vectors[0]

    # 2. Vector search
    vector_results = await vector_search(
        project_id=project_id,
        query_vector=query_vector,
        top_k=rerank_n,
        session=session,
        filter_dict=filter_dict,
    )

    # 3. BM25 search — build/refresh index if missing or stale
    await _ensure_bm25_index(project_id, session)

    query_tokens = query_text.lower().split()
    bm25_results = await bm25_search(
        project_id=project_id,
        query_tokens=query_tokens,
        top_k=rerank_n,
        session=session,
    )

    # 4. RRF fusion
    fused: list[ChunkResult] = reciprocal_rank_fusion(vector_results, bm25_results)[:rerank_n]

    # 5. Rerank
    if reranker and fused:
        fused = reranker.rerank(query_text, fused)

    top_chunks = fused[:k]

    if debug:
        for i, c in enumerate(top_chunks):
            logger.debug(
                "Chunk %d [%s/%d] score=%.4f: %s",
                i, c.filename, c.chunk_index, c.score, c.content[:120],
            )

    # 6. Build prompt
    prompt = build_prompt(query_text, top_chunks)

    sources = [
        SourceAttribution(
            chunk_id=str(c.chunk_id),
            filename=c.filename,
            chunk_index=c.chunk_index,
            score=c.score,
        )
        for c in top_chunks
    ]
    top_scores = [{"filename": s.filename, "chunk_index": s.chunk_index, "score": s.score} for s in sources]

    if stream:
        async def _streaming_gen() -> AsyncGenerator[str, None]:
            gen = await generator.generate(prompt, stream=True)
            async for token in gen:
                yield token

        return _streaming_gen()

    # 7. Generate
    result: GenerationResult = await generator.generate(prompt, stream=False)
    latency_ms = int((time.monotonic() - start) * 1000)

    await log_query_event(
        project_id=project_id,
        query_text=query_text,
        latency_ms=latency_ms,
        tokens_used=result.tokens_used,
        top_scores=top_scores,
        session=session,
    )

    query_result = QueryResult(
        answer=result.text,
        sources=sources,
        latency_ms=latency_ms,
        tokens_used=result.tokens_used,
    )
    await _set_cached(cache_key, query_result)
    return query_result
