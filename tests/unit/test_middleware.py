"""Tests for api_key_middleware and Redis-backed rate_limit_middleware."""

import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from api.middleware import _check_rate_limit, api_key_middleware, rate_limit_middleware


def _mock_request(path: str = "/projects", api_key: str | None = "test-key") -> MagicMock:
    req = MagicMock()
    req.url.path = path
    req.headers.get = lambda k, default=None: api_key if k == "X-API-Key" else default
    req.state = MagicMock()
    return req


def _mock_session_factory(api_key_row):
    """Return a patched AsyncSessionLocal that yields a session returning api_key_row."""
    mock_session = AsyncMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = api_key_row
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


class FakeRedis:
    def __init__(self):
        self.windows: dict[str, list[tuple[str, int]]] = {}

    async def eval(self, script, numkeys, key, window_start, now_ms, limit, member, expiry_seconds):
        entries = self.windows.setdefault(key, [])
        entries[:] = [(m, score) for m, score in entries if score > int(window_start)]
        if len(entries) >= int(limit):
            oldest_score = min(score for _, score in entries)
            return [0, oldest_score]
        entries.append((member, int(now_ms)))
        return [1, 0]


# ---------------------------------------------------------------------------
# api_key_middleware
# ---------------------------------------------------------------------------

async def test_auth_exempt_path_passes_without_key():
    req = _mock_request(path="/health", api_key=None)
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    await api_key_middleware(req, call_next)
    call_next.assert_awaited_once_with(req)


async def test_auth_missing_key_returns_401():
    req = _mock_request(api_key=None)
    call_next = AsyncMock()
    response = await api_key_middleware(req, call_next)
    assert response.status_code == 401
    call_next.assert_not_awaited()


async def test_auth_invalid_key_returns_401():
    req = _mock_request(api_key="bad-key")
    call_next = AsyncMock()
    factory = _mock_session_factory(api_key_row=None)

    with patch("api.middleware.AsyncSessionLocal", factory):
        response = await api_key_middleware(req, call_next)

    assert response.status_code == 401
    call_next.assert_not_awaited()


async def test_auth_valid_key_calls_next_and_sets_state():
    project_id = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
    req = _mock_request(path=f"/projects/{project_id}/documents", api_key="good-key")
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    mock_api_key = MagicMock()
    mock_api_key.project_id = uuid.UUID(project_id)
    factory = _mock_session_factory(api_key_row=mock_api_key)

    with (
        patch("api.middleware.AsyncSessionLocal", factory),
        patch("api.middleware._is_bootstrap_key", return_value=False),
    ):
        await api_key_middleware(req, call_next)

    call_next.assert_awaited_once_with(req)
    assert req.state.api_key is mock_api_key


async def test_auth_root_projects_requires_bootstrap_key():
    req = _mock_request(path="/projects", api_key="project-key")
    call_next = AsyncMock()
    mock_api_key = MagicMock()
    factory = _mock_session_factory(api_key_row=mock_api_key)

    with (
        patch("api.middleware.AsyncSessionLocal", factory),
        patch("api.middleware._is_bootstrap_key", return_value=False),
    ):
        response = await api_key_middleware(req, call_next)

    assert response.status_code == 403
    call_next.assert_not_awaited()


async def test_auth_project_route_requires_matching_project_key():
    project_id = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
    req = _mock_request(path=f"/projects/{project_id}/documents", api_key="project-key")
    call_next = AsyncMock()
    mock_api_key = MagicMock()
    mock_api_key.project_id = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"
    factory = _mock_session_factory(api_key_row=mock_api_key)

    with (
        patch("api.middleware.AsyncSessionLocal", factory),
        patch("api.middleware._is_bootstrap_key", return_value=False),
    ):
        response = await api_key_middleware(req, call_next)

    assert response.status_code == 403
    call_next.assert_not_awaited()


# ---------------------------------------------------------------------------
# _check_rate_limit
# ---------------------------------------------------------------------------

