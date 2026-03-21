import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
from ragcore.config import settings
from ragcore.embeddings.openai_embedder import OpenAIEmbedder
from ragcore.generation.openai_generator import OpenAIGenerator
from ragcore.projects.service import get_project
from ragcore.query.pipeline import QueryResult, run_query
from ragcore.retrieval.reranker import CrossEncoderReranker

router = APIRouter(prefix="/projects/{project_id}/query", tags=["query"])


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

    embedder = OpenAIEmbedder()
    generator = OpenAIGenerator()
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
    session: AsyncSession = Depends(get_db_session),
):
    project = await get_project(project_id, session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    embedder = OpenAIEmbedder()
    generator = OpenAIGenerator()

    gen = await run_query(
        project_id=project_id,
        query_text=q,
        session=session,
        embedder=embedder,
        generator=generator,
        stream=True,
    )

    async def event_stream():
        async for token in gen:
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
