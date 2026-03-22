import logging
import uuid
from pathlib import Path

from arq.connections import RedisSettings
from sqlalchemy import select

from ragcore.config import settings
from ragcore.db.models import Document
from ragcore.db.session import AsyncSessionLocal
from ragcore.ingestion.pipeline import run_ingestion
from ragcore.providers import make_embedder
from ragcore.query.pipeline import invalidate_project_query_cache
from ragcore.retrieval.bm25_search import invalidate_bm25_index

logger = logging.getLogger(__name__)


async def ingest_document(
    ctx: dict,
    project_id: str,
    file_path: str,
    metadata: dict | None = None,
) -> dict:
    """ARQ task: ingest a single document into the vector store."""
    target_doc_id = metadata.get("document_id") if metadata else None
    file = Path(file_path)
    async with AsyncSessionLocal() as session:
        try:
            embedder = make_embedder()
            doc = await run_ingestion(
                project_id=uuid.UUID(project_id),
                file_path=file,
                session=session,
                embedder=embedder,
                metadata=metadata,
            )
            await invalidate_bm25_index(uuid.UUID(project_id), session)
            await session.commit()
            await invalidate_project_query_cache(uuid.UUID(project_id))
            return {"document_id": str(doc.id), "status": doc.status}
        except Exception:
            logger.exception("ingest_document failed for project %s file %s", project_id, file)
            await session.rollback()
            if target_doc_id:
                result = await session.execute(
                    select(Document).where(
                        Document.id == uuid.UUID(target_doc_id),
                        Document.project_id == uuid.UUID(project_id),
                    )
                )
                doc = result.scalar_one_or_none()
                if doc:
                    doc.status = "failed"
            await session.commit()
            raise
        finally:
            try:
                file.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to delete upload temp file %s", file, exc_info=True)


class WorkerSettings:
    functions = [ingest_document]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
