from pathlib import Path

from ragcore.ingestion.parsers.base import BaseParser


class TextParser(BaseParser):
    def parse(self, path: Path) -> list[str]:
        text = path.read_text(encoding="utf-8", errors="replace")
        return [text] if text.strip() else []
