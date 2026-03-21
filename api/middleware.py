import hashlib

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from ragcore.db.models import APIKey
from ragcore.db.session import AsyncSessionLocal

_EXEMPT_PATHS = {"/", "/docs", "/openapi.json", "/redoc", "/health"}


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

    if not api_key:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid API key"},
        )

    request.state.api_key = api_key
    return await call_next(request)
