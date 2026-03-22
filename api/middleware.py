import hashlib
import logging
import math
import secrets
import time
import uuid
from re import compile as re_compile

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from ragcore.config import settings
from ragcore.db.models import APIKey
from ragcore.db.redis import get_redis
from ragcore.db.session import AsyncSessionLocal

_EXEMPT_PATHS = {"/", "/docs", "/openapi.json", "/redoc", "/health"}
_EXEMPT_PREFIXES = ("/handbook",)
_RATE_LIMIT_WINDOW_SECONDS = 60
_PROJECT_PATH_RE = re_compile(r"^/projects/([^/]+)(?:/|$)")
_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local window_start = tonumber(ARGV[1])
local now_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
local expiry_seconds = tonumber(ARGV[5])

redis.call("ZREMRANGEBYSCORE", key, "-inf", window_start)
local count = redis.call("ZCARD", key)

if count >= limit then
  local oldest = redis.call("ZRANGE", key, 0, 0, "WITHSCORES")
  if oldest[2] then
    return {0, oldest[2]}
  end
  return {0, now_ms}
end

redis.call("ZADD", key, now_ms, member)
redis.call("EXPIRE", key, expiry_seconds)
return {1, 0}
"""
logger = logging.getLogger(__name__)


def _is_exempt_request(request: Request) -> bool:
    path = request.url.path
    return (
        request.method == "OPTIONS"
        or path in _EXEMPT_PATHS
        or any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES)
    )


def _is_bootstrap_key(raw_key: str) -> bool:
    bootstrap_key = settings.BOOTSTRAP_API_KEY.strip()
    return bool(bootstrap_key) and secrets.compare_digest(raw_key, bootstrap_key)


def _get_project_id_from_path(path: str) -> uuid.UUID | None:
    match = _PROJECT_PATH_RE.match(path)
    if not match:
        return None
    try:
        return uuid.UUID(match.group(1))
    except ValueError:
        return None


async def _check_rate_limit(key_hash: str, limit: int, now_ms: int | None = None) -> tuple[bool, int]:
    current_ms = now_ms or int(time.time() * 1000)
    window_start = current_ms - (_RATE_LIMIT_WINDOW_SECONDS * 1000)
    member = f"{current_ms}:{time.monotonic_ns()}"
    redis = get_redis()
    result = await redis.eval(
        _RATE_LIMIT_SCRIPT,
        1,
        f"rate_limit:{key_hash}",
        window_start,
        current_ms,
        limit,
        member,
        _RATE_LIMIT_WINDOW_SECONDS,
    )

    allowed = int(result[0]) == 1
    if allowed:
        return True, 0

    oldest_ms = int(float(result[1]))
    retry_after = max(
        1,
        math.ceil(((_RATE_LIMIT_WINDOW_SECONDS * 1000) - (current_ms - oldest_ms)) / 1000),
    )
    return False, retry_after


async def api_key_middleware(request: Request, call_next):
    if _is_exempt_request(request):
        return await call_next(request)

    key = request.headers.get("X-API-Key")
    if not key:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing X-API-Key header"},
        )

    key_hash = hashlib.sha256(key.encode()).hexdigest()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(APIKey).where(APIKey.key_hash == key_hash))
        api_key = result.scalar_one_or_none()
        if hasattr(api_key, "__await__"):
            api_key = await api_key

    if not api_key:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid API key"},
        )

    is_bootstrap = _is_bootstrap_key(key)
    project_id = _get_project_id_from_path(request.url.path)
    if request.url.path == "/projects" and not is_bootstrap:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Bootstrap API key required"},
        )
    if project_id is not None and not is_bootstrap and api_key.project_id != project_id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "API key is not authorized for this project"},
        )

    request.state.api_key = api_key
    request.state.api_key_hash = key_hash
    return await call_next(request)


async def rate_limit_middleware(request: Request, call_next):
    """Shared sliding-window rate limiter keyed on the validated API key hash."""
    if _is_exempt_request(request) or settings.RATE_LIMIT_PER_MINUTE == 0:
        return await call_next(request)

    # key_hash is populated by api_key_middleware which runs after this one,
    # so we derive it here from the raw header to keep middleware order simple.
    raw_key = request.headers.get("X-API-Key")
    if not raw_key:
        return await call_next(request)  # auth middleware will reject it

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    try:
        allowed, retry_after = await _check_rate_limit(key_hash, settings.RATE_LIMIT_PER_MINUTE)
    except Exception:
        logger.warning("Redis rate-limit check failed; allowing request", exc_info=True)
        return await call_next(request)

    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Try again later."},
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)
