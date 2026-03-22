import logging
import uuid
from pathlib import Path

from arq.connections import RedisSettings

from ragcore.config import settings
from ragcore.db.session import AsyncSessionLocal
from ragcore.ingestion.pipeline import run_ingestion
from ragcore.providers import make_embedder

logger = logging.getLogger(__name__)


async def ingest_document(
    ctx: dict,
    project_id: str,
    file_path: str,
    metadata: dict | None = None,
) -> dict:
    """ARQ task: ingest a single document into the vector store."""
    async with AsyncSessionLocal() as session:
        embedder = make_embedder()
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
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
