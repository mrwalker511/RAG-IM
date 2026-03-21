import hashlib
import shutil
import tempfile
import uuid
from pathlib import Path

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
from ragcore.config import settings
from ragcore.db.models import Document
from ragcore.projects.service import get_project

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])


class DocumentStatus(BaseModel):
    document_id: str
    filename: str
    status: str


class UploadResponse(BaseModel):
    job_id: str
    document_id: str
    filename: str


@router.post("", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
):
    project = await get_project(project_id, session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Save to temp file for worker
    suffix = Path(file.filename or "upload").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job(
            "ingest_document",
            str(project_id),
            tmp_path,
            {"original_filename": file.filename},
        )
    except Exception:
        import os
        os.unlink(tmp_path)
        raise

    # Create a pending document record
    doc = Document(
        project_id=project_id,
        filename=file.filename or "unknown",
        content_hash=hashlib.sha256(b"pending").hexdigest(),
        status="pending",
        metadata={"job_id": job.job_id},
    )
    session.add(doc)
    await session.flush()

    return UploadResponse(job_id=job.job_id, document_id=str(doc.id), filename=doc.filename)


@router.get("/{document_id}/status", response_model=DocumentStatus)
async def get_document_status(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(Document).where(Document.id == document_id, Document.project_id == project_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentStatus(document_id=str(doc.id), filename=doc.filename, status=doc.status)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(Document).where(Document.id == document_id, Document.project_id == project_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    await session.delete(doc)