async def test_check_rate_limit_allows_until_limit_then_blocks():
    fake_redis = FakeRedis()
    key_hash = hashlib.sha256(b"rate-limit-key-1").hexdigest()

    with patch("api.middleware.get_redis", return_value=fake_redis):
        allowed_1, retry_1 = await _check_rate_limit(key_hash, limit=2, now_ms=1_000)
        allowed_2, retry_2 = await _check_rate_limit(key_hash, limit=2, now_ms=2_000)
        allowed_3, retry_3 = await _check_rate_limit(key_hash, limit=2, now_ms=3_000)

    assert allowed_1 is True and retry_1 == 0
    assert allowed_2 is True and retry_2 == 0
    assert allowed_3 is False
    assert retry_3 > 0


async def test_check_rate_limit_windows_are_independent_per_key():
    fake_redis = FakeRedis()
    key_a = hashlib.sha256(b"key-a").hexdigest()
    key_b = hashlib.sha256(b"key-b").hexdigest()

    with patch("api.middleware.get_redis", return_value=fake_redis):
        assert await _check_rate_limit(key_a, limit=1, now_ms=1_000) == (True, 0)
        allowed_a, _ = await _check_rate_limit(key_a, limit=1, now_ms=2_000)
        allowed_b, _ = await _check_rate_limit(key_b, limit=1, now_ms=2_000)

    assert allowed_a is False
    assert allowed_b is True


async def test_check_rate_limit_reopens_after_window_expires():
    fake_redis = FakeRedis()
    key_hash = hashlib.sha256(b"rate-limit-key-2").hexdigest()

    with patch("api.middleware.get_redis", return_value=fake_redis):
        assert await _check_rate_limit(key_hash, limit=1, now_ms=1_000) == (True, 0)
        allowed_blocked, retry_after = await _check_rate_limit(key_hash, limit=1, now_ms=2_000)
        allowed_again, _ = await _check_rate_limit(key_hash, limit=1, now_ms=62_000)

    assert allowed_blocked is False
    assert retry_after > 0
    assert allowed_again is True


# ---------------------------------------------------------------------------
# rate_limit_middleware
# ---------------------------------------------------------------------------

async def test_rate_limit_exempt_path_always_passes():
    req = _mock_request(path="/health")
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    with patch("api.middleware.settings") as s:
        s.RATE_LIMIT_PER_MINUTE = 1
        await rate_limit_middleware(req, call_next)
    call_next.assert_awaited_once()


async def test_rate_limit_disabled_when_zero():
    req = _mock_request(api_key="any-key")
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    with patch("api.middleware.settings") as s:
        s.RATE_LIMIT_PER_MINUTE = 0
        await rate_limit_middleware(req, call_next)
    call_next.assert_awaited_once()


async def test_rate_limit_no_api_key_passes_to_auth():
    req = _mock_request(api_key=None)
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    with patch("api.middleware.settings") as s:
        s.RATE_LIMIT_PER_MINUTE = 1
        await rate_limit_middleware(req, call_next)
    call_next.assert_awaited_once()


async def test_rate_limit_returns_429_after_limit_exceeded():
    req = _mock_request(api_key="rate-limit-test-key-unique-001")
    call_next = AsyncMock(return_value=MagicMock(status_code=200))

    with (
        patch("api.middleware.settings") as s,
        patch("api.middleware._check_rate_limit", new=AsyncMock(side_effect=[(True, 0), (True, 0), (False, 42)])),
    ):
        s.RATE_LIMIT_PER_MINUTE = 2
        await rate_limit_middleware(req, call_next)
        await rate_limit_middleware(req, call_next)
        resp = await rate_limit_middleware(req, call_next)

    assert call_next.await_count == 2
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "42"


async def test_rate_limit_fail_open_on_redis_error():
    req = _mock_request(api_key="redis-down-key")
    call_next = AsyncMock(return_value=MagicMock(status_code=200))

    with (
        patch("api.middleware.settings") as s,
        patch("api.middleware._check_rate_limit", new=AsyncMock(side_effect=ConnectionError("Redis down"))),
    ):
        s.RATE_LIMIT_PER_MINUTE = 1
        response = await rate_limit_middleware(req, call_next)

    assert response.status_code == 200
    call_next.assert_awaited_once_with(req)
