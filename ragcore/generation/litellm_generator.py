import asyncio
import logging
from collections.abc import AsyncGenerator

import litellm
from litellm.exceptions import RateLimitError, ServiceUnavailableError, APIError

from ragcore.config import settings
from ragcore.generation.base import BaseLLMGenerator, GenerationResult

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0
_RETRYABLE = (RateLimitError, ServiceUnavailableError, APIError)


class LiteLLMGenerator(BaseLLMGenerator):
    """Multi-provider LLM generator via LiteLLM (OpenAI, Anthropic, Azure, etc.)."""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or settings.LLM_MODEL

    async def generate(
        self,
        prompt: str,
        stream: bool = False,
    ) -> GenerationResult | AsyncGenerator[str, None]:
        if stream:
            return self._stream(prompt)
        return await self._complete(prompt)

    async def _complete(self, prompt: str) -> GenerationResult:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = await litellm.acompletion(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=False,
                )
                text = response.choices[0].message.content or ""
                tokens_used = response.usage.total_tokens if response.usage else 0
                return GenerationResult(text=text, tokens_used=tokens_used)
            except _RETRYABLE as exc:
                last_exc = exc
                delay = _RETRY_BASE_DELAY * (2**attempt)
                logger.warning("LiteLLM generation failed (attempt %d/%d): %s. Retrying in %.1fs", attempt + 1, _MAX_RETRIES, exc, delay)
                await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]

    async def _stream(self, prompt: str) -> AsyncGenerator[str, None]:
        async def _gen():
            response = await litellm.acompletion(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

        return _gen()
