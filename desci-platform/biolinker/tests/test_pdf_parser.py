"""
Unit tests for the PDF parser abstraction and GROBID fallback behavior.
"""
from __future__ import annotations

from types import SimpleNamespace

import services.pdf_parser as pdf_parser_module


def test_parse_document_prefers_grobid_when_available(monkeypatch):
    """Structured GROBID output should be used when available."""
    stub_grobid = SimpleNamespace(
        is_configured=True,
        parse_document=lambda content, filename="document.pdf": SimpleNamespace(
            text="Structured full text",
            metadata={"title": "Structured Title", "doi": "10.1000/test"},
            tei_xml="<TEI />",
        ),
    )
    monkeypatch.setattr(pdf_parser_module, "get_grobid_parser", lambda: stub_grobid)

    parser = pdf_parser_module.PDFParser()
    result = parser.parse_document(b"%PDF-1.4 test", filename="paper.pdf")

    assert result.parser == "grobid"
    assert result.text == "Structured full text"
    assert result.metadata["title"] == "Structured Title"


def test_parse_document_falls_back_to_pypdf(monkeypatch):
    """When GROBID is unavailable, pypdf should still provide a result."""
    stub_grobid = SimpleNamespace(
        is_configured=True,
        parse_document=lambda content, filename="document.pdf": None,
    )
    monkeypatch.setattr(pdf_parser_module, "get_grobid_parser", lambda: stub_grobid)
    monkeypatch.setattr(
        pdf_parser_module.PDFParser,
        "_parse_with_pypdf",
        staticmethod(lambda content: "Fallback text"),
    )
    monkeypatch.setattr(
        pdf_parser_module.PDFParser,
        "_extract_metadata_with_pypdf",
        staticmethod(lambda content: {"source": "pypdf"}),
    )

    parser = pdf_parser_module.PDFParser()
    result = parser.parse_document(b"%PDF-1.4 test", filename="paper.pdf")

    assert result.parser == "pypdf"
    assert result.text == "Fallback text"
    assert result.metadata["source"] == "pypdf"
