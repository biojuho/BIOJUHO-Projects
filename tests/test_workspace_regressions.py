from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESCI_PATH = PROJECT_ROOT / "apps" / "desci-platform"
NOTION_SCRIPTS_PATH = PROJECT_ROOT / "automation" / "DailyNews" / "scripts"
DAILYNEWS_SRC_PATH = PROJECT_ROOT / "automation" / "DailyNews" / "src"
HEALTHCHECK_PATH = PROJECT_ROOT / "ops" / "scripts" / "healthcheck.py"

for candidate in (DESCI_PATH, NOTION_SCRIPTS_PATH, DAILYNEWS_SRC_PATH):
    candidate_text = str(candidate)
    if candidate_text not in sys.path:
        sys.path.insert(0, candidate_text)

_OPTIONAL_MEMBER_DEPENDENCIES = {
    "aiohttp",
    "anthropic",
    "firebase_admin",
    "google",
    "gspread",
    "httpx",
    "instructor",
    "loguru",
    "notion_client",
    "openai",
    "scrapling",
    "selectolax",
    "slowapi",
    "web3",
}


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _expect_equal(actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")


def _import_workspace_module(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        missing_root = (exc.name or "").split(".")[0]
        if missing_root in _OPTIONAL_MEMBER_DEPENDENCIES:
            pytest.skip(
                f"{module_name} requires optional workspace dependency '{exc.name}' that is not installed in the root test env"
            )
        raise


def test_brain_module_robust_json_parse(monkeypatch) -> None:
    from antigravity_mcp.integrations.brain_adapter import _robust_json_parse

    _expect_equal(_robust_json_parse('```json\n{"key":"value"}\n```'), {"key": "value"})
    _expect_equal(_robust_json_parse('{"key":"value", }'), {"key": "value"})


def test_notion_server_reads_db_id_from_env() -> None:
    config_path = PROJECT_ROOT / "automation" / "DailyNews" / "src" / "antigravity_mcp" / "config.py"
    content = config_path.read_text(encoding="utf-8")
    _expect("ANTIGRAVITY_DB_ID" in content, "DailyNews config should read ANTIGRAVITY_DB_ID")


def test_healthcheck_tracks_dailynews_canonical_server_path() -> None:
    spec = importlib.util.spec_from_file_location("healthcheck_under_test", HEALTHCHECK_PATH)
    _expect(spec is not None and spec.loader is not None, "healthcheck module spec should load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    dailynews = next(project for project in module.CHECKS if project["name"] == "DailyNews")
    _expect_equal(dailynews["checks"], [("server", "automation/DailyNews/src/antigravity_mcp/server.py")])


def test_getdaytrends_package_imports_from_repo_root() -> None:
    collectors = _import_workspace_module("getdaytrends.collectors")
    generation = _import_workspace_module("getdaytrends.generation")
    analyzer = _import_workspace_module("getdaytrends.analyzer")
    db_module = _import_workspace_module("getdaytrends.db")

    _expect(hasattr(collectors, "_async_collect_contexts"), "collectors should expose async context collection")
    _expect(callable(generation.select_persona), "generation.select_persona should be callable")
    _expect(callable(analyzer.analyze_trends), "analyzer.analyze_trends should be callable")
    _expect(hasattr(db_module, "compute_fingerprint"), "db module should expose compute_fingerprint")


def test_getdaytrends_pipeline_modules_import_from_repo_root() -> None:
    scraper = _import_workspace_module("getdaytrends.scraper")
    generator = _import_workspace_module("getdaytrends.generator")
    storage = _import_workspace_module("getdaytrends.storage")
    pipeline = _import_workspace_module("getdaytrends.core.pipeline")
    pipeline_steps = _import_workspace_module("getdaytrends.core.pipeline_steps")
    main_module = _import_workspace_module("getdaytrends.main")
    canva = _import_workspace_module("getdaytrends.canva")
    fact_checker = _import_workspace_module("getdaytrends.fact_checker")
    prompts = _import_workspace_module("getdaytrends.generation.prompts")

    _expect(callable(scraper.collect_trends), "scraper.collect_trends should be callable")
    _expect(callable(generator.generate_for_trend_async), "generator.generate_for_trend_async should be callable")
    _expect(callable(storage.save_to_notion), "storage.save_to_notion should be callable")
    _expect(callable(pipeline.run_pipeline), "pipeline.run_pipeline should be callable")
    _expect(callable(pipeline_steps._step_generate), "pipeline_steps._step_generate should be callable")
    _expect(callable(main_module.parse_args), "main.parse_args should be callable")
    _expect(hasattr(canva, "CanvaMCPClient"), "canva module should expose CanvaMCPClient")
    _expect(callable(fact_checker.verify_content), "fact_checker.verify_content should be callable")
    _expect(hasattr(prompts, "_select_generation_tier"), "prompts should expose _select_generation_tier")


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
    _expect_equal(result, "Page 1 Text\nPage 2 Text")


@patch("biolinker.services.pdf_parser.pypdf.PdfReader")
def test_pdf_parser_returns_empty_string_on_error(mock_reader_class: MagicMock) -> None:
    from biolinker.services.pdf_parser import PDFParser

    mock_reader_class.side_effect = Exception("Invalid PDF")
    parser = PDFParser()
    _expect_equal(parser.parse(b"invalid content"), "")
