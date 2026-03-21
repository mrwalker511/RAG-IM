from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass


@dataclass
class GenerationResult:
    text: str
    tokens_used: int


class BaseLLMGenerator(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        stream: bool = False,
    ) -> "GenerationResult | AsyncGenerator[str, None]":
        """Generate an answer from a prompt.

        Returns a GenerationResult when stream=False, or an async generator of
        string chunks when stream=True.
        """
