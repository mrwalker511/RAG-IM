import uuid
from dataclasses import dataclass

from pgvector.sqlalchemy import Vector
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.db.models import Chunk, Document


@dataclass
class ChunkResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    project_id: uuid.UUID
    content: str
    score: float
    chunk_index: int
    filename: str
    metadata: dict


async def vector_search(
    project_id: uuid.UUID,
    query_vector: list[float],
    top_k: int,
    session: AsyncSession,
    filter_dict: dict | None = None,
) -> list[ChunkResult]:
    stmt = (
        select(
            Chunk,
            Document.filename,
            (Chunk.embedding.op("<=>", return_type=Vector)(query_vector)).label("distance"),
        )
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.project_id == project_id)
    )

    if filter_dict:
        for key, value in filter_dict.items():
            stmt = stmt.where(Chunk.metadata[key].astext == str(value))

    stmt = stmt.order_by(text("distance")).limit(top_k)

    result = await session.execute(stmt)
    rows = result.all()

    return [
        ChunkResult(
            chunk_id=row.Chunk.id,
            document_id=row.Chunk.document_id,
            project_id=row.Chunk.project_id,
            content=row.Chunk.content,
            score=1.0 - float(row.distance),  # cosine similarity from distance
            chunk_index=row.Chunk.chunk_index,
            filename=row.filename,
            metadata=row.Chunk.metadata,
        )
        for row in rows
    ]
