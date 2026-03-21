import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
from ragcore.config import settings
from ragcore.embeddings.base import BaseEmbedder
from ragcore.generation.base import BaseLLMGenerator
from ragcore.projects.service import get_project
from ragcore.query.pipeline import QueryResult, run_query
from ragcore.retrieval.reranker import CrossEncoderReranker

router = APIRouter(prefix="/projects/{project_id}/query", tags=["query"])


def _make_embedder() -> BaseEmbedder:
    if settings.EMBEDDING_PROVIDER == "sentence_transformer":
        from ragcore.embeddings.sentence_transformer_embedder import SentenceTransformerEmbedder
        return SentenceTransformerEmbedder(model_name=settings.EMBEDDING_MODEL)
    from ragcore.embeddings.openai_embedder import OpenAIEmbedder
    return OpenAIEmbedder()


def _make_generator() -> BaseLLMGenerator:
    if settings.LLM_PROVIDER == "litellm":
        from ragcore.generation.litellm_generator import LiteLLMGenerator
        return LiteLLMGenerator()
    from ragcore.generation.openai_generator import OpenAIGenerator
    return OpenAIGenerator()


class QueryRequest(BaseModel):
    query: str
    top_k: int | None = None
    filters: dict | None = None
    debug: bool = False
    rerank: bool = True


class SourceResponse(BaseModel):
    chunk_id: str
    filename: str
    chunk_index: int
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
    latency_ms: int
    tokens_used: int


@router.post("", response_model=QueryResponse)
async def query_project(
    project_id: uuid.UUID,
    body: QueryRequest,
    session: AsyncSession = Depends(get_db_session),
):
    project = await get_project(project_id, session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    embedder = _make_embedder()
    generator = _make_generator()
    reranker = CrossEncoderReranker() if body.rerank else None

    result: QueryResult = await run_query(
        project_id=project_id,
        query_text=body.query,
        session=session,
        embedder=embedder,
        generator=generator,
        top_k=body.top_k,
        reranker=reranker,
        filter_dict=body.filters,
        debug=body.debug,
    )

    return QueryResponse(
        answer=result.answer,
        sources=[SourceResponse(**s.__dict__) for s in result.sources],
        latency_ms=result.latency_ms,
        tokens_used=result.tokens_used,
    )


@router.get("/stream")
async def stream_query(
    project_id: uuid.UUID,
    q: str,
    rerank: bool = False,
    session: AsyncSession = Depends(get_db_session),
):
    project = await get_project(project_id, session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    embedder = _make_embedder()
    generator = _make_generator()
    reranker = CrossEncoderReranker() if rerank else None

    # Run retrieval/reranking synchronously first so we can emit sources before tokens
    from ragcore.query.pipeline import _ensure_bm25_index, SourceAttribution
    from ragcore.retrieval.bm25_search import bm25_search
    from ragcore.retrieval.hybrid import reciprocal_rank_fusion
    from ragcore.retrieval.vector_search import vector_search
    from ragcore.generation.prompt_builder import build_prompt

    k = settings.DEFAULT_TOP_K
    rerank_n = settings.RERANK_TOP_N

    query_vectors = await embedder.embed([q])
    query_vector = query_vectors[0]

    vector_results = await vector_search(
        project_id=project_id, query_vector=query_vector, top_k=rerank_n, session=session
    )
    await _ensure_bm25_index(project_id, session)
    bm25_results = await bm25_search(
        project_id=project_id, query_tokens=q.lower().split(), top_k=rerank_n, session=session
    )

    from ragcore.retrieval.vector_search import ChunkResult
    fused: list[ChunkResult] = reciprocal_rank_fusion(vector_results, bm25_results)[:rerank_n]
    if reranker and fused:
        fused = reranker.rerank(q, fused)
    top_chunks = fused[:k]

    sources = [
        {"chunk_id": str(c.chunk_id), "filename": c.filename, "chunk_index": c.chunk_index, "score": c.score}
        for c in top_chunks
    ]
    prompt = build_prompt(q, top_chunks)
    token_gen = await generator.generate(prompt, stream=True)

    async def event_stream():
        # First event: sources metadata
        yield f"event: sources\ndata: {json.dumps(sources)}\n\n"
        # Subsequent events: token chunks
        try:
            async for token in token_gen:
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
