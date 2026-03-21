from abc import ABC, abstractmethod
from pathlib import Path


class BaseParser(ABC):
    @abstractmethod
    def parse(self, path: Path) -> list[str]:
        """Return list of text pages/sections from the document at path."""
