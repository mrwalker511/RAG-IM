import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
from ragcore.config import settings
from ragcore.projects.service import get_project
from ragcore.providers import make_embedder, make_generator
from ragcore.query.pipeline import QueryResult, prepare_query_context, run_query
from ragcore.retrieval.reranker import CrossEncoderReranker

router = APIRouter(prefix="/projects/{project_id}/query", tags=["query"])


def _make_embedder():
    return make_embedder()


def _make_generator():
    return make_generator()


def _source_to_response(source) -> "SourceResponse":
    data = dict(source.__dict__)
    data["chunk_id"] = str(data["chunk_id"])
    return SourceResponse(**data)


class QueryRequest(BaseModel):
    query: str
    top_k: int | None = None
    filters: dict | None = None
    debug: bool = False
    rerank: bool = True
    mode: str = "hybrid"
    include_context: bool = False
    include_eval: bool = False


class SourceResponse(BaseModel):
    chunk_id: str
    filename: str
    chunk_index: int
    score: float
    source_kind: str | None = None
    source_label: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
    latency_ms: int
    tokens_used: int
    retrieval: dict[str, Any] | None = None
    eval: dict[str, Any] | None = None


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
        mode=body.mode,
    )

    return QueryResponse(
        answer=result.answer,
        sources=[_source_to_response(s) for s in result.sources],
        latency_ms=result.latency_ms,
        tokens_used=result.tokens_used,
        retrieval=result.retrieval_trace if body.debug or body.include_context else None,
        eval=result.eval_payload if body.include_eval else None,
    )


@router.get("/stream")
async def stream_query(
    project_id: uuid.UUID,
    q: str,
    rerank: bool = False,
    mode: str = "hybrid",
    include_context: bool = False,
    session: AsyncSession = Depends(get_db_session),
):
    project = await get_project(project_id, session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    embedder = _make_embedder()
    generator = _make_generator()
    reranker = CrossEncoderReranker() if rerank else None

    prepared = await prepare_query_context(
        project_id=project_id,
        query_text=q,
        session=session,
        embedder=embedder,
        top_k=settings.DEFAULT_TOP_K,
        reranker=reranker,
        mode=mode,
    )
    sources = [
        {
            "chunk_id": str(chunk.chunk_id),
            "filename": chunk.filename,
            "chunk_index": chunk.chunk_index,
            "score": chunk.score,
            "source_kind": chunk.source_kind,
            "source_label": chunk.source_label,
        }
        for chunk in prepared.top_chunks
    ]
    token_gen = await generator.generate(prepared.prompt, stream=True)

    async def event_stream():
        yield f"event: sources\ndata: {json.dumps(sources)}\n\n"
        if include_context:
            yield f"event: retrieval\ndata: {json.dumps(prepared.retrieval_trace)}\n\n"
        # Subsequent events: token chunks
        try:
            async for token in token_gen:
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
