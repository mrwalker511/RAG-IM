import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.db.models import Chunk, Document
from ragcore.embeddings.base import BaseEmbedder
from ragcore.ingestion.chunker import chunk_texts
from ragcore.ingestion.deduplication import compute_hash
from ragcore.ingestion.parsers.base import BaseParser
from ragcore.ingestion.parsers.docx import DocxParser
from ragcore.ingestion.parsers.markdown import MarkdownParser
from ragcore.ingestion.parsers.pdf import PDFParser
from ragcore.ingestion.parsers.text import TextParser

logger = logging.getLogger(__name__)

_PARSER_MAP: dict[str, type[BaseParser]] = {
    ".pdf": PDFParser,
    ".docx": PDFParser,  # overridden below
    ".md": MarkdownParser,
    ".markdown": MarkdownParser,
    ".txt": TextParser,
}
_PARSER_MAP[".docx"] = DocxParser


def _get_parser(path: Path) -> BaseParser:
    suffix = path.suffix.lower()
    cls = _PARSER_MAP.get(suffix, TextParser)
    return cls()


async def _get_target_document(
    project_id: uuid.UUID,
    session: AsyncSession,
    content_hash: str,
    filename: str,
    metadata: dict | None,
) -> Document | None:
    if metadata and metadata.get("document_id"):
        document_id = uuid.UUID(metadata["document_id"])
        result = await session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()

    result = await session.execute(
        select(Document).where(
            Document.project_id == project_id,
            Document.filename == filename,
            Document.content_hash == content_hash,
        )
    )
    return result.scalar_one_or_none()


async def run_ingestion(
    project_id: uuid.UUID,
    file_path: Path,
    session: AsyncSession,
    embedder: BaseEmbedder,
    metadata: dict | None = None,
) -> Document:
    content_hash = compute_hash(file_path)
    filename = (metadata or {}).get("original_filename") or file_path.name
    doc = await _get_target_document(project_id, session, content_hash, filename, metadata)

    # Deduplication check
    if doc and doc.status == "complete":
        logger.info("Skipping unchanged document: %s", filename)
        return doc

    # Upsert document row
    if not doc:
        doc = Document(
            project_id=project_id,
            filename=filename,
            content_hash=content_hash,
            status="processing",
            meta=metadata or {},
        )
        session.add(doc)
    else:
        doc.filename = filename
        doc.status = "processing"
        doc.content_hash = content_hash
        if metadata:
            doc.meta = {**doc.meta, **metadata}
        # Remove old chunks so we can replace them
        for chunk in list(doc.chunks):
            await session.delete(chunk)

    await session.flush()

    try:
        parser = _get_parser(file_path)
        sections = parser.parse(file_path)
        chunk_results = chunk_texts(sections)
        texts = [c.content for c in chunk_results]
        vectors = await embedder.embed(texts)

        for chunk_res, vector in zip(chunk_results, vectors):
            chunk = Chunk(
                document_id=doc.id,
                project_id=project_id,
                content=chunk_res.content,
                embedding=vector,
                chunk_index=chunk_res.chunk_index,
                meta={},
            )
            session.add(chunk)

        doc.status = "complete"
        logger.info("Ingested %d chunks from %s", len(chunk_results), filename)
    except Exception as exc:
        doc.status = "failed"
        logger.exception("Ingestion failed for %s: %s", filename, exc)
        raise

    await session.flush()
    return doc
