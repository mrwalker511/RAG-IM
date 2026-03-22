"""Tests for startup bootstrap seeding."""

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ragcore.bootstrap import ensure_bootstrap_project_api_key
from ragcore.db.models import APIKey, Project


def _scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@asynccontextmanager
async def _session_factory(session):
    yield session


@pytest.mark.asyncio
async def test_bootstrap_seed_creates_project_and_key():
    added = []
    project_id = uuid.uuid4()
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_result(None),
            _scalar_result(None),
        ]
    )
    session.add.side_effect = added.append

    async def _flush():
        for item in added:
            if isinstance(item, Project):
                item.id = project_id

    session.flush = AsyncMock(side_effect=_flush)
    session.commit = AsyncMock()

    with patch("ragcore.bootstrap.settings") as s:
        s.BOOTSTRAP_API_KEY = "bootstrap-key-a"
        s.BOOTSTRAP_PROJECT_NAME = "bootstrap-project-a"
        s.BOOTSTRAP_API_KEY_LABEL = "bootstrap"
        await ensure_bootstrap_project_api_key(lambda: _session_factory(session))

    assert len(added) == 2
    assert isinstance(added[0], Project)
    assert added[0].name == "bootstrap-project-a"
    assert isinstance(added[1], APIKey)
    assert added[1].project_id == project_id
    assert added[1].label == "bootstrap"
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_bootstrap_seed_is_idempotent_for_existing_key():
    added = []
    project_id = uuid.uuid4()
    existing_key = MagicMock()
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_result(None),
            _scalar_result(None),
            _scalar_result(existing_key),
        ]
    )
    session.add.side_effect = added.append

    async def _flush():
        for item in added:
            if isinstance(item, Project):
                item.id = project_id

    session.flush = AsyncMock(side_effect=_flush)
    session.commit = AsyncMock()

    with patch("ragcore.bootstrap.settings") as s:
        s.BOOTSTRAP_API_KEY = "bootstrap-key-b"
        s.BOOTSTRAP_PROJECT_NAME = "bootstrap-project-b"
        s.BOOTSTRAP_API_KEY_LABEL = "bootstrap"
        await ensure_bootstrap_project_api_key(lambda: _session_factory(session))
        await ensure_bootstrap_project_api_key(lambda: _session_factory(session))

    assert len(added) == 2
    assert isinstance(added[0], Project)
    assert isinstance(added[1], APIKey)
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()
