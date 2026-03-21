"""Tests for api_key_middleware and rate_limit_middleware."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.middleware import _rate_windows, api_key_middleware, rate_limit_middleware


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
    factory = _mock_session_factory(api_key_row=None)  # DB finds nothing

    with patch("api.middleware.AsyncSessionLocal", factory):
        response = await api_key_middleware(req, call_next)

    assert response.status_code == 401
    call_next.assert_not_awaited()


async def test_auth_valid_key_calls_next_and_sets_state():
    req = _mock_request(api_key="good-key")
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    mock_api_key = MagicMock()
    factory = _mock_session_factory(api_key_row=mock_api_key)

    with patch("api.middleware.AsyncSessionLocal", factory):
        await api_key_middleware(req, call_next)

    call_next.assert_awaited_once_with(req)
    assert req.state.api_key is mock_api_key


# ---------------------------------------------------------------------------
# rate_limit_middleware
# ---------------------------------------------------------------------------

async def test_rate_limit_exempt_path_always_passes():
    req = _mock_request(path="/health")
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    with patch("api.middleware.settings") as s:
        s.RATE_LIMIT_PER_MINUTE = 1
        s.CORS_ORIGINS = "*"
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
    """Missing key is not rate-limited — auth middleware handles rejection."""
    req = _mock_request(api_key=None)
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    with patch("api.middleware.settings") as s:
        s.RATE_LIMIT_PER_MINUTE = 1
        await rate_limit_middleware(req, call_next)
    call_next.assert_awaited_once()


async def test_rate_limit_returns_429_after_limit_exceeded():
    key = "rate-limit-test-key-unique-001"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    _rate_windows.pop(key_hash, None)  # ensure clean state

    req = _mock_request(api_key=key)
    call_next = AsyncMock(return_value=MagicMock(status_code=200))

    try:
        with patch("api.middleware.settings") as s:
            s.RATE_LIMIT_PER_MINUTE = 2

            r1 = await rate_limit_middleware(req, call_next)
            r2 = await rate_limit_middleware(req, call_next)
            r3 = await rate_limit_middleware(req, call_next)

        assert call_next.await_count == 2
        assert r3.status_code == 429
    finally:
        _rate_windows.pop(key_hash, None)


async def test_rate_limit_429_includes_retry_after_header():
    key = "rate-limit-test-key-unique-002"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    _rate_windows.pop(key_hash, None)

    req = _mock_request(api_key=key)
    call_next = AsyncMock(return_value=MagicMock(status_code=200))

    try:
        with patch("api.middleware.settings") as s:
            s.RATE_LIMIT_PER_MINUTE = 1

            await rate_limit_middleware(req, call_next)   # allowed
            resp = await rate_limit_middleware(req, call_next)  # blocked

        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        assert int(resp.headers["Retry-After"]) > 0
    finally:
        _rate_windows.pop(key_hash, None)


async def test_rate_limit_different_keys_have_independent_windows():
    key_a = "rate-key-a-unique-003"
    key_b = "rate-key-b-unique-003"
    hash_a = hashlib.sha256(key_a.encode()).hexdigest()
    hash_b = hashlib.sha256(key_b.encode()).hexdigest()
    _rate_windows.pop(hash_a, None)
    _rate_windows.pop(hash_b, None)

    call_next = AsyncMock(return_value=MagicMock(status_code=200))

    try:
        with patch("api.middleware.settings") as s:
            s.RATE_LIMIT_PER_MINUTE = 1

            req_a = _mock_request(api_key=key_a)
            req_b = _mock_request(api_key=key_b)

            await rate_limit_middleware(req_a, call_next)  # key_a: 1/1 used
            resp_a = await rate_limit_middleware(req_a, call_next)  # key_a: blocked
            resp_b = await rate_limit_middleware(req_b, call_next)  # key_b: first request, allowed

        assert resp_a.status_code == 429
        assert resp_b.status_code == 200
    finally:
        _rate_windows.pop(hash_a, None)
        _rate_windows.pop(hash_b, None)
