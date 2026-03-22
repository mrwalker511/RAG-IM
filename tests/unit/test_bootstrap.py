"""Tests for startup bootstrap seeding."""

from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ragcore.bootstrap import ensure_bootstrap_project_api_key
from ragcore.db.models import APIKey, Project


@pytest.mark.asyncio
async def test_bootstrap_seed_creates_project_and_key(test_engine):
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    with patch("ragcore.bootstrap.settings") as s:
        s.BOOTSTRAP_API_KEY = "bootstrap-key-a"
        s.BOOTSTRAP_PROJECT_NAME = "bootstrap-project-a"
        s.BOOTSTRAP_API_KEY_LABEL = "bootstrap"
        await ensure_bootstrap_project_api_key(factory)

    async with factory() as session:
        project = (
            await session.execute(select(Project).where(Project.name == "bootstrap-project-a"))
        ).scalar_one()
        api_key = (
            await session.execute(select(APIKey).where(APIKey.project_id == project.id))
        ).scalar_one()

    assert project.name == "bootstrap-project-a"
    assert api_key.label == "bootstrap"


@pytest.mark.asyncio
async def test_bootstrap_seed_is_idempotent_for_existing_key(test_engine):
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    with patch("ragcore.bootstrap.settings") as s:
        s.BOOTSTRAP_API_KEY = "bootstrap-key-b"
        s.BOOTSTRAP_PROJECT_NAME = "bootstrap-project-b"
        s.BOOTSTRAP_API_KEY_LABEL = "bootstrap"
        await ensure_bootstrap_project_api_key(factory)
        await ensure_bootstrap_project_api_key(factory)

    async with factory() as session:
        projects = (
            await session.execute(select(Project).where(Project.name == "bootstrap-project-b"))
        ).scalars().all()
        project_ids = [project.id for project in projects]
        keys = (
            await session.execute(select(APIKey).where(APIKey.project_id.in_(project_ids)))
        ).scalars().all()

    assert len(projects) == 1
    assert len(keys) == 1
