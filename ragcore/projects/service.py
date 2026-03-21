import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.db.models import Project
from ragcore.projects.schemas import ProjectCreate


async def create_project(data: ProjectCreate, session: AsyncSession) -> Project:
    project = Project(name=data.name, config=data.config.model_dump())
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return project


async def get_project(project_id: uuid.UUID, session: AsyncSession) -> Project | None:
    result = await session.execute(select(Project).where(Project.id == project_id))
    return result.scalar_one_or_none()


async def get_project_by_name(name: str, session: AsyncSession) -> Project | None:
    result = await session.execute(select(Project).where(Project.name == name))
    return result.scalar_one_or_none()


async def list_projects(session: AsyncSession) -> list[Project]:
    result = await session.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


async def delete_project(project_id: uuid.UUID, session: AsyncSession) -> bool:
    result = await session.execute(delete(Project).where(Project.id == project_id))
    return result.rowcount > 0
