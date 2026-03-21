import logging
import pickle
import uuid
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.db.models import BM25Index, Chunk, Document
from ragcore.retrieval.vector_search import ChunkResult

logger = logging.getLogger(__name__)


@dataclass
class _IndexPayload:
    bm25: BM25Okapi
    chunk_ids: list[uuid.UUID]
    chunk_contents: list[str]
    chunk_indices: list[int]
    filenames: list[str]
    document_ids: list[uuid.UUID]
    metadatas: list[dict]


async def build_bm25_index(project_id: uuid.UUID, session: AsyncSession) -> None:
    """Build BM25 index from all project chunks and persist to DB."""
    result = await session.execute(
        select(Chunk, Document.filename)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.project_id == project_id)
        .order_by(Chunk.chunk_index)
    )
    rows = result.all()

    if not rows:
        logger.info("No chunks found for project %s; skipping BM25 build", project_id)
        return

    tokenized = [row.Chunk.content.lower().split() for row in rows]
    bm25 = BM25Okapi(tokenized)

    payload = _IndexPayload(
        bm25=bm25,
        chunk_ids=[row.Chunk.id for row in rows],
        chunk_contents=[row.Chunk.content for row in rows],
        chunk_indices=[row.Chunk.chunk_index for row in rows],
        filenames=[row.filename for row in rows],
        document_ids=[row.Chunk.document_id for row in rows],
        metadatas=[row.Chunk.meta for row in rows],
    )
    serialized = pickle.dumps(payload)

    existing = await session.execute(
        select(BM25Index).where(BM25Index.project_id == project_id)
    )
    index_row = existing.scalar_one_or_none()
    if index_row:
        index_row.index_data = serialized
    else:
        session.add(BM25Index(project_id=project_id, index_data=serialized))

    await session.flush()
    logger.info("BM25 index built for project %s (%d chunks)", project_id, len(rows))


async def bm25_search(
    project_id: uuid.UUID,
    query_tokens: list[str],
    top_k: int,
    session: AsyncSession,
) -> list[ChunkResult]:
    result = await session.execute(
        select(BM25Index).where(BM25Index.project_id == project_id)
    )
    index_row = result.scalar_one_or_none()
    if not index_row:
        return []

    payload: _IndexPayload = pickle.loads(index_row.index_data)
    scores = payload.bm25.get_scores(query_tokens)

    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

    return [
        ChunkResult(
            chunk_id=payload.chunk_ids[i],
            document_id=payload.document_ids[i],
            project_id=project_id,
            content=payload.chunk_contents[i],
            score=float(score),
            chunk_index=payload.chunk_indices[i],
            filename=payload.filenames[i],
            metadata=payload.metadatas[i],
        )
        for i, score in ranked
        if score > 0
    ]


async def invalidate_bm25_index(project_id: uuid.UUID, session: AsyncSession) -> None:
    """Mark BM25 index stale by deleting it — will be rebuilt on next query."""
    result = await session.execute(
        select(BM25Index).where(BM25Index.project_id == project_id)
    )
    index_row = result.scalar_one_or_none()
    if index_row:
        await session.delete(index_row)
        await session.flush()
