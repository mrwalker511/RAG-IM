import re
from pathlib import Path

from ragcore.ingestion.parsers.base import BaseParser


class MarkdownParser(BaseParser):
    def parse(self, path: Path) -> list[str]:
        text = path.read_text(encoding="utf-8")
        # Split on top-level or second-level headings to form sections
        sections = re.split(r"\n(?=#{1,2} )", text)
        return [s.strip() for s in sections if s.strip()]
