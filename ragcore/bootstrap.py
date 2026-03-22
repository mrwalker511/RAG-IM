import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ragcore.config import settings
from ragcore.db.models import APIKey, Project
from ragcore.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def ensure_bootstrap_project_api_key(
    session_factory: async_sessionmaker = AsyncSessionLocal,
) -> None:
    raw_key = settings.BOOTSTRAP_API_KEY.strip()
    if not raw_key:
        return

    project_name = settings.BOOTSTRAP_PROJECT_NAME.strip() or "default"
    key_label = settings.BOOTSTRAP_API_KEY_LABEL.strip() or "bootstrap"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    async with session_factory() as session:
        result = await session.execute(select(APIKey).where(APIKey.key_hash == key_hash))
        existing_key = result.scalar_one_or_none()
        if existing_key:
            return

        result = await session.execute(select(Project).where(Project.name == project_name))
        project = result.scalar_one_or_none()
        if not project:
            project = Project(name=project_name, config={})
            session.add(project)
            await session.flush()

        session.add(APIKey(project_id=project.id, key_hash=key_hash, label=key_label))
        await session.commit()
        logger.info(
            "Seeded bootstrap API key for project '%s'.",
            project_name,
        )
