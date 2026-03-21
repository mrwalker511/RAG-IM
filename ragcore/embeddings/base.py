from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return a list of embedding vectors, one per input text."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension."""
