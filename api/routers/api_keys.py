import hashlib
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
from ragcore.db.models import APIKey
from ragcore.projects.service import get_project

router = APIRouter(prefix="/projects/{project_id}/api-keys", tags=["api-keys"])


class APIKeyCreate(BaseModel):
    label: str | None = None


class APIKeyResponse(BaseModel):
    id: str
    label: str | None
    created_at: str

    class Config:
        from_attributes = True


class APIKeyCreated(APIKeyResponse):
    """Returned only at creation time — includes the raw key."""
    key: str


@router.post("", response_model=APIKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    project_id: uuid.UUID,
    body: APIKeyCreate,
    session: AsyncSession = Depends(get_db_session),
):
    project = await get_project(project_id, session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    api_key = APIKey(project_id=project_id, key_hash=key_hash, label=body.label)
    session.add(api_key)
    await session.flush()
    await session.refresh(api_key)

    return APIKeyCreated(
        id=str(api_key.id),
        label=api_key.label,
        created_at=api_key.created_at.isoformat(),
        key=raw_key,
    )


@router.get("", response_model=list[APIKeyResponse])
async def list_api_keys(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
):
    project = await get_project(project_id, session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await session.execute(
        select(APIKey).where(APIKey.project_id == project_id).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        APIKeyResponse(id=str(k.id), label=k.label, created_at=k.created_at.isoformat())
        for k in keys
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.project_id == project_id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    await session.delete(api_key)
