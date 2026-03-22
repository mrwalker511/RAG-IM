"""Ingest all project markdown docs directly via ragcore pipeline (no API/worker needed).

Uses SentenceTransformer (all-MiniLM-L6-v2, 384 dims) — no API key required.

Usage:
    python scripts/ingest_project_docs.py

Requires PostgreSQL running and migrations applied:
    alembic upgrade head

RAG_PROJECT_NAME env var overrides the default project name "rag-im-docs".
"""
import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import select

from ragcore.db.models import Project
from ragcore.db.session import AsyncSessionLocal
from ragcore.embeddings.sentence_transformer_embedder import SentenceTransformerEmbedder
from ragcore.ingestion.pipeline import run_ingestion

PROJECT_NAME = os.getenv("RAG_PROJECT_NAME", "rag-im-docs")
PROJECT_ROOT = Path(__file__).parent.parent
MD_FILES = sorted(PROJECT_ROOT.glob("*.md"))


async def get_or_create_project(session):
    result = await session.execute(select(Project).where(Project.name == PROJECT_NAME))
    project = result.scalar_one_or_none()
    if not project:
        project = Project(name=PROJECT_NAME)
        session.add(project)
        await session.flush()
        print(f"Created project: {PROJECT_NAME} ({project.id})")
    else:
        print(f"Using existing project: {PROJECT_NAME} ({project.id})")
    return project


async def main() -> int:
    if not MD_FILES:
        print("No .md files found in project root.", file=sys.stderr)
        return 1

    print(f"Files to ingest ({len(MD_FILES)}):")
    for f in MD_FILES:
        print(f"  {f.name}")
    print()

    embedder = SentenceTransformerEmbedder()
    failed = 0

    async with AsyncSessionLocal() as session:
        project = await get_or_create_project(session)

        for f in MD_FILES:
            try:
                doc = await run_ingestion(
                    project_id=project.id,
                    file_path=f,
                    session=session,
                    embedder=embedder,
                    metadata={"original_filename": f.name},
                )
                print(f"  ✓ {f.name} → {doc.status}")
            except Exception as exc:
                print(f"  ✗ {f.name} → {exc}", file=sys.stderr)
                failed += 1

        await session.commit()

    print(f"\nDone. {len(MD_FILES) - failed}/{len(MD_FILES)} files ingested successfully.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
