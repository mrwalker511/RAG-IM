"""Tests for DOCX parser edge cases."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ragcore.ingestion.parsers.docx import DocxParser


def _make_doc(texts: list[str]):
    """Build a mock docx.Document with the given paragraph texts."""
    doc = MagicMock()
    paragraphs = []
    for text in texts:
        p = MagicMock()
        p.text = text
        paragraphs.append(p)
    doc.paragraphs = paragraphs
    return doc


def test_docx_parser_empty_document_returns_empty_list():
    mock_doc = _make_doc([])
    with patch("ragcore.ingestion.parsers.docx.docx.Document", return_value=mock_doc):
        result = DocxParser().parse(Path("fake.docx"))
    assert result == []


def test_docx_parser_whitespace_only_returns_empty_list():
    mock_doc = _make_doc(["   ", "", "\t"])
    with patch("ragcore.ingestion.parsers.docx.docx.Document", return_value=mock_doc):
        result = DocxParser().parse(Path("fake.docx"))
    assert result == []


def test_docx_parser_single_section():
    mock_doc = _make_doc(["Hello", "World"])
    with patch("ragcore.ingestion.parsers.docx.docx.Document", return_value=mock_doc):
        result = DocxParser().parse(Path("fake.docx"))
    assert len(result) == 1
    assert "Hello" in result[0]
    assert "World" in result[0]


def test_docx_parser_multiple_sections_split_by_blank():
    mock_doc = _make_doc(["Para 1", "", "Para 2"])
    with patch("ragcore.ingestion.parsers.docx.docx.Document", return_value=mock_doc):
        result = DocxParser().parse(Path("fake.docx"))
    assert len(result) == 2
    assert result[0] == "Para 1"
    assert result[1] == "Para 2"
