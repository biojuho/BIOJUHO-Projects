from __future__ import annotations

import errno
import importlib.util
import json
import os
import re
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "run_workspace_smoke.py"
COMPILE_HELPER_PATH = PROJECT_ROOT / "ops" / "scripts" / "compile_workspace_paths.py"
QUALITY_GATE_PATH = PROJECT_ROOT / "docs" / "QUALITY_GATE.md"
HANDOFF_PATH = PROJECT_ROOT / "HANDOFF.md"
PRODUCT_READINESS_PROGRESS_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-05" / "PRODUCT_READINESS_PROGRESS_2026-05-28.md"
DASHBOARD_CSS_PATH = PROJECT_ROOT / "apps" / "dashboard" / "src" / "index.css"
DASHBOARD_BUILD_SCRIPT_PATH = PROJECT_ROOT / "apps" / "dashboard" / "scripts" / "build.mjs"


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("workspace_smoke", SMOKE_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_compile_helper_module():
    spec = importlib.util.spec_from_file_location("compile_workspace_paths", COMPILE_HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_quality_gate_documents_all_supported_scopes() -> None:
    quality_gate = QUALITY_GATE_PATH.read_text(encoding="utf-8")

    for scope in ("all", "workspace", "desci", "agriguard", "mcp", "dailynews", "getdaytrends", "cie"):
        assert f"--scope {scope}" in quality_gate


def test_quality_gate_documents_incremental_json_evidence() -> None:
    quality_gate = QUALITY_GATE_PATH.read_text(encoding="utf-8")
    normalized_quality_gate = quality_gate.replace("\n", " ")

    assert "refreshes the JSON report after each" in quality_gate
    assert "partial evidence" in quality_gate
    assert "atomically" in quality_gate
    assert "schema_version: 1" in quality_gate
    assert "`partial` or" in quality_gate
    assert "session_bootstrap.py" in quality_gate
    assert "generate_context_snapshot.py" in quality_gate
    assert "legacy array reports" in quality_gate
    assert "boolean `ok` field" in quality_gate
    assert "at least one result" in quality_gate
    assert "malformed legacy arrays" in quality_gate
    assert "empty legacy arrays" in quality_gate
    assert "var/workspace-smoke*.json" in quality_gate
    assert "newest valid smoke" in quality_gate
    assert "file modification time" in quality_gate
    assert "caller-provided candidate order" in quality_gate
    assert "shared reader is also responsible for collecting" in quality_gate
    assert "ignoring matching directories or other non-file candidates" in quality_gate
    assert "`workspace-smoke-workspace*.json` reports over newer focused app-scope smoke" in normalized_quality_gate
    assert "nonnegative `elapsed_ms` timing" in normalized_quality_gate
    assert "`elapsed_ms_total` plus `slowest_results`" in normalized_quality_gate
    assert "final terminal summary" in quality_gate
    assert "slowest-check timing" in quality_gate
    assert "backward-compatible `latest_smoke` display" in quality_gate
    assert "structured `latest_smoke_evidence` metadata" in quality_gate
    assert "`elapsed_ms_total` and `slowest_results` metadata" in normalized_quality_gate
    assert "`elapsed=...; slowest=...` suffix" in quality_gate
    assert "`N/N PASS` compatibility shape" in quality_gate
    assert "`status` (`valid`, `corrupt`, or `missing`)" in quality_gate
    assert "report `path`/`name`, `passed`, `total`" in quality_gate
    assert "`schema_version` is not" in quality_gate
    assert "`schema_version` is a boolean" in quality_gate
    assert "`generated_at` is not parseable" in quality_gate
    assert "`generated_at` is missing a timezone offset" in quality_gate
    assert "`status` is missing" in quality_gate
    assert "top-level `summary` object or `results` array is" in quality_gate
    assert "`summary.total` or `summary.completed` is zero" in quality_gate
    assert "summary counts are inconsistent" in quality_gate
    assert "`status` contradicts remaining check counts" in quality_gate
    assert "`results[]` entries are missing required result fields" in quality_gate
    assert "are not objects with" in quality_gate
    assert "boolean `ok` values" in quality_gate
    assert "trace fields (`scope`, `name`, `cwd`, `command`) are" in quality_gate
    assert "`scope` is not a known canonical smoke scope" in quality_gate
    assert "`results[].ok` values contradict their" in quality_gate
    assert "`returncode`" in quality_gate
    assert "`results[].elapsed_ms` is not a nonnegative integer" in normalized_quality_gate
    assert "summary.elapsed_ms_total" in quality_gate
    assert "summary.slowest_results" in quality_gate
    assert "session bootstrap/context snapshot consumers" in quality_gate
    assert "`results[].ok` pass/fail counts contradict" in quality_gate
    assert "`summary.failed`" in quality_gate
    assert "release_approval_check.py" in quality_gate
    assert "--markdown-out" in quality_gate
    assert "RELEASE_APPROVAL_OPERATOR_HANDOFF" in quality_gate
    assert "GITHUB_STEP_SUMMARY" in quality_gate
    assert "--release-approval-handoff" in quality_gate
    assert "release-approval-handoff" in quality_gate
    assert "fails closed" in quality_gate
    assert "does not make expected external blockers pass" in normalized_quality_gate
    assert "writes a schema v1 JSON object" in quality_gate
    assert "writes an array of objects" not in quality_gate


def test_quality_gate_release_approval_machine_wrapper_exists() -> None:
    quality_gate = QUALITY_GATE_PATH.read_text(encoding="utf-8")
    wrapper = PROJECT_ROOT / "ops" / "scripts" / "run_release_approval_gate_machine.ps1"

    assert "run_release_approval_gate_machine.ps1" in quality_gate
    assert wrapper.exists()

    source = wrapper.read_text(encoding="utf-8")
    for marker in (
        "run_workspace_smoke.py",
        "release_approval_check.py",
        "session_bootstrap.py",
        "--markdown-out",
        "RELEASE_APPROVAL_OPERATOR_HANDOFF",
        "GITHUB_STEP_SUMMARY",
        "AppendGitHubStepSummary",
    ):
        assert marker in source
        assert marker in quality_gate

    for marker in ("workflow_dispatch", "release_approval_handoff"):
        assert marker in quality_gate
    assert "write_release_approval_handoff_artifact_index.py" in quality_gate
    assert "release-approval-handoff-artifact-index-machine.json" in quality_gate
    assert "release-approval-handoff-artifact-index-summary.md" in quality_gate
    assert "upload_before_fail_closed" in quality_gate
    assert "desci-release-gate-release-approval-handoff-machine.json" in quality_gate
    assert "--release-approval-handoff" in quality_gate

    assert "Invoke-Expression" not in source


def test_quality_gate_documents_default_check_names() -> None:
    smoke = load_smoke_module()
    quality_gate = QUALITY_GATE_PATH.read_text(encoding="utf-8")
    inventory = quality_gate.split("## Smoke Check Inventory", 1)[1].split(
        "Python compile checks use `ops/scripts/compile_workspace_paths.py`", 1
    )[0]
    documented_check_names = {
        line.removeprefix("- `").removesuffix("`")
        for line in inventory.splitlines()
        if line.startswith("- `") and line.endswith("`")
    }

    assert documented_check_names == {check.name for check in smoke.default_checks("python")}


def test_quality_gate_documents_compile_excludes() -> None:
    quality_gate = QUALITY_GATE_PATH.read_text(encoding="utf-8")

    for excluded in (
        ".agent",
        ".agents",
        ".venv",
        "venv",
        "__pycache__",
        "output",
        "archive",
        "var",
        ".pytest-temp-verify",
        ".pytest-root",
        ".pytest_cache",
        ".smoke-tmp",
        ".mypy_cache",
        ".ruff_cache",
    ):
        assert f"- `{excluded}`" in quality_gate


def test_compile_helper_prunes_transient_directories(tmp_path) -> None:
    helper = load_compile_helper_module()
    source_dir = tmp_path / "src"
    excluded_dir = source_dir / ".smoke-tmp"
    source_dir.mkdir()
    excluded_dir.mkdir()
    (source_dir / "ok.py").write_text("VALUE = 1\n", encoding="utf-8")
    (excluded_dir / "bad.py").write_text("def broken(:\n", encoding="utf-8")

    assert helper.compile_targets([source_dir]) == 0


def test_quality_gate_documents_desci_release_readiness_coverage() -> None:
    smoke = load_smoke_module()
    quality_gate = QUALITY_GATE_PATH.read_text(encoding="utf-8")
    assert "\n\n- `agriguard`" in quality_gate
    section = quality_gate.split("DeSci release-readiness pytest files:", 1)[1].split("\n\n- `agriguard`", 1)[0]
    documented_tests = [
        line.removeprefix("- `").removesuffix("`")
        for line in section.splitlines()
        if line.startswith("- `") and line.endswith("`")
    ]
    expected_tests = [
        f"apps/desci-platform/backend/tests/{test_file}" for test_file in smoke.DESCI_RELEASE_READINESS_TESTS
    ]

    assert "production auth and LLM fallback policy" in quality_gate
    assert "worker bootstrap/dispatch behavior" in quality_gate
    assert "operator JSON evidence contract coverage" in quality_gate
    assert "atomic `--json-out` writers" in quality_gate
    assert "dry-run artifact validation skip semantics" in quality_gate
    assert "- `agriguard`" not in section
    assert all(test.startswith("apps/desci-platform/backend/tests/") for test in documented_tests)
    assert documented_tests == expected_tests


def test_dashboard_css_uses_plain_css_for_vite_build() -> None:
    dashboard_css = DASHBOARD_CSS_PATH.read_text(encoding="utf-8")
    dashboard_build_script = DASHBOARD_BUILD_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "@extend" not in dashboard_css
    assert "Backward-compat alias styles live in section 20." in dashboard_css
    assert ".refresh-btn" in dashboard_css
    assert 'encoding: "utf8"' in dashboard_build_script
    assert "Unknown at rule" in dashboard_build_script
    assert "CSS compiler warning detected; failing build." in dashboard_build_script
    assert 'stdio: "inherit"' not in dashboard_build_script
    assert "treating build as successful" not in dashboard_build_script
    assert "existsSync" not in dashboard_build_script


def test_dashboard_build_script_fails_css_compiler_warnings(tmp_path: Path) -> None:
    _write_fake_vite(
        tmp_path,
        """
        console.error("Unknown at rule: @extend");
        process.exit(0);
        """,
    )

    result = _run_dashboard_build_script(tmp_path)

    assert result.returncode == 1
    assert "CSS compiler warning detected; failing build." in result.stderr


def test_dashboard_build_script_fails_nonzero_vite_exit_even_with_dist(tmp_path: Path) -> None:
    (tmp_path / "dist" / "assets").mkdir(parents=True)
    (tmp_path / "dist" / "index.html").write_text("<!doctype html>", encoding="utf-8")
    _write_fake_vite(
        tmp_path,
        """
        console.error("vite failed after emitting dist");
        process.exit(7);
        """,
    )

    result = _run_dashboard_build_script(tmp_path)

    assert result.returncode == 7
    assert "vite failed after emitting dist" in result.stderr
    assert "treating build as successful" not in result.stderr


def _write_fake_vite(cwd: Path, source: str) -> None:
    fake_vite = cwd / "node_modules" / "vite" / "bin" / "vite.js"
    fake_vite.parent.mkdir(parents=True)
    fake_vite.write_text(source, encoding="utf-8")


def _run_dashboard_build_script(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(DASHBOARD_BUILD_SCRIPT_PATH)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_handoff_current_baseline_matches_product_readiness_gate() -> None:
    handoff = HANDOFF_PATH.read_text(encoding="utf-8")
    current_section = handoff.split("### System completion audit refresh", 1)[1].split(
        "## Current State (2026-06-04)", 1
    )[0]
    product_readiness_section = handoff.split("## Current State (2026-05-28)", 1)[1].split(
        "## Current State (2026-05-20)", 1
    )[0]

    updated_match = re.search(r"\*\*Last Updated\*\*: (?P<date>\d{4}-\d{2}-\d{2})", handoff)
    assert updated_match
    assert updated_match.group("date") >= "2026-06-06"
    assert "AUTO_RESEARCH_DASHBOARD_LIVE_SOURCE_STATUS_2026-06-06.md" in handoff
    assert "previous freshness-only split canonical smoke was 35/35 PASS" in handoff
    assert "latest strict getdaytrends launch rerun is `3/4 PASS`" in handoff
    for artifact in (
        "var/workspace-smoke-workspace-2026-06-05-dailynews-x-canonical-refresh.json",
        "var/workspace-smoke-desci-2026-06-05-dailynews-x-canonical-refresh.json",
        "var/workspace-smoke-agriguard-2026-06-05-dailynews-x-canonical-refresh.json",
        "var/workspace-smoke-mcp-dailynews-x-browser-2026-06-05.json",
        "var/workspace-smoke-getdaytrends-2026-06-05-cli-smoke-freshness.json",
        "var/workspace-smoke-getdaytrends-2026-06-05-runtime-fallback-gate.json",
        "var/workspace-smoke-cie-2026-06-05-dailynews-x-canonical-refresh.json",
    ):
        assert artifact in current_section
    assert "Previous freshness-only deterministic gate coverage: 35/35 PASS" in current_section
    assert "Current launch-grade getdaytrends gate status: blocked" in current_section
    assert "getdaytrends launch readiness gate" in current_section
    assert "AUTO_RESEARCH_GETDAYTRENDS_SCHEDULER_REMEDIATION_HINT_2026-06-05.md" in current_section
    assert "AUTO_RESEARCH_GETDAYTRENDS_RUNTIME_FALLBACK_GATE_2026-06-05.md" in current_section
    assert "logs/smoke/dashboard_browser_runtime_fallback_gate.json" in current_section
    assert "AUTO_RESEARCH_DAILYNEWS_X_OPS_BROWSER_SMOKE_2026-06-05.md" in current_section
    assert "var/dailynews-x-ops-browser-smoke-mcp.json" in current_section
    assert "SYSTEM_COMPLETION_AUDIT_2026-06-05.md" in current_section
    assert "AUTO_RESEARCH_MCP_TRACE_LIVE_USAGE_EMISSION_2026-06-05.md" in current_section
    assert "AUTO_RESEARCH_OPERATOR_STATUS_2026-06-05.md" in current_section
    assert "MCP_SMOKE_TRACE_USAGE_SIDECAR_2026-06-05.md" in current_section
    assert "total tokens `155`" in current_section
    assert "Focused sidecar/trace/proxy regression: `23 passed`" in current_section
    assert "GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-05.md" in current_section
    assert "var/github-modernization-radar-2026-06-05.json" in current_section
    assert "var/github-modernization-radar-auto-research.json" in current_section
    assert "Current radar counts: adopted=7, partially_adopted=0, watch=0" in current_section
    assert re.search(r"Latest Veritas AutoResearch source commit: `[0-9a-f]{40}`", current_section)
    assert "AutoResearch operator status: `ok`" in current_section
    assert "git diff --check -- . ':!.pytest-root/**'" in current_section
    for artifact in (
        "var/workspace-smoke-workspace-2026-05-28-current-product-readiness.json",
        "var/workspace-smoke-desci-2026-05-28-release-readiness-doc-list-locked.json",
        "var/workspace-smoke-agriguard-2026-05-28-current-product-readiness.json",
        "var/workspace-smoke-mcp-2026-05-28-current-product-readiness.json",
        "var/workspace-smoke-getdaytrends-2026-05-28-current-product-readiness.json",
        "var/workspace-smoke-cie-2026-05-28-current-product-readiness.json",
    ):
        assert artifact in product_readiness_section
    assert "Current result: **32/32 PASS**" in product_readiness_section
    assert "release approval contract tests" in product_readiness_section
    assert "tests/test_security_gate_contracts.py" in product_readiness_section
    assert "desci release readiness contracts" in product_readiness_section
    assert "schema v1 object and per-result fields" in product_readiness_section
    assert "operator JSON evidence contracts" in product_readiness_section
    assert (
        "var\\workspace-smoke-desci-2026-05-28-quality-gate-operator-json-contract.json"
        in product_readiness_section
    )
    assert "199 passed" in product_readiness_section
    assert "75 passed" in product_readiness_section
    assert "structured `latest_smoke_evidence` metadata" in product_readiness_section
    assert "candidate-order-independent newest-valid selection" in product_readiness_section
    assert "caller-provided candidate order" in product_readiness_section
    assert "shared reader owns current/legacy candidate collection" in product_readiness_section
    assert "ignores matching directories and non-file candidates" in product_readiness_section
    assert "newest corrupt candidate" in product_readiness_section
    assert "legacy `scripts` startup/context entrypoints" in product_readiness_section
    assert "workspace-map.json" in product_readiness_section
    assert (
        "Legacy array reports remain supported only when every entry is an object with boolean `ok` "
        "and at least one result"
        in product_readiness_section
    )
    assert "malformed legacy arrays and empty legacy arrays are skipped" in product_readiness_section
    assert "zero `summary.total` or `summary.completed`" in product_readiness_section
    assert "inconsistent schema v1 summaries" in product_readiness_section
    assert "missing top-level `summary` object" in product_readiness_section
    assert "missing top-level `results` array" in product_readiness_section
    assert "missing/empty/non-string `status`" in product_readiness_section
    assert "unsupported or boolean `schema_version`" in product_readiness_section
    assert "unparseable or timezone-naive `generated_at`" in product_readiness_section
    assert "status/progress contradictions" in product_readiness_section
    assert "missing required `results[]` fields" in product_readiness_section
    assert "non-object `results[]` entries" in product_readiness_section
    assert "empty trace fields (`scope`, `name`, `cwd`, `command`)" in product_readiness_section
    assert "unknown result scopes" in product_readiness_section
    assert "non-boolean `results[].ok`" in product_readiness_section
    assert "`results[].ok` values that contradict `returncode`" in product_readiness_section
    assert "`results[].ok` pass/fail counts" in product_readiness_section
    assert "`summary.failed`" in product_readiness_section
    assert "PRODUCT_READINESS_PROGRESS_2026-05-28.md" in product_readiness_section
    assert "without Lightning CSS `@extend` warnings" in product_readiness_section
    assert "293 passed" in product_readiness_section
    assert "25/25" not in product_readiness_section
    assert "29/29" not in product_readiness_section
    assert "30/30" not in product_readiness_section


def test_product_readiness_progress_records_latest_evidence_contracts() -> None:
    report = PRODUCT_READINESS_PROGRESS_PATH.read_text(encoding="utf-8")

    assert "schema v1 object instead of the stale bare-array format" in report
    assert "unsupported or boolean `schema_version`" in report
    assert "unparseable or timezone-naive `generated_at`" in report
    assert "missing top-level `summary` objects" in report
    assert "missing top-level `results` arrays" in report
    assert "missing/empty/non-string statuses" in report
    assert "inconsistent schema v1 summary counts" in report
    assert "status/progress contradictions" in report
    assert "missing required `results[]` fields" in report
    assert "missing required result fields" in report
    assert "`results[]` entries" in report
    assert "non-boolean `results[].ok`" in report
    assert "`results[].ok` values that contradict `returncode`" in report
    assert "`results[].ok` pass/fail-count drift" in report
    assert "malformed or empty legacy arrays" in report
    assert "Legacy arrays must contain only object entries with boolean `ok` and at least one result" in report
    assert "zero `summary.total` or `summary.completed`" in report
    assert "candidate collection now lives in the shared reader" in report
    assert "ignores matching directories and non-file candidates" in report
    assert "name the newest corrupt candidate" in report
    assert "structured `latest_smoke_evidence` metadata" in report
    assert "unknown result scopes" in report
    assert "empty trace fields (`scope`, `name`, `cwd`, `command`)" in report
    assert "caller-provided candidate order" in report
    assert "legacy `scripts` startup/context entrypoints" in report
    assert "workspace-map.json" in report
    assert "199 passed" in report
    assert "75 passed" in report
    assert "var/workspace-smoke-desci-2026-05-28-quality-gate-operator-json-contract.json" in report
    assert "without Lightning CSS @extend warnings" in report
    assert "293 passed" in report
    assert "docs/reports/2026-05/RELEASE_APPROVAL_WORKSPACE_2026-05-28.json" in report
    assert "var/workspace-smoke-workspace-2026-05-28-release-approval-artifact.json" in report
    assert "release approval evidence is valid" in report


def test_default_checks_cover_expected_scopes_and_existing_paths() -> None:
    smoke = load_smoke_module()
    checks = smoke.default_checks("python")

    assert {check.scope for check in checks} == {"workspace", "desci", "agriguard", "mcp", "getdaytrends", "cie"}
    assert any(check.name == "workspace regression tests" for check in checks)
    assert any(check.name == "ops agents tests" for check in checks)
    assert any(check.name == "security contract tests" for check in checks)
    assert any(check.name == "release approval contract tests" for check in checks)
    assert any(check.name == "dashboard frontend lint" for check in checks)
    assert any(check.name == "dashboard frontend tests" for check in checks)
    assert any(check.name == "dashboard frontend build" for check in checks)
    assert any(check.name == "dashboard bundle budget" for check in checks)
    assert any(check.name == "desci frontend unit tests" for check in checks)
    assert any(check.name == "desci bundle budget" for check in checks)
    assert any(check.name == "desci contracts compile" for check in checks)
    assert any(check.name == "desci contracts tests" for check in checks)
    assert any(check.name == "desci release readiness contracts" for check in checks)
    assert any(check.name == "agriguard contracts compile" for check in checks)
    assert any(check.name == "agriguard contracts tests" for check in checks)
    assert any(check.name == "agriguard backend tests" for check in checks)
    assert any(check.name == "notebooklm compile" for check in checks)
    assert any(check.name == "DailyNews unit tests" for check in checks)
    assert any(check.name == "DailyNews X ops suite" for check in checks)
    assert any(check.name == "DailyNews X ops browser smoke" for check in checks)
    assert any(check.name == "DailyNews X action-log roundtrip smoke" for check in checks)
    assert any(check.name == "DailyNews first-run verifier smoke" for check in checks)
    dailynews_checks = smoke.filter_checks_by_scope(checks, "dailynews")
    assert [check.name for check in dailynews_checks] == [
        "DailyNews unit tests",
        "DailyNews X ops suite",
        "DailyNews X ops browser smoke",
        "DailyNews X action-log roundtrip smoke",
        "DailyNews first-run verifier smoke",
    ]
    assert all(check.scope == "mcp" for check in dailynews_checks)
    assert any(check.name == "getdaytrends entrypoint syntax" for check in checks)
    assert any(check.name == "getdaytrends tests" for check in checks)
    assert any(check.name == "getdaytrends subpackage tests" for check in checks)
    assert any(check.name == "getdaytrends launch readiness gate" for check in checks)
    assert any(check.name == "getdaytrends Supabase recovery packet" for check in checks)
    assert any(check.name == "cie compile" for check in checks)
    assert any(check.name == "cie tests" for check in checks)

    for check in checks:
        assert (PROJECT_ROOT / check.cwd).exists()
        if check.name in {"notebooklm compile", "github-mcp compile", "getdaytrends compile", "cie compile"}:
            assert check.command[1] == smoke.COMPILE_HELPER
    for transient_dir in (
        ".venv",
        ".pytest-temp-verify",
        ".pytest-root",
        ".pytest_cache",
        ".smoke-tmp",
        ".mypy_cache",
        ".ruff_cache",
    ):
        assert transient_dir.replace(".", r"\.") in smoke.EXCLUDE_REGEX

    workspace_regression = next(check for check in checks if check.name == "workspace regression tests")
    assert "tests/test_auto_research_status.py" in workspace_regression.command
    ops_agents = next(check for check in checks if check.name == "ops agents tests")
    assert ops_agents.command[-2:] == ["ops/agents", "-q"]
    action_roundtrip = next(check for check in checks if check.name == "DailyNews X action-log roundtrip smoke")
    scratch_dir = action_roundtrip.command[action_roundtrip.command.index("--scratch-dir") + 1]
    json_out = action_roundtrip.command[action_roundtrip.command.index("--json-out") + 1]
    assert scratch_dir.startswith("../../var/dailynews-x-action-log-roundtrip-mcp-")
    assert scratch_dir != "../../var/dailynews-x-action-log-roundtrip-mcp"
    assert json_out == "../../var/dailynews-x-action-log-roundtrip-mcp.json"

    dailynews_browser_smoke = next(check for check in checks if check.name == "DailyNews X ops browser smoke")
    assert "../../var/dailynews-x-ops-browser-smoke-mcp.json" in dailynews_browser_smoke.command
    assert "--screenshot" in dailynews_browser_smoke.command
    assert "../../var/dailynews-x-ops-browser-smoke-mcp.png" in dailynews_browser_smoke.command
    dailynews_first_run = next(check for check in checks if check.name == "DailyNews first-run verifier smoke")
    assert "--refresh-browser-smoke" in dailynews_first_run.command
    assert "../../var/dailynews-x-ops-browser-smoke-first-run-verifier-mcp.json" in dailynews_first_run.command
    assert "../../var/dailynews-x-ops-browser-smoke-first-run-verifier-mcp.png" in dailynews_first_run.command

    getdaytrends_syntax = next(check for check in checks if check.name == "getdaytrends entrypoint syntax")
    assert getdaytrends_syntax.command[1:3] == ["-m", "py_compile"]
    assert getdaytrends_syntax.command[-1].endswith("main.py")

    getdaytrends_subpackages = next(check for check in checks if check.name == "getdaytrends subpackage tests")
    assert getdaytrends_subpackages.command[-4:] == ["core/tests", "tap/tests", "edape/tests", "-q"]

    getdaytrends_readiness = next(check for check in checks if check.name == "getdaytrends launch readiness gate")
    assert getdaytrends_readiness.cwd.endswith("automation/getdaytrends") or getdaytrends_readiness.cwd.endswith("automation\\getdaytrends")
    assert getdaytrends_readiness.command[1:] == [
        "scripts/readiness_check.py",
        "--max-scheduler-age-hours",
        "24",
        "--max-cli-smoke-age-hours",
        "24",
        "--max-browser-smoke-age-hours",
        "24",
        "--fail-on-runtime-fallback",
        "--require-live-db",
    ]

    getdaytrends_recovery_packet = next(
        check for check in checks if check.name == "getdaytrends Supabase recovery packet"
    )
    assert getdaytrends_recovery_packet.cwd.endswith("automation/getdaytrends") or getdaytrends_recovery_packet.cwd.endswith(
        "automation\\getdaytrends"
    )
    assert getdaytrends_recovery_packet.command[1:] == ["scripts/verify_supabase_recovery_packet.py"]

    desci_release = next(check for check in checks if check.name == "desci release readiness contracts")
    expected_desci_release_tests = [
        f"apps/desci-platform/backend/tests/{test_file}" for test_file in smoke.DESCI_RELEASE_READINESS_TESTS
    ]
    actual_desci_release_tests = [Path(part).as_posix() for part in desci_release.command[3:-1]]
    assert actual_desci_release_tests == expected_desci_release_tests


def test_select_checks_can_resume_after_named_check() -> None:
    smoke = load_smoke_module()
    checks = [
        smoke.Check("desci", "desci frontend lint", ".", ["npm", "run", "lint"]),
        smoke.Check("desci", "desci frontend unit tests", ".", ["npm", "run", "test:lts"]),
        smoke.Check("desci", "desci frontend build", ".", ["npm", "run", "build:lts"]),
        smoke.Check("desci", "desci bundle budget", ".", ["npm", "run", "check:bundle"]),
    ]

    selected = smoke.select_checks(checks, start_after="desci frontend unit tests")

    assert [check.name for check in selected] == ["desci frontend build", "desci bundle budget"]


def test_select_checks_only_check_preserves_default_order_and_rejects_missing() -> None:
    smoke = load_smoke_module()
    checks = [
        smoke.Check("desci", "desci frontend lint", ".", ["npm", "run", "lint"]),
        smoke.Check("desci", "desci frontend unit tests", ".", ["npm", "run", "test:lts"]),
        smoke.Check("desci", "desci frontend build", ".", ["npm", "run", "build:lts"]),
    ]

    selected = smoke.select_checks(
        checks,
        only_checks=["desci frontend build", "desci frontend lint", "desci frontend build"],
    )

    assert [check.name for check in selected] == ["desci frontend lint", "desci frontend build"]

    try:
        smoke.select_checks(checks, only_checks=["missing check"])
    except ValueError as exc:
        assert "missing check" in str(exc)
        assert "desci frontend lint" in str(exc)
    else:
        raise AssertionError("missing check should fail closed")


def test_uv_dependency_contract_covers_isolated_test_imports() -> None:
    smoke = load_smoke_module()

    shared_deps = smoke.UV_EXTRA_DEPENDENCIES["shared package tests"]
    security_deps = smoke.UV_EXTRA_DEPENDENCIES["security contract tests"]
    desci_backend_deps = smoke.UV_EXTRA_DEPENDENCIES["desci backend smoke"]
    desci_release_deps = smoke.UV_EXTRA_DEPENDENCIES["desci release readiness contracts"]
    dailynews_first_run_deps = smoke.UV_EXTRA_DEPENDENCIES["DailyNews first-run verifier smoke"]
    cie_deps = smoke.UV_EXTRA_DEPENDENCIES["cie tests"]

    assert "google-genai>=2.5.0,<3.0" in shared_deps
    assert smoke.WORKSPACE_SYNC_SENTINELS["ops agents tests"] == ("pydantic", "pytest_asyncio")
    assert "pyyaml>=6.0.0,<7.0" in security_deps
    assert smoke.WORKSPACE_SYNC_SENTINELS["security contract tests"] == ("yaml",)
    assert "security contract tests" not in smoke.FORCE_UV_CHECKS
    assert smoke.WORKSPACE_SYNC_SENTINELS["desci release readiness contracts"] == ("fastapi", "redis")
    assert desci_release_deps == desci_backend_deps
    assert "desci release readiness contracts" in smoke.FORCE_UV_CHECKS
    assert "google.genai" in smoke.WORKSPACE_SYNC_SENTINELS["shared package tests"]
    assert "dotenv" in smoke.WORKSPACE_SYNC_SENTINELS["telegram-mcp tests"]
    assert "python-dotenv" not in smoke.WORKSPACE_SYNC_SENTINELS["telegram-mcp tests"]
    assert "getdaytrends tests" not in smoke.FORCE_UV_CHECKS
    assert smoke.WORKSPACE_SYNC_SENTINELS["getdaytrends subpackage tests"] == ("shared.llm", "loguru")
    assert "getdaytrends subpackage tests" not in smoke.FORCE_UV_CHECKS
    assert smoke.WORKSPACE_SYNC_SENTINELS["getdaytrends launch readiness gate"] == ("schedule", "sqlalchemy")
    assert "getdaytrends launch readiness gate" not in smoke.FORCE_UV_CHECKS
    assert "DailyNews first-run verifier smoke" in smoke.FORCE_UV_CHECKS
    assert "playwright>=1.40.0,<2.0" in dailynews_first_run_deps

    for dependency in (
        "loguru>=0.7.0,<1.0",
        "sqlalchemy>=2.0.0,<3.0",
        "pydantic>=2.0.0,<3.0",
        "httpx>=0.27.0",
    ):
        assert dependency in cie_deps

    assert smoke.WORKSPACE_SYNC_SENTINELS["cie tests"] == ("loguru", "sqlalchemy", "pydantic", "httpx")


def test_build_pythonpath_includes_canonical_workspace_entries() -> None:
    smoke = load_smoke_module()
    pythonpath = smoke.build_pythonpath(PROJECT_ROOT, {"PYTHONPATH": "custom-entry"})
    entries = pythonpath.split(smoke.os.pathsep)

    assert str(PROJECT_ROOT) in entries
    assert str(PROJECT_ROOT / "packages") in entries
    assert str(PROJECT_ROOT / "automation") in entries
    assert str(PROJECT_ROOT / "apps" / "desci-platform") in entries
    assert entries[-1] == "custom-entry"


def test_runtime_temp_dir_stays_under_workspace_var_tmp() -> None:
    smoke = load_smoke_module()
    check = smoke.Check("workspace", "workspace regression tests", ".", ["python", "-m", "pytest", "-q"])
    temp_dir = smoke.runtime_temp_dir(PROJECT_ROOT, check)

    assert temp_dir.is_relative_to(PROJECT_ROOT / "var" / "tmp" / "workspace-smoke")
    assert temp_dir.parts[-2] == "workspace"


def test_command_for_check_appends_workspace_local_basetemp() -> None:
    smoke = load_smoke_module()
    check = smoke.Check(
        "workspace",
        "workspace regression tests",
        ".",
        ["python", "-m", "pytest", "tests/test_workspace_smoke.py", "-q"],
    )
    temp_dir = smoke.runtime_temp_dir(PROJECT_ROOT, check)

    command = smoke.command_for_check(check, temp_dir)

    assert command[-2:] == ["--basetemp", str(smoke.pytest_temp_dir(temp_dir))]


def test_resolve_python_executable_prefers_workspace_venv_over_current_interpreter(tmp_path: Path, monkeypatch) -> None:
    smoke = load_smoke_module()
    venv_python_rel = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    venv_python = tmp_path / ".venv" / venv_python_rel
    current_python = tmp_path / "current-python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")
    current_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(smoke.sys, "executable", str(current_python))
    monkeypatch.setattr(smoke, "has_module", lambda python_exe, module_name: True)

    assert smoke.resolve_python_executable(tmp_path) == str(venv_python)


def test_ensure_workspace_environment_falls_back_to_uv_runner_when_local_venv_is_incomplete(
    tmp_path: Path, monkeypatch
) -> None:
    smoke = load_smoke_module()
    venv_rel = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    local_python = tmp_path / ".venv" / venv_rel
    local_python.parent.mkdir(parents=True)
    local_python.write_text("", encoding="utf-8")
    global_python = tmp_path / "global-python.exe"
    global_python.write_text("", encoding="utf-8")
    check = smoke.Check("workspace", "workspace regression tests", ".", ["python", "-m", "pytest", "-q"])

    def fake_has_module(python_exe: str, module_name: str) -> bool:
        return False

    monkeypatch.setattr(smoke, "has_module", fake_has_module)
    monkeypatch.setattr(smoke.shutil, "which", lambda name: "uv" if name == "uv" else None)
    monkeypatch.setattr(smoke, "USE_UV_ISOLATED_RUNNER", False)

    result = smoke.ensure_workspace_environment(tmp_path, str(global_python), [check])

    assert result == str(global_python)
    assert smoke.USE_UV_ISOLATED_RUNNER is True


def test_workspace_environment_helpers_select_missing_modules(tmp_path: Path) -> None:
    smoke = load_smoke_module()
    candidates = smoke.local_python_candidates(tmp_path)
    venv_rel = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    assert tmp_path / ".venv" / venv_rel in candidates
    assert tmp_path / "venv" / venv_rel in candidates

    checks = [
        smoke.Check("workspace", "shared package tests", ".", []),
    ]
    required = smoke.required_modules_for_checks(checks)
    assert "pytest" in required
    assert "google.genai" in required
    assert "pydantic" in smoke.required_modules_for_checks(
        [smoke.Check("workspace", "ops agents tests", ".", [])]
    )



def test_run_one_uses_uv_isolated_runner_for_python_checks_when_bootstrap_fallback_is_enabled(
    tmp_path: Path, monkeypatch
) -> None:
    smoke = load_smoke_module()
    check = smoke.Check("workspace", "workspace regression tests", ".", ["python", "-m", "pytest", "-q"])
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)

        class Proc:
            returncode = 0
            stdout = b"ok"
            stderr = b""

        return Proc()

    monkeypatch.setattr(smoke, "USE_UV_ISOLATED_RUNNER", True)
    monkeypatch.setattr(smoke, "run_command_capture", fake_run)

    result = smoke.run_one(PROJECT_ROOT, check)

    assert result.ok is True
    assert commands[0][:4] == ["uv", "run", "--isolated", "--no-project"]
    assert "--with" in commands[0]
    assert "--with-editable" in commands[0]
    assert commands[0][-6:] == [
        "python",
        "-m",
        "pytest",
        "-q",
        "--basetemp",
        str(smoke.pytest_temp_dir(smoke.runtime_temp_dir(PROJECT_ROOT, check))),
    ]


def test_security_contract_tests_use_ready_workspace_python_without_forced_uv() -> None:
    smoke = load_smoke_module()
    check = smoke.Check(
        "workspace",
        "security contract tests",
        ".",
        ["python", "-m", "pytest", "tests/test_security_gate_contracts.py", "-q"],
    )

    command = smoke.prepared_command(PROJECT_ROOT, check, smoke.runtime_temp_dir(PROJECT_ROOT, check))

    assert command[:4] != ["uv", "run", "--isolated", "--no-project"]
    assert command[:4] == ["python", "-m", "pytest", "tests/test_security_gate_contracts.py"]
    assert command[-2:] == ["--basetemp", str(smoke.pytest_temp_dir(smoke.runtime_temp_dir(PROJECT_ROOT, check)))]


def test_run_one_uses_configured_check_timeout(monkeypatch) -> None:
    smoke = load_smoke_module()
    check = smoke.Check("workspace", "workspace timeout probe", ".", ["python", "-c", "print('ok')"])
    observed_timeout = None

    def fake_run(command, **kwargs):  # noqa: ARG001
        nonlocal observed_timeout
        observed_timeout = kwargs["timeout"]

        class Proc:
            returncode = 0
            stdout = b"ok"
            stderr = b""

        return Proc()

    monkeypatch.setattr(smoke, "CHECK_TIMEOUT_SECONDS", 123)
    monkeypatch.setattr(smoke, "run_command_capture", fake_run)

    result = smoke.run_one(PROJECT_ROOT, check)

    assert result.ok is True
    assert observed_timeout == 123
    assert isinstance(result.elapsed_ms, int)
    assert result.elapsed_ms >= 0


def test_run_command_capture_terminates_process_tree_on_timeout(monkeypatch) -> None:
    smoke = load_smoke_module()
    terminated = []

    class FakeProcess:
        pid = 12345
        returncode = None

        def __init__(self):
            self.communicate_calls = 0
            self.killed = False

        def communicate(self, timeout=None):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise subprocess.TimeoutExpired(["slow"], timeout, output=b"partial out", stderr=b"partial err")
            return b"final out", b"final err"

        def poll(self):
            return self.returncode

        def kill(self):
            self.killed = True

    fake_proc = FakeProcess()

    def fake_popen(*args, **kwargs):  # noqa: ARG001
        return fake_proc

    monkeypatch.setattr(smoke.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(smoke, "terminate_process_tree", lambda proc: terminated.append(proc.pid))

    with pytest.raises(subprocess.TimeoutExpired) as exc_info:
        smoke.run_command_capture(["slow"], cwd=str(PROJECT_ROOT), env={}, timeout=1)

    assert terminated == [12345]
    assert fake_proc.communicate_calls == 2
    assert exc_info.value.output == b"final out"
    assert exc_info.value.stderr == b"final err"


def test_run_one_reports_elapsed_ms(monkeypatch) -> None:
    smoke = load_smoke_module()
    check = smoke.Check("workspace", "workspace timing probe", ".", ["python", "-c", "print('ok')"])
    perf_counter_values = iter([10.0, 10.125])

    def fake_run(command, **kwargs):  # noqa: ARG001
        class Proc:
            returncode = 0
            stdout = b"ok"
            stderr = b""

        return Proc()

    monkeypatch.setattr(smoke.time, "perf_counter", lambda: next(perf_counter_values))
    monkeypatch.setattr(smoke, "run_command_capture", fake_run)

    result = smoke.run_one(PROJECT_ROOT, check)
    payload = smoke.result_payload(result)

    assert result.elapsed_ms == 125
    assert payload["elapsed_ms"] == 125


def test_json_report_payload_includes_elapsed_summary() -> None:
    smoke = load_smoke_module()
    results = [
        smoke.Result("workspace", "fast check", ".", "python -V", 0, True, "ok", "", elapsed_ms=10),
        smoke.Result("workspace", "slow check", ".", "python -V", 1, False, "", "failed", elapsed_ms=250),
        smoke.Result("workspace", "middle check", ".", "python -V", 0, True, "ok", "", elapsed_ms=25),
    ]

    payload = smoke.json_report_payload(results, total_checks=4, complete=False)

    assert payload["status"] == "partial"
    assert payload["summary"]["elapsed_ms_total"] == 285
    assert payload["summary"]["slowest_results"] == [
        {"scope": "workspace", "name": "slow check", "elapsed_ms": 250, "ok": False},
        {"scope": "workspace", "name": "middle check", "elapsed_ms": 25, "ok": True},
        {"scope": "workspace", "name": "fast check", "elapsed_ms": 10, "ok": True},
    ]


def test_json_report_payload_records_release_profile() -> None:
    smoke = load_smoke_module()
    results = [smoke.Result("agriguard", "agriguard backend tests", ".", "pytest", 0, True, "ok", "")]

    payload = smoke.json_report_payload(
        results,
        total_checks=1,
        complete=True,
        release_profile="agriguard-release-smoke",
    )

    assert payload["release_profile"] == "agriguard-release-smoke"


def test_print_results_summary_includes_elapsed_timing(capsys) -> None:
    smoke = load_smoke_module()
    results = [
        smoke.Result("workspace", "fast check", ".", "python -V", 0, True, "ok", "", elapsed_ms=10),
        smoke.Result("workspace", "slow check", ".", "python -m pytest", 1, False, "", "failed", elapsed_ms=1250),
    ]

    smoke.print_results_summary(results)

    out = capsys.readouterr().out
    assert "[smoke] timing: elapsed=1.3s" in out
    assert "- [FAIL] slow check elapsed=1.2s" in out
    assert "- [PASS] fast check elapsed=10ms" in out


def test_run_one_cleans_stale_temp_dir(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    temp_dir = tmp_path / "workspace-smoke-temp"
    stale_file = temp_dir / "stale.txt"
    temp_dir.mkdir(parents=True)
    stale_file.write_text("stale", encoding="utf-8")

    monkeypatch.setattr(smoke, "runtime_temp_dir", lambda root, item: temp_dir)
    check = smoke.Check("workspace", "temp cleanup", ".", [sys.executable, "-c", "print('ok')"])

    result = smoke.run_one(PROJECT_ROOT, check)

    assert result.ok is True
    assert temp_dir.exists()
    assert stale_file.exists() is False


def test_run_one_reports_missing_working_directory() -> None:
    smoke = load_smoke_module()
    check = smoke.Check("workspace", "missing", "does-not-exist", ["python", "-V"])

    result = smoke.run_one(PROJECT_ROOT, check)

    assert result.ok is False
    assert result.returncode == 2
    assert result.stderr_tail == "working directory missing"


def test_run_check_retries_transient_desci_vitest_worker_failure(monkeypatch) -> None:
    smoke = load_smoke_module()
    check = smoke.Check(
        "desci", "desci frontend unit tests", "apps/desci-platform/frontend", ["npm.cmd", "run", "test:lts"]
    )
    attempts = iter(
        [
            smoke.Result(
                "desci",
                "desci frontend unit tests",
                "apps/desci-platform/frontend",
                "npm.cmd run test:lts",
                1,
                False,
                "",
                "Error: [vitest-pool]: Failed to start threads worker\nCaused by: Error: [vitest-pool-runner]: Timeout waiting for worker to respond",
            ),
            smoke.Result(
                "desci",
                "desci frontend unit tests",
                "apps/desci-platform/frontend",
                "npm.cmd run test:lts",
                0,
                True,
                "31 passed",
                "",
            ),
        ]
    )

    monkeypatch.setattr(smoke, "run_one", lambda root, item: next(attempts))

    result = smoke.run_check(PROJECT_ROOT, check)

    assert result.ok is True
    assert result.stdout_tail == "31 passed"


def test_should_retry_ignores_non_transient_failures() -> None:
    smoke = load_smoke_module()
    check = smoke.Check(
        "desci", "desci frontend unit tests", "apps/desci-platform/frontend", ["npm.cmd", "run", "test:lts"]
    )
    result = smoke.Result(
        "desci",
        "desci frontend unit tests",
        "apps/desci-platform/frontend",
        "npm.cmd run test:lts",
        1,
        False,
        "",
        "AssertionError: expected false to be true",
    )

    assert smoke.should_retry(check, result) is False


def test_should_retry_uv_access_denied_install_failure() -> None:
    smoke = load_smoke_module()
    check = smoke.Check("mcp", "DailyNews unit tests", "automation/DailyNews", ["python", "-m", "pytest", "tests/unit"])
    result = smoke.Result(
        "mcp",
        "DailyNews unit tests",
        "automation/DailyNews",
        "uv run --isolated --no-project python -m pytest tests/unit",
        2,
        False,
        "",
        "error: ?≪꽭?ㅺ? 嫄곕??섏뿀?듬땲?? (os error -2147024891)",
    )

    assert smoke.should_retry(check, result) is True


def test_should_retry_uv_trampoline_resource_update_failure() -> None:
    smoke = load_smoke_module()
    check = smoke.Check(
        "getdaytrends",
        "getdaytrends launch readiness gate",
        "automation/getdaytrends",
        ["python", "scripts/readiness_check.py"],
    )
    result = smoke.Result(
        "getdaytrends",
        "getdaytrends launch readiness gate",
        "automation/getdaytrends",
        "uv run --isolated --no-project python scripts/readiness_check.py",
        2,
        False,
        "",
        (
            "error: Failed to update Windows PE resources: "
            "var/tmp/workspace-smoke/.tmp/uv-trampoline.exe\n"
            "  Caused by: path not found (os error -2147024893)"
        ),
    )

    assert smoke.should_retry(check, result) is True


def test_should_retry_silent_uv_process_failure() -> None:
    smoke = load_smoke_module()
    check = smoke.Check("cie", "cie tests", "automation/content-intelligence", ["python", "-m", "pytest", "tests"])

    result = smoke.Result(
        "cie",
        "cie tests",
        "automation/content-intelligence",
        "uv run --isolated --no-project python -m pytest tests",
        0xFFFFFFFF,
        False,
        "",
        "",
    )
    non_uv = smoke.Result("cie", "cie tests", ".", "python -m pytest tests", 0xFFFFFFFF, False, "", "")
    non_pytest = smoke.Result("cie", "cie tests", ".", "python scripts/check.py", 0xFFFFFFFF, False, "", "")

    assert smoke.should_retry(check, result) is True
    assert smoke.should_retry(check, non_uv) is True
    assert smoke.should_retry(check, non_pytest) is False


def test_should_retry_uv_abrupt_exit_with_pytest_progress_only() -> None:
    smoke = load_smoke_module()
    check = smoke.Check("getdaytrends", "getdaytrends tests", "automation/getdaytrends", ["python", "-m", "pytest"])
    progress_only = smoke.Result(
        "getdaytrends",
        "getdaytrends tests",
        "automation/getdaytrends",
        "uv run --isolated --no-project python -m pytest -q",
        0xFFFFFFFF,
        False,
        "s....................................................................... [  7%]\n..............................s.ss......",
        "",
    )
    real_failure = smoke.Result(
        "getdaytrends",
        "getdaytrends tests",
        "automation/getdaytrends",
        "uv run --isolated --no-project python -m pytest -q",
        0xFFFFFFFF,
        False,
        "FAILED tests/test_example.py::test_case - AssertionError",
        "",
    )

    assert smoke.should_retry(check, progress_only) is True
    assert smoke.should_retry(check, real_failure) is False


def test_should_retry_python_pytest_abrupt_exit_with_progress_only() -> None:
    smoke = load_smoke_module()
    check = smoke.Check("getdaytrends", "getdaytrends tests", "automation/getdaytrends", ["python", "-m", "pytest"])
    progress_only = smoke.Result(
        "getdaytrends",
        "getdaytrends tests",
        "automation/getdaytrends",
        '"D:\\AI project\\.venv\\Scripts\\python.exe" -m pytest -c pytest.ini tests -q',
        0xFFFFFFFF,
        False,
        "s....................................................................... [  5%]\n.............................. [ 73%]",
        "",
    )
    real_failure = smoke.Result(
        "getdaytrends",
        "getdaytrends tests",
        "automation/getdaytrends",
        '"D:\\AI project\\.venv\\Scripts\\python.exe" -m pytest -c pytest.ini tests -q',
        0xFFFFFFFF,
        False,
        "FAILED tests/test_example.py::test_case - AssertionError",
        "",
    )

    assert smoke.should_retry(check, progress_only) is True
    assert smoke.should_retry(check, real_failure) is False


def test_retry_helper_patterns_are_command_specific() -> None:
    smoke = load_smoke_module()
    check = smoke.Check("scope", "name", ".", ["npm", "run", "test"])

    # 1. NPM transient pattern EPERM on npm command
    res1 = smoke.Result("scope", "name", ".", "npm run test", 1, False, "worker timeout", "EPERM")
    assert smoke.should_retry(check, res1) is True

    # 2. UV transient pattern on uv command
    check_uv = smoke.Check("scope", "name", ".", ["uv", "run", "pytest"])
    res2 = smoke.Result("scope", "name", ".", "uv run pytest", 1, False, "", "액세스가 거부되었습니다")
    assert smoke.should_retry(check_uv, res2) is True

    # 3. Non-matching pattern on UV command doesn't retry
    res3 = smoke.Result("scope", "name", ".", "uv run pytest", 1, False, "", "some other error")
    assert smoke.should_retry(check_uv, res3) is False


def test_agriguard_disk_preflight_reports_low_cache_paths(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    root = tmp_path / "workspace"
    temp_dir = tmp_path / "temp"
    npm_cache = tmp_path / "npm-cache"
    uv_cache = tmp_path / "uv-cache"
    for path in (root, temp_dir, npm_cache, uv_cache):
        path.mkdir(parents=True)
    args = Namespace(scope="agriguard", skip_disk_preflight=False, min_free_mb=128)
    checks = [smoke.Check("agriguard", "agriguard frontend lint", ".", ["npm", "run", "lint"])]

    monkeypatch.setattr(
        smoke.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=32 * 1024 * 1024),
    )

    result = smoke.disk_preflight_failure_result(
        root,
        args,
        checks,
        None,
        environ={
            "TEMP": str(temp_dir),
            "TMP": str(temp_dir),
            "npm_config_cache": str(npm_cache),
            "UV_CACHE_DIR": str(uv_cache),
        },
    )

    assert result is not None
    assert result.name == "agriguard disk preflight"
    assert result.returncode == errno.ENOSPC
    assert "requires at least 128 MiB" in result.stderr_tail
    assert "set TEMP and TMP" in result.stderr_tail
    assert "set npm_config_cache" in result.stderr_tail
    assert "set UV_CACHE_DIR" in result.stderr_tail


def test_agriguard_disk_preflight_passes_with_d_backed_paths(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    root = tmp_path / "workspace"
    temp_dir = tmp_path / "var" / "tmp"
    npm_cache = tmp_path / "var" / "npm-cache"
    uv_cache = tmp_path / "var" / "uv-cache"
    for path in (root, temp_dir, npm_cache, uv_cache):
        path.mkdir(parents=True)
    args = Namespace(scope="agriguard", skip_disk_preflight=False, min_free_mb=128)
    checks = [smoke.Check("agriguard", "agriguard frontend lint", ".", ["npm", "run", "lint"])]

    monkeypatch.setattr(
        smoke.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=1024 * 1024 * 1024),
    )

    result = smoke.disk_preflight_failure_result(
        root,
        args,
        checks,
        tmp_path / "var" / "smoke.json",
        environ={
            "TEMP": str(temp_dir),
            "TMP": str(temp_dir),
            "npm_config_cache": str(npm_cache),
            "UV_CACHE_DIR": str(uv_cache),
        },
    )

    assert result is None


def test_agriguard_disk_preflight_uses_concrete_scope_for_all_scope(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    root = tmp_path / "workspace"
    temp_dir = tmp_path / "temp"
    for path in (root, temp_dir):
        path.mkdir(parents=True)
    args = Namespace(scope="all", skip_disk_preflight=False, min_free_mb=128)
    checks = [
        smoke.Check("workspace", "workspace regression tests", ".", ["python", "-m", "pytest"]),
        smoke.Check("agriguard", "agriguard frontend lint", ".", ["npm", "run", "lint"]),
    ]

    monkeypatch.setattr(
        smoke.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=32 * 1024 * 1024),
    )

    result = smoke.disk_preflight_failure_result(
        root,
        args,
        checks,
        None,
        environ={
            "TEMP": str(temp_dir),
            "TMP": str(temp_dir),
            "npm_config_cache": str(root / "npm-cache"),
            "UV_CACHE_DIR": str(root / "uv-cache"),
        },
    )

    assert result is not None
    assert result.scope == "agriguard"
    assert result.name == "agriguard disk preflight"


def test_main_writes_json_report_for_selected_scope(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    fake_check = smoke.Check("workspace", "fake check", ".", ["python", "-V"])
    fake_result = smoke.Result("workspace", "fake check", ".", "python -V", 0, True, "ok", "")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(smoke, "resolve_python_executable", lambda root: "python")
    monkeypatch.setattr(smoke, "has_module", lambda python_exe, module_name: True)
    monkeypatch.setattr(smoke, "default_checks", lambda python_exe: [fake_check])
    monkeypatch.setattr(smoke, "run_one", lambda root, item: fake_result)
    monkeypatch.setattr(
        smoke.sys,
        "argv",
        ["run_workspace_smoke.py", "--scope", "workspace", "--json-out", "smoke.json"],
    )

    exit_code = smoke.main()

    report = json.loads((tmp_path / "smoke.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["schema_version"] == 1
    assert report["status"] == "complete"
    assert report["summary"] == {
        "total": 1,
        "completed": 1,
        "passed": 1,
        "failed": 0,
        "remaining": 0,
        "expected_external_failures": [],
        "unexpected_failures": [],
    }
    assert report["results"] == [
        {
            "scope": "workspace",
            "name": "fake check",
            "cwd": ".",
            "command": "python -V",
            "returncode": 0,
            "ok": True,
            "stdout_tail": "ok",
            "stderr_tail": "",
        }
    ]


def test_main_writes_partial_json_when_agriguard_disk_preflight_fails(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    fake_check = smoke.Check("agriguard", "fake agriguard check", ".", ["python", "-V"])
    preflight = smoke.Result(
        "agriguard",
        "agriguard disk preflight",
        ".",
        "workspace disk preflight",
        errno.ENOSPC,
        False,
        "",
        "python_temp: C:\\Temp has 32.0 MiB free; requires at least 128 MiB",
        elapsed_ms=0,
    )
    report_path = tmp_path / "smoke.json"

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("selected checks should not run after disk preflight failure")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(smoke, "resolve_python_executable", lambda root: "python")
    monkeypatch.setattr(smoke, "has_module", lambda python_exe, module_name: True)
    monkeypatch.setattr(smoke, "default_checks", lambda python_exe: [fake_check])
    monkeypatch.setattr(smoke, "run_one", fail_if_called)
    monkeypatch.setattr(
        smoke,
        "disk_preflight_failure_result",
        lambda root, args, checks, out_path: preflight,
    )
    monkeypatch.setattr(
        smoke.sys,
        "argv",
        ["run_workspace_smoke.py", "--scope", "agriguard", "--json-out", str(report_path)],
    )

    exit_code = smoke.main()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["status"] == "partial"
    assert report["summary"]["total"] == 2
    assert report["summary"]["completed"] == 1
    assert report["summary"]["failed"] == 1
    assert report["summary"]["remaining"] == 1
    assert report["results"][0]["name"] == "agriguard disk preflight"


def test_main_accepts_dailynews_scope_alias(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    checks = [
        smoke.Check("mcp", "DailyNews unit tests", "automation/DailyNews", ["python", "-V"]),
        smoke.Check("mcp", "canva-mcp build", "mcp/canva-mcp", ["npm", "run", "build"]),
        smoke.Check("workspace", "workspace regression tests", ".", ["python", "-V"]),
    ]
    ran: list[str] = []

    def fake_run_one(root, item):  # noqa: ARG001
        ran.append(item.name)
        return smoke.Result(item.scope, item.name, item.cwd, smoke.format_command(item.command), 0, True, "ok", "")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(smoke, "resolve_python_executable", lambda root: "python")
    monkeypatch.setattr(smoke, "has_module", lambda python_exe, module_name: True)
    monkeypatch.setattr(smoke, "default_checks", lambda python_exe: checks)
    monkeypatch.setattr(smoke, "run_one", fake_run_one)
    monkeypatch.setattr(
        smoke.sys,
        "argv",
        ["run_workspace_smoke.py", "--scope", "dailynews", "--json-out", "smoke.json"],
    )

    exit_code = smoke.main()

    report = json.loads((tmp_path / "smoke.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert ran == ["DailyNews unit tests"]
    assert report["summary"]["total"] == 1
    assert report["results"][0]["scope"] == "mcp"
    assert report["results"][0]["name"] == "DailyNews unit tests"


def test_main_updates_json_report_after_each_completed_check(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    checks = [
        smoke.Check("workspace", "first check", ".", ["python", "-V"]),
        smoke.Check("workspace", "second check", ".", ["python", "-V"]),
    ]
    results = {
        "first check": smoke.Result("workspace", "first check", ".", "python -V", 0, True, "first", ""),
        "second check": smoke.Result("workspace", "second check", ".", "python -V", 0, True, "second", ""),
    }
    report_path = tmp_path / "smoke.json"

    def fake_run_one(root, item):  # noqa: ARG001
        if item.name == "second check":
            partial_report = json.loads(report_path.read_text(encoding="utf-8"))
            assert partial_report["status"] == "partial"
            assert partial_report["summary"] == {
                "total": 2,
                "completed": 1,
                "passed": 1,
                "failed": 0,
                "remaining": 1,
                "expected_external_failures": [],
                "unexpected_failures": [],
            }
            assert [entry["name"] for entry in partial_report["results"]] == ["first check"]
        return results[item.name]

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(smoke, "resolve_python_executable", lambda root: "python")
    monkeypatch.setattr(smoke, "has_module", lambda python_exe, module_name: True)
    monkeypatch.setattr(smoke, "default_checks", lambda python_exe: checks)
    monkeypatch.setattr(smoke, "run_one", fake_run_one)
    monkeypatch.setattr(
        smoke.sys,
        "argv",
        ["run_workspace_smoke.py", "--scope", "workspace", "--json-out", str(report_path)],
    )

    exit_code = smoke.main()

    final_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert final_report["status"] == "complete"
    assert final_report["summary"] == {
        "total": 2,
        "completed": 2,
        "passed": 2,
        "failed": 0,
        "remaining": 0,
        "expected_external_failures": [],
        "unexpected_failures": [],
    }
    assert [entry["name"] for entry in final_report["results"]] == ["first check", "second check"]


def test_write_json_report_replaces_existing_report_atomically(tmp_path) -> None:
    smoke = load_smoke_module()
    report_path = tmp_path / "nested" / "smoke.json"
    report_path.parent.mkdir()
    report_path.write_text("stale", encoding="utf-8")
    result = smoke.Result("workspace", "atomic check", ".", "python -V", 0, True, "ok", "")

    smoke.write_json_report(report_path, [result], total_checks=1, complete=True)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "complete"
    assert report["summary"] == {
        "total": 1,
        "completed": 1,
        "passed": 1,
        "failed": 0,
        "remaining": 0,
        "expected_external_failures": [],
        "unexpected_failures": [],
    }
    assert report["results"][0]["name"] == "atomic check"
    assert not (report_path.parent / "smoke.json.tmp").exists()


def test_write_json_report_retries_transient_replace_lock(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    report_path = tmp_path / "smoke.json"
    temp_path = report_path.with_name(f"{report_path.name}.tmp")
    result = smoke.Result("workspace", "retry check", ".", "python -V", 0, True, "ok", "")
    original_replace = Path.replace
    replace_calls: list[str] = []
    sleeps: list[float] = []

    def flaky_replace(self: Path, target: Path) -> Path:
        if self == temp_path and not replace_calls:
            replace_calls.append("locked")
            raise PermissionError(13, "The process cannot access the file")
        replace_calls.append("replaced")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    monkeypatch.setattr(smoke.time, "sleep", lambda delay: sleeps.append(delay))

    smoke.write_json_report(report_path, [result], total_checks=1, complete=True)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert replace_calls == ["locked", "replaced"]
    assert sleeps == [smoke.JSON_REPORT_REPLACE_RETRY_DELAY_SECONDS]
    assert report["results"][0]["name"] == "retry check"
    assert not temp_path.exists()


def test_json_report_payload_classifies_expected_external_getdaytrends_failure() -> None:
    smoke = load_smoke_module()
    results = [
        smoke.Result("getdaytrends", "getdaytrends tests", ".", "python -m pytest", 0, True, "ok", ""),
        smoke.Result(
            "getdaytrends",
            "getdaytrends launch readiness gate",
            ".",
            "python scripts/readiness_check.py --require-live-db",
            1,
            False,
            "live_db_doctor database_url_live_check_failed tenant/user live PostgreSQL probe failed",
            "",
        ),
    ]

    report = smoke.json_report_payload(results, total_checks=2, complete=True)

    assert report["summary"]["failed"] == 1
    assert report["summary"]["expected_external_failures"] == ["getdaytrends launch readiness gate"]
    assert report["summary"]["unexpected_failures"] == []


def test_smoke_dataclasses_sanity() -> None:
    smoke = load_smoke_module()
    check = smoke.Check("workspace", "workspace check", ".", ["python", "-V"])
    assert check.scope == "workspace"
    assert check.name == "workspace check"

    result = smoke.Result("workspace", "workspace check", ".", "python -V", 0, True, "ok", "")
    assert result.ok is True
    assert result.stdout_tail == "ok"
