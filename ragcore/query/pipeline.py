from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections import defaultdict
from collections.abc import AsyncGenerator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.config import settings
from ragcore.db.models import BM25Index
from ragcore.db.redis import get_redis
from ragcore.embeddings.base import BaseEmbedder
from ragcore.generation.base import BaseLLMGenerator, GenerationResult
from ragcore.generation.prompt_builder import build_prompt
from ragcore.graph.retrieval import global_graph_search, local_graph_search
from ragcore.observability.logger import log_query_event
from ragcore.retrieval.bm25_search import bm25_search, build_bm25_index
from ragcore.retrieval.hybrid import reciprocal_rank_fusion
from ragcore.retrieval.reranker import CrossEncoderReranker
from ragcore.retrieval.vector_search import ChunkResult, vector_search

logger = logging.getLogger(__name__)

SUPPORTED_QUERY_MODES = {"naive", "local", "global", "hybrid", "mix"}


def _cache_key(
    project_id: uuid.UUID,
    query_text: str,
    top_k: int,
    mode: str = "hybrid",
    filter_dict: dict | None = None,
    rerank: bool = False,
) -> str:
    payload = {
        "project_id": str(project_id),
        "query_text": query_text,
        "top_k": top_k,
        "mode": mode,
        "filters": filter_dict or {},
        "rerank": rerank,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return f"query_cache:{project_id}:{digest}"


async def _get_cached(key: str) -> QueryResult | None:
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
            retrieval_trace=data.get("retrieval_trace", {}),
            eval_payload=data.get("eval_payload", {}),
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
                "retrieval_trace": result.retrieval_trace,
                "eval_payload": result.eval_payload,
            }
        )
        await redis.setex(key, settings.QUERY_CACHE_TTL, payload)
    except Exception:
        logger.debug("Redis cache write failed; continuing without caching", exc_info=True)


async def invalidate_project_query_cache(project_id: uuid.UUID) -> None:
    if settings.QUERY_CACHE_TTL == 0:
        return
    try:
        redis = get_redis()
        keys: list[str] = []
        async for key in redis.scan_iter(match=f"query_cache:{project_id}:*"):
            keys.append(key)
        if keys:
            await redis.delete(*keys)
    except Exception:
        logger.debug("Redis cache invalidation failed for project %s", project_id, exc_info=True)


@dataclass
class SourceAttribution:
    chunk_id: str
    filename: str
    chunk_index: int
    score: float
    source_kind: str = "chunk"
    source_label: str | None = None


@dataclass
class QueryResult:
    answer: str
    sources: list[SourceAttribution]
    latency_ms: int
    tokens_used: int
    retrieval_trace: dict = field(default_factory=dict)
    eval_payload: dict = field(default_factory=dict)


@dataclass
class PreparedQueryContext:
    prompt: str
    top_chunks: list[ChunkResult]
    retrieval_trace: dict


async def _ensure_bm25_index(project_id: uuid.UUID, session: AsyncSession) -> None:
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
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    if now - updated_at > stale_threshold:
        logger.info("BM25 index for project %s is stale; rebuilding", project_id)
        await build_bm25_index(project_id, session)


def _trace_candidate(chunk: ChunkResult) -> dict:
    return {
        "chunk_id": str(chunk.chunk_id),
        "filename": chunk.filename,
        "chunk_index": chunk.chunk_index,
        "score": round(chunk.score, 4),
        "source_kind": chunk.source_kind,
        "source_label": chunk.source_label,
    }


def _fuse_ranked_lists(*ranked_lists: list[ChunkResult], k: int = 60) -> list[ChunkResult]:
    scores: dict[uuid.UUID, float] = defaultdict(float)
    by_id: dict[uuid.UUID, ChunkResult] = {}

    for ranked_list in ranked_lists:
        for rank, result in enumerate(ranked_list):
            scores[result.chunk_id] += 1.0 / (k + rank + 1)
            by_id[result.chunk_id] = result

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [by_id[item_id] for item_id, _ in ranked]


def _validate_mode(mode: str) -> str:
    normalized = mode.lower()
    if normalized not in SUPPORTED_QUERY_MODES:
        raise ValueError(f"Unsupported query mode: {mode}")
    return normalized


def _build_sources(chunks: list[ChunkResult]) -> list[SourceAttribution]:
    return [
        SourceAttribution(
            chunk_id=str(chunk.chunk_id),
            filename=chunk.filename,
            chunk_index=chunk.chunk_index,
            score=chunk.score,
            source_kind=chunk.source_kind,
            source_label=chunk.source_label,
        )
        for chunk in chunks
    ]


def _build_eval_payload(
    query_text: str,
    answer: str,
    mode: str,
    chunks: list[ChunkResult],
) -> dict:
    contexts = [
        {
            "chunk_id": str(chunk.chunk_id),
            "source_kind": chunk.source_kind,
            "source_label": chunk.source_label or chunk.filename,
            "filename": chunk.filename,
            "chunk_index": chunk.chunk_index,
            "score": round(chunk.score, 4),
            "content": chunk.content[:1000],
        }
        for chunk in chunks
    ]
    return {
        "question": query_text,
        "answer": answer,
        "mode": mode,
        "contexts": contexts,
    }


