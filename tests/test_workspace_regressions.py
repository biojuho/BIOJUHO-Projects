from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESCI_PATH = PROJECT_ROOT / "apps" / "desci-platform"
NOTION_SCRIPTS_PATH = PROJECT_ROOT / "automation" / "DailyNews" / "scripts"
NOTION_SERVER_PATH = PROJECT_ROOT / "automation" / "DailyNews" / "server.py"
DAILYNEWS_SRC_PATH = PROJECT_ROOT / "automation" / "DailyNews" / "src"

for candidate in (DESCI_PATH, NOTION_SCRIPTS_PATH, DAILYNEWS_SRC_PATH):
    candidate_text = str(candidate)
    if candidate_text not in sys.path:
        sys.path.insert(0, candidate_text)


def test_brain_module_robust_json_parse(monkeypatch) -> None:
    from antigravity_mcp.integrations.brain_adapter import _robust_json_parse

    assert _robust_json_parse('```json\n{"key":"value"}\n```') == {"key": "value"}
    assert _robust_json_parse('{"key":"value", }') == {"key": "value"}


def test_notion_server_reads_db_id_from_env() -> None:
    config_path = PROJECT_ROOT / "automation" / "DailyNews" / "src" / "antigravity_mcp" / "config.py"
    content = config_path.read_text(encoding="utf-8")
    assert "ANTIGRAVITY_DB_ID" in content


def test_getdaytrends_package_imports_from_repo_root() -> None:
    collectors = importlib.import_module("getdaytrends.collectors")
    generation = importlib.import_module("getdaytrends.generation")
    analyzer = importlib.import_module("getdaytrends.analyzer")
    db_module = importlib.import_module("getdaytrends.db")

    assert hasattr(collectors, "_async_collect_contexts")
    assert callable(generation.select_persona)
    assert callable(analyzer.analyze_trends)
    assert hasattr(db_module, "compute_fingerprint")


def test_getdaytrends_pipeline_modules_import_from_repo_root() -> None:
    scraper = importlib.import_module("getdaytrends.scraper")
    generator = importlib.import_module("getdaytrends.generator")
    storage = importlib.import_module("getdaytrends.storage")
    pipeline = importlib.import_module("getdaytrends.core.pipeline")
    pipeline_steps = importlib.import_module("getdaytrends.core.pipeline_steps")
    main_module = importlib.import_module("getdaytrends.main")
    canva = importlib.import_module("getdaytrends.canva")
    fact_checker = importlib.import_module("getdaytrends.fact_checker")
    prompts = importlib.import_module("getdaytrends.generation.prompts")

    assert callable(scraper.collect_trends)
    assert callable(generator.generate_for_trend_async)
    assert callable(storage.save_to_notion)
    assert callable(pipeline.run_pipeline)
    assert callable(pipeline_steps._step_generate)
    assert callable(main_module.parse_args)
    assert hasattr(canva, "CanvaMCPClient")
    assert callable(fact_checker.verify_content)
    assert hasattr(prompts, "_select_generation_tier")


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

    parser = PDFParser()
    result = parser.parse(b"dummy pdf content")
    assert result == "Page 1 Text\nPage 2 Text"


@patch("biolinker.services.pdf_parser.pypdf.PdfReader")
def test_pdf_parser_returns_empty_string_on_error(mock_reader_class: MagicMock) -> None:
    from biolinker.services.pdf_parser import PDFParser

    mock_reader_class.side_effect = Exception("Invalid PDF")
    parser = PDFParser()
    assert parser.parse(b"invalid content") == ""
