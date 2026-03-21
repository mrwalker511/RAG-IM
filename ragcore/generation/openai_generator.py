from collections.abc import AsyncGenerator
from dataclasses import dataclass

from openai import AsyncOpenAI

from ragcore.config import settings
from ragcore.generation.base import BaseLLMGenerator


@dataclass
class GenerationResult:
    text: str
    tokens_used: int


class OpenAIGenerator(BaseLLMGenerator):
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self._model = model or settings.LLM_MODEL
        self._client = AsyncOpenAI(api_key=api_key or settings.OPENAI_API_KEY)

    async def generate(
        self,
        prompt: str,
        stream: bool = False,
    ) -> str | AsyncGenerator[str, None]:
        if stream:
            return self._stream(prompt)
        return await self._complete(prompt)

    async def _complete(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        return response.choices[0].message.content or ""

    async def _stream(self, prompt: str) -> AsyncGenerator[str, None]:
        async def _gen():
            async with await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            ) as response:
                async for chunk in response:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta

        return _gen()
