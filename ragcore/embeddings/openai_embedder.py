import asyncio

from openai import AsyncOpenAI

from ragcore.config import settings
from ragcore.embeddings.base import BaseEmbedder

_BATCH_SIZE = 100
_MAX_RETRIES = 3
_RETRY_DELAY = 1.0


class OpenAIEmbedder(BaseEmbedder):
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self._model = model or settings.EMBEDDING_MODEL
        self._client = AsyncOpenAI(api_key=api_key or settings.OPENAI_API_KEY)

    @property
    def dimension(self) -> int:
        return settings.EMBEDDING_DIM

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            vectors.extend(await self._embed_batch(batch))
        return vectors

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(_MAX_RETRIES):
            try:
                response = await self._client.embeddings.create(
                    input=texts,
                    model=self._model,
                )
                return [item.embedding for item in response.data]
            except Exception:
                if attempt == _MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(_RETRY_DELAY * (2**attempt))
        return []  # unreachable
