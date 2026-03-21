import logging
import time
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.config import settings
from ragcore.embeddings.base import BaseEmbedder
from ragcore.generation.base import BaseLLMGenerator
from ragcore.generation.prompt_builder import build_prompt
from ragcore.observability.logger import log_query_event
from ragcore.retrieval.bm25_search import bm25_search, build_bm25_index
from ragcore.retrieval.hybrid import reciprocal_rank_fusion
from ragcore.retrieval.reranker import CrossEncoderReranker
from ragcore.retrieval.vector_search import ChunkResult, vector_search

logger = logging.getLogger(__name__)


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

    # 3. BM25 search (ensure index exists)
    from sqlalchemy import select
    from ragcore.db.models import BM25Index
    idx = await session.execute(select(BM25Index).where(BM25Index.project_id == project_id))
    if not idx.scalar_one_or_none():
        await build_bm25_index(project_id, session)

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
            logger.debug("Chunk %d [%s/%d] score=%.4f: %s", i, c.filename, c.chunk_index, c.score, c.content[:120])

    # 6. Build prompt + generate
    prompt = build_prompt(query_text, top_chunks)

    tokens_used = 0
    latency_ms = 0
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

    answer = await generator.generate(prompt, stream=False)
    latency_ms = int((time.monotonic() - start) * 1000)

    await log_query_event(
        project_id=project_id,
        query_text=query_text,
        latency_ms=latency_ms,
        tokens_used=tokens_used,
        top_scores=top_scores,
        session=session,
    )

    return QueryResult(
        answer=answer,
        sources=sources,
        latency_ms=latency_ms,
        tokens_used=tokens_used,
    )
