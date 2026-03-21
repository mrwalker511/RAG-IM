from pathlib import Path

import docx

from ragcore.ingestion.parsers.base import BaseParser


class DocxParser(BaseParser):
    def parse(self, path: Path) -> list[str]:
        doc = docx.Document(str(path))
        sections: list[str] = []
        current: list[str] = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                if current:
                    sections.append("\n".join(current))
                    current = []
            else:
                current.append(text)
        if current:
            sections.append("\n".join(current))
        return sections
