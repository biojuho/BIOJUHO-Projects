from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops" / "scripts"))

from pr_triage import (  # noqa: E402
    DiffStats,
    calculate_risk,
    classify_areas,
    evaluate_template_status,
    human_attention_reasons,
    infer_change_kind,
    is_docs_only,
    recommended_checks,
)


def test_classify_areas_detects_cross_cutting_paths() -> None:
    files = [
        "automation/DailyNews/scripts/run_daily_news.py",
        "packages/shared/llm/client.py",
        ".github/workflows/ci.yml",
    ]
    assert classify_areas(files) == ["DailyNews", "Shared", "GitHub"]


def test_docs_only_is_true_for_docs_and_markdown() -> None:
    files = [
        "docs/PR_TRIAGE_SYSTEM.md",
        ".github/pull_request_template.md",
    ]
    assert is_docs_only(files) is True


def test_infer_change_kind_prefers_docs_for_docs_only_pr() -> None:
    files = ["docs/PR_TRIAGE_SYSTEM.md"]
    areas = ["Docs"]
    assert infer_change_kind("docs: clarify triage", "", files, areas) == "docs"


def test_workflow_change_is_not_treated_as_docs_only() -> None:
    files = [".github/workflows/pr-triage.yml"]
    assert is_docs_only(files) is False
    assert infer_change_kind("ci: add triage", "", files, ["GitHub"]) == "infra"


def test_calculate_risk_marks_docs_only_as_low() -> None:
    risk = calculate_risk(
        files=["docs/PR_TRIAGE_SYSTEM.md"],
        areas=["Docs"],
        stats=DiffStats(files_changed=1, lines_added=40, lines_deleted=0),
        change_kind="docs",
    )
    assert risk == "low"


def test_calculate_risk_marks_shared_workflow_change_as_high() -> None:
    files = [
        "packages/shared/llm/client.py",
        "automation/DailyNews/src/antigravity_mcp/config.py",
        "automation/getdaytrends/main.py",
        ".github/workflows/ci.yml",
    ]
    risk = calculate_risk(
        files=files,
        areas=["DailyNews", "GetDayTrends", "Shared", "GitHub"],
        stats=DiffStats(files_changed=22, lines_added=500, lines_deleted=180),
        change_kind="infra",
    )
    assert risk == "high"


def test_template_status_reports_missing_sections_and_requests() -> None:
    body = """
## Plain-Language Intent
Fix publishing reliability for DailyNews.

## Human Judgment Needed
- [x] Architecture or scope decision needed
"""
    status = evaluate_template_status(body)
    assert "underlying_problem" in status.missing_sections
    assert "why_this_approach" in status.missing_sections
    assert status.requested_human_decisions == ["architecture_or_scope"]


def test_human_attention_reasons_reflect_template_and_risk() -> None:
    reasons = human_attention_reasons(
        files=[".github/workflows/ci.yml", "packages/shared/llm/client.py"],
        areas=["Shared", "GitHub", "DailyNews", "GetDayTrends"],
        stats=DiffStats(files_changed=30, lines_added=800, lines_deleted=200),
        template_status=evaluate_template_status(""),
        risk_level="high",
    )
    assert any("missing intention-first template sections" in reason.lower() for reason in reasons)
    assert any("ci or workflow automation changed" in reason.lower() for reason in reasons)
    assert any("high risk" in reason.lower() for reason in reasons)


def test_recommended_checks_include_workspace_smoke_for_shared_changes() -> None:
    checks = recommended_checks(["DailyNews", "Shared"], "feature", "medium")
    assert "workspace-smoke" in checks
    assert "automation/DailyNews targeted pytest or regression command" in checks
