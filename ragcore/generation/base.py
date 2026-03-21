from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class BaseLLMGenerator(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        stream: bool = False,
    ) -> str | AsyncGenerator[str, None]:
        """Generate an answer from a prompt.

        Returns a string when stream=False, or an async generator of string
        chunks when stream=True.
        """
