import logging
import uuid
from pathlib import Path

from arq import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.config import settings
from ragcore.db.session import AsyncSessionLocal
from ragcore.embeddings.openai_embedder import OpenAIEmbedder
from ragcore.ingestion.pipeline import run_ingestion

logger = logging.getLogger(__name__)


async def ingest_document(
    ctx: dict,
    project_id: str,
    file_path: str,
    metadata: dict | None = None,
) -> dict:
    """ARQ task: ingest a single document into the vector store."""
    async with AsyncSessionLocal() as session:
        embedder = OpenAIEmbedder()
        doc = await run_ingestion(
            project_id=uuid.UUID(project_id),
            file_path=Path(file_path),
            session=session,
            embedder=embedder,
            metadata=metadata,
        )
        await session.commit()
        return {"document_id": str(doc.id), "status": doc.status}


class WorkerSettings:
    functions = [ingest_document]
    redis_settings = settings.REDIS_URL
