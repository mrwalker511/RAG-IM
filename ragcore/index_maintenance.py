from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.graph.service import purge_document_graph
from ragcore.query.pipeline import invalidate_project_query_cache
from ragcore.retrieval.bm25_search import invalidate_bm25_index


async def maintain_project_indexes_for_document_delete(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    await purge_document_graph(project_id=project_id, document_id=document_id, session=session)
    await invalidate_bm25_index(project_id, session)
    await invalidate_project_query_cache(project_id)
