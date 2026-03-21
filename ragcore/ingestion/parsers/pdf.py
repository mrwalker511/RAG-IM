from pathlib import Path

import pypdf

from ragcore.ingestion.parsers.base import BaseParser


class PDFParser(BaseParser):
    def parse(self, path: Path) -> list[str]:
        pages: list[str] = []
        with open(path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(text)
        return pages
