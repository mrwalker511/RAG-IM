import io
import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Text parser
# ---------------------------------------------------------------------------

def test_text_parser(tmp_path):
    from ragcore.ingestion.parsers.text import TextParser
    f = tmp_path / "sample.txt"
    f.write_text("Hello world.\nSecond line.", encoding="utf-8")
    result = TextParser().parse(f)
    assert len(result) == 1
    assert "Hello world" in result[0]


def test_text_parser_empty_file(tmp_path):
    from ragcore.ingestion.parsers.text import TextParser
    f = tmp_path / "empty.txt"
    f.write_text("   ", encoding="utf-8")
    assert TextParser().parse(f) == []


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

def test_markdown_parser_splits_on_headings(tmp_path):
    from ragcore.ingestion.parsers.markdown import MarkdownParser
    f = tmp_path / "doc.md"
    f.write_text("# Section One\nContent one.\n\n## Section Two\nContent two.", encoding="utf-8")
    result = MarkdownParser().parse(f)
    assert len(result) >= 2


def test_markdown_parser_single_block(tmp_path):
    from ragcore.ingestion.parsers.markdown import MarkdownParser
    f = tmp_path / "doc.md"
    f.write_text("Just plain text without headings.", encoding="utf-8")
    result = MarkdownParser().parse(f)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# PDF parser (creates a minimal valid PDF in-memory via pypdf)
# ---------------------------------------------------------------------------

def test_pdf_parser(tmp_path):
    pytest.importorskip("pypdf")
    from pypdf import PdfWriter
    from ragcore.ingestion.parsers.pdf import PDFParser

    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    pdf_path = tmp_path / "test.pdf"
    with open(pdf_path, "wb") as f:
        writer.write(f)

    # Blank page has no text — parser should return empty list
    result = PDFParser().parse(pdf_path)
    assert isinstance(result, list)
