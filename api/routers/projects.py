import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
from ragcore.projects import schemas, service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=schemas.ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: schemas.ProjectCreate,
    session: AsyncSession = Depends(get_db_session),
):
    existing = await service.get_project_by_name(data.name, session)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project name already exists")
    return await service.create_project(data, session)


@router.get("", response_model=schemas.ProjectList)
async def list_projects(session: AsyncSession = Depends(get_db_session)):
    projects = await service.list_projects(session)
    return schemas.ProjectList(projects=projects, total=len(projects))


@router.get("/{project_id}", response_model=schemas.ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
):
    project = await service.get_project(project_id, session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
):
    deleted = await service.delete_project(project_id, session)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
