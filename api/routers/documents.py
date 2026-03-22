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
from ragcore.ingestion.deduplication import compute_hash
from ragcore.projects.service import get_project
from ragcore.retrieval.bm25_search import invalidate_bm25_index

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])


class DocumentStatus(BaseModel):
    document_id: str
    filename: str
    status: str


class UploadResponse(BaseModel):
    job_id: str
    document_id: str
    filename: str


class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


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
    upload_dir = Path(settings.UPLOAD_TMP_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=upload_dir) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    content_hash = compute_hash(Path(tmp_path))

    # Create the pending row before enqueue so the worker can update this exact record.
    doc = Document(
        project_id=project_id,
        filename=file.filename or "unknown",
        content_hash=content_hash,
        status="pending",
        meta={},
    )
    session.add(doc)
    await session.flush()

    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job(
            "ingest_document",
            str(project_id),
            tmp_path,
            {
                "document_id": str(doc.id),
                "original_filename": file.filename,
            },
        )
    except Exception:
        import os
        os.unlink(tmp_path)
        raise

    doc.meta = {"job_id": job.job_id}

    return UploadResponse(job_id=job.job_id, document_id=str(doc.id), filename=doc.filename)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
):
    project = await get_project(project_id, session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await session.execute(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
    )
    documents = list(result.scalars().all())
    return DocumentListResponse(
        documents=[
            DocumentResponse(id=str(doc.id), filename=doc.filename, status=doc.status)
            for doc in documents
        ],
        total=len(documents),
    )


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
    await invalidate_bm25_index(project_id, session)
