import hashlib
import time
from collections import defaultdict, deque

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from ragcore.config import settings
from ragcore.db.models import APIKey
from ragcore.db.session import AsyncSessionLocal

_EXEMPT_PATHS = {"/", "/docs", "/openapi.json", "/redoc", "/health"}

# In-memory sliding-window rate limiter: {key_hash: deque of request timestamps}
_rate_windows: dict[str, deque] = defaultdict(deque)


async def api_key_middleware(request: Request, call_next):
    if request.url.path in _EXEMPT_PATHS:
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

    request.state.api_key = api_key
    request.state.api_key_hash = key_hash
    return await call_next(request)


async def rate_limit_middleware(request: Request, call_next):
    """Sliding-window rate limiter keyed on the validated API key hash."""
    if request.url.path in _EXEMPT_PATHS or settings.RATE_LIMIT_PER_MINUTE == 0:
        return await call_next(request)

    # key_hash is populated by api_key_middleware which runs after this one,
    # so we derive it here from the raw header to keep middleware order simple.
    raw_key = request.headers.get("X-API-Key")
    if not raw_key:
        return await call_next(request)  # auth middleware will reject it

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    window = _rate_windows[key_hash]
    now = time.monotonic()
    cutoff = now - 60.0

    # Drop timestamps older than 1 minute
    while window and window[0] < cutoff:
        window.popleft()

    if len(window) >= settings.RATE_LIMIT_PER_MINUTE:
        retry_after = int(60 - (now - window[0])) + 1
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Try again later."},
            headers={"Retry-After": str(retry_after)},
        )

    window.append(now)
    return await call_next(request)
