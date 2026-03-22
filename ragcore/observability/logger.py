import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.db.models import QueryLog

logger = logging.getLogger(__name__)


async def log_query_event(
    project_id: uuid.UUID,
    query_text: str,
    query_mode: str,
    latency_ms: int,
    tokens_used: int,
    top_scores: list[dict],
    retrieval_trace: dict,
    eval_payload: dict,
    session: AsyncSession,
) -> None:
    entry = QueryLog(
        project_id=project_id,
        query_text=query_text,
        query_mode=query_mode,
        latency_ms=latency_ms,
        tokens_used=tokens_used,
        top_scores={"scores": top_scores},
        retrieval_trace=retrieval_trace,
        eval_payload=eval_payload,
    )
    session.add(entry)
    try:
        await session.flush()
    except Exception:
        logger.exception("Failed to log query event for project %s", project_id)
