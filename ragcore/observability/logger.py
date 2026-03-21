import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.db.models import QueryLog

logger = logging.getLogger(__name__)


async def log_query_event(
    project_id: uuid.UUID,
    query_text: str,
    latency_ms: int,
    tokens_used: int,
    top_scores: list[dict],
    session: AsyncSession,
) -> None:
    entry = QueryLog(
        project_id=project_id,
        query_text=query_text,
        latency_ms=latency_ms,
        tokens_used=tokens_used,
        top_scores={"scores": top_scores},
    )
    session.add(entry)
    try:
        await session.flush()
    except Exception:
        logger.exception("Failed to log query event for project %s", project_id)
