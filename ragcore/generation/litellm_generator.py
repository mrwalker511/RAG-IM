from collections.abc import AsyncGenerator

import litellm

from ragcore.config import settings
from ragcore.generation.base import BaseLLMGenerator


class LiteLLMGenerator(BaseLLMGenerator):
    """Multi-provider LLM generator via LiteLLM (OpenAI, Anthropic, Azure, etc.)."""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or settings.LLM_MODEL

    async def generate(
        self,
        prompt: str,
        stream: bool = False,
    ) -> str | AsyncGenerator[str, None]:
        if stream:
            return self._stream(prompt)
        return await self._complete(prompt)

    async def _complete(self, prompt: str) -> str:
        response = await litellm.acompletion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        return response.choices[0].message.content or ""

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