async def prepare_query_context(
    project_id: uuid.UUID,
    query_text: str,
    session: AsyncSession,
    embedder: BaseEmbedder,
    top_k: int | None = None,
    reranker: CrossEncoderReranker | None = None,
    filter_dict: dict | None = None,
    mode: str = "hybrid",
) -> PreparedQueryContext:
    mode = _validate_mode(mode)
    k = top_k or settings.DEFAULT_TOP_K
    rerank_n = max(k, settings.RERANK_TOP_N)

    vector_results: list[ChunkResult] = []
    bm25_results: list[ChunkResult] = []
    graph_local_chunks: list[ChunkResult] = []
    graph_global_chunks: list[ChunkResult] = []
    graph_entities: list[dict] = []
    graph_relations: list[dict] = []

    if mode in {"naive", "hybrid", "mix"}:
        query_vectors = await embedder.embed([query_text])
        vector_results = await vector_search(
            project_id=project_id,
            query_vector=query_vectors[0],
            top_k=rerank_n,
            session=session,
            filter_dict=filter_dict,
        )

    if mode in {"hybrid", "mix"}:
        await _ensure_bm25_index(project_id, session)
        bm25_results = await bm25_search(
            project_id=project_id,
            query_tokens=query_text.lower().split(),
            top_k=rerank_n,
            session=session,
        )

    if mode in {"local", "hybrid", "mix"}:
        local_graph = await local_graph_search(
            project_id=project_id,
            query_text=query_text,
            top_k=rerank_n,
            session=session,
        )
        graph_local_chunks = local_graph.chunks
        graph_entities = local_graph.entities

    if mode in {"global", "hybrid", "mix"}:
        global_graph = await global_graph_search(
            project_id=project_id,
            query_text=query_text,
            top_k=rerank_n,
            session=session,
        )
        graph_global_chunks = global_graph.chunks
        if not graph_entities:
            graph_entities = global_graph.entities
        graph_relations = global_graph.relations

    keyword_results = reciprocal_rank_fusion(vector_results, bm25_results)[:rerank_n]

    if mode == "naive":
        fused = vector_results[:rerank_n]
    elif mode == "local":
        fused = graph_local_chunks[:rerank_n]
    elif mode == "global":
        fused = graph_global_chunks[:rerank_n]
    elif mode == "mix":
        fused = _fuse_ranked_lists(vector_results, graph_local_chunks, graph_global_chunks)[:rerank_n]
    else:
        fused = _fuse_ranked_lists(keyword_results, graph_local_chunks, graph_global_chunks)[:rerank_n]

    if reranker and fused:
        fused = reranker.rerank(query_text, fused)

    top_chunks = fused[:k]
    prompt = build_prompt(query_text, top_chunks)
    retrieval_trace = {
        "mode": mode,
        "vector_candidates": [_trace_candidate(chunk) for chunk in vector_results[:k]],
        "keyword_candidates": [_trace_candidate(chunk) for chunk in bm25_results[:k]],
        "graph_entities": graph_entities[:k],
        "graph_relations": graph_relations[:k],
        "selected_contexts": [_trace_candidate(chunk) for chunk in top_chunks],
        "prompt_preview": prompt[:2000],
    }
    return PreparedQueryContext(prompt=prompt, top_chunks=top_chunks, retrieval_trace=retrieval_trace)


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
    mode: str = "hybrid",
) -> QueryResult | AsyncGenerator[str, None]:
    normalized_mode = _validate_mode(mode)
    k = top_k or settings.DEFAULT_TOP_K

    if not stream:
        cache_key = _cache_key(
            project_id=project_id,
            query_text=query_text,
            top_k=k,
            mode=normalized_mode,
            filter_dict=filter_dict,
            rerank=reranker is not None,
        )
        cached = await _get_cached(cache_key)
        if cached is not None:
            logger.debug("Cache hit for query '%s' project %s", query_text[:60], project_id)
            return cached

    start = time.monotonic()
    prepared = await prepare_query_context(
        project_id=project_id,
        query_text=query_text,
        session=session,
        embedder=embedder,
        top_k=k,
        reranker=reranker,
        filter_dict=filter_dict,
        mode=normalized_mode,
    )

    if debug:
        for index, chunk in enumerate(prepared.top_chunks):
            logger.debug(
                "Context %d [%s/%d kind=%s score=%.4f]: %s",
                index,
                chunk.filename,
                chunk.chunk_index,
                chunk.source_kind,
                chunk.score,
                chunk.content[:120],
            )

    if stream:
        async def _streaming_gen() -> AsyncGenerator[str, None]:
            gen = await generator.generate(prepared.prompt, stream=True)
            async for token in gen:
                yield token

        return _streaming_gen()

    result: GenerationResult = await generator.generate(prepared.prompt, stream=False)
    latency_ms = int((time.monotonic() - start) * 1000)
    sources = _build_sources(prepared.top_chunks)
    top_scores = [{"filename": source.filename, "chunk_index": source.chunk_index, "score": source.score} for source in sources]
    eval_payload = _build_eval_payload(
        query_text=query_text,
        answer=result.text,
        mode=normalized_mode,
        chunks=prepared.top_chunks,
    )

    await log_query_event(
        project_id=project_id,
        query_text=query_text,
        query_mode=normalized_mode,
        latency_ms=latency_ms,
        tokens_used=result.tokens_used,
        top_scores=top_scores,
        retrieval_trace=prepared.retrieval_trace,
        eval_payload=eval_payload,
        session=session,
    )

    query_result = QueryResult(
        answer=result.text,
        sources=sources,
        latency_ms=latency_ms,
        tokens_used=result.tokens_used,
        retrieval_trace=prepared.retrieval_trace,
        eval_payload=eval_payload,
    )
    await _set_cached(cache_key, query_result)
    return query_result
