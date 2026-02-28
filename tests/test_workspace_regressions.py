from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESCI_PATH = PROJECT_ROOT / "desci-platform"
NOTION_SCRIPTS_PATH = PROJECT_ROOT / "MCP_notion-antigravity" / "scripts"
NOTION_SERVER_PATH = PROJECT_ROOT / "MCP_notion-antigravity" / "server.py"

for candidate in (DESCI_PATH, NOTION_SCRIPTS_PATH):
    candidate_text = str(candidate)
    if candidate_text not in sys.path:
        sys.path.insert(0, candidate_text)


def test_brain_module_robust_json_parse(monkeypatch) -> None:
    brain_module = importlib.import_module("brain_module")

    class DummyAnthropic:
        def __init__(self, api_key: str):
            self.api_key = api_key

    monkeypatch.setattr(brain_module.anthropic, "Anthropic", DummyAnthropic)
    monkeypatch.setattr(brain_module, "ANTHROPIC_API_KEY", "test-key")

    module = brain_module.BrainModule()
    assert module._robust_json_parse('```json\n{"key":"value"}\n```') == {"key": "value"}
    assert module._robust_json_parse('{"key":"value", }') == {"key": "value"}


def test_notion_server_reads_db_id_from_env() -> None:
    content = NOTION_SERVER_PATH.read_text(encoding="utf-8")
    assert 'ANTIGRAVITY_DB_ID = os.getenv("ANTIGRAVITY_DB_ID")' in content


@patch("biolinker.services.pdf_parser.pypdf.PdfReader")
def test_pdf_parser_extracts_page_text(mock_reader_class: MagicMock) -> None:
    from biolinker.services.pdf_parser import PDFParser

    mock_reader = MagicMock()
    page_1 = MagicMock()
    page_1.extract_text.return_value = "Page 1 Text"
    page_2 = MagicMock()
    page_2.extract_text.return_value = "Page 2 Text"
    mock_reader.pages = [page_1, page_2]
    mock_reader_class.return_value = mock_reader

    result = PDFParser.parse(b"dummy pdf content")
    assert result == "Page 1 Text\nPage 2 Text"


@patch("biolinker.services.pdf_parser.pypdf.PdfReader")
def test_pdf_parser_returns_empty_string_on_error(mock_reader_class: MagicMock) -> None:
    from biolinker.services.pdf_parser import PDFParser

    mock_reader_class.side_effect = Exception("Invalid PDF")
    assert PDFParser.parse(b"invalid content") == ""
