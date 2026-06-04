from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "external_credential_live_verify.py"
REGISTRY_PATH = PROJECT_ROOT / "ops" / "references" / "external_credential_boundaries.json"
DRY_RUN_JSON_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.json"
DRY_RUN_MARKDOWN_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.md"
READY_ONLY_JSON_PATH = (
    PROJECT_ROOT / "docs" / "reports" / "2026-06" / "EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.json"
)
READY_ONLY_MARKDOWN_PATH = (
    PROJECT_ROOT / "docs" / "reports" / "2026-06" / "EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.md"
)


def load_module():
    spec = importlib.util.spec_from_file_location("external_credential_live_verify", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_registry_dry_run_reports_ready_and_blocked_boundaries() -> None:
    verifier = load_module()

    report = verifier.run(REGISTRY_PATH, env={})

    assert report["status"] == "pass"
    assert report["mode"] == "dry_run"
    assert report["summary"]["selected_boundaries"] >= 5
    assert report["summary"]["ready_boundaries"] == 1
    assert report["summary"]["blocked_boundaries"] == 4
    assert report["summary"]["commands_executed"] == 0
    assert "canva_oauth_and_openapi_tool_execution" in {
        boundary["id"]
        for boundary in report["boundaries"]
        if boundary["live_status"] == "blocked_missing_required_env"
    }
    assert "github_source_refresh_rate_limit_token" in {
        boundary["id"]
        for boundary in report["boundaries"]
        if boundary["live_status"] == "blocked_missing_optional_env"
    }


def test_boundary_filter_rejects_unknown_id() -> None:
    verifier = load_module()

    exit_code = verifier.main(["--registry", str(REGISTRY_PATH), "--boundary", "missing_boundary"])

    assert exit_code == 1


def test_execute_skips_missing_required_env(tmp_path: Path) -> None:
    verifier = load_module()
    registry = _write_registry(
        tmp_path,
        required_env=["SAMPLE_TOKEN"],
        command=f"{sys.executable} -c \"print('should-not-run')\"",
    )

    plan = verifier.build_plan(registry, env={}, workspace_root=tmp_path)
    report = verifier.execute_plan(plan, env={}, workspace_root=tmp_path)

    assert report["status"] == "fail"
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["commands_skipped"] == 1
    assert report["commands"][0]["skip_reason"] == "missing required env"


def test_execute_skips_missing_optional_token_boundary(tmp_path: Path) -> None:
    verifier = load_module()
    registry = _write_registry(
        tmp_path,
        status="optional_token_absent",
        required_env=[],
        optional_env_any_of=["SAMPLE_TOKEN"],
        command=f"{sys.executable} -c \"print('should-not-run')\"",
    )

    plan = verifier.build_plan(registry, env={}, workspace_root=tmp_path)
    report = verifier.execute_plan(plan, env={}, workspace_root=tmp_path)

    assert plan["boundaries"][0]["live_status"] == "blocked_missing_optional_env"
    assert report["status"] == "fail"
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["commands_skipped"] == 1
    assert report["commands"][0]["skip_reason"] == "missing optional token env"


def test_ready_only_filters_default_registry_to_runnable_boundaries() -> None:
    verifier = load_module()

    report = verifier.run(REGISTRY_PATH, env={}, ready_only=True)

    assert report["status"] == "pass"
    assert report["selection"] == "ready_only"
    assert report["summary"]["selected_boundaries"] == 1
    assert report["summary"]["ready_boundaries"] == 1
    assert report["summary"]["blocked_boundaries"] == 0
    assert [boundary["id"] for boundary in report["boundaries"]] == ["hosted_agent_runtime_credentials"]


def test_ready_only_execute_ignores_blocked_boundary(tmp_path: Path) -> None:
    verifier = load_module()
    registry = _write_mixed_registry(tmp_path)

    report = verifier.run(registry, execute=True, ready_only=True, env={}, workspace_root=tmp_path)

    assert report["status"] == "pass"
    assert report["summary"]["selected_boundaries"] == 1
    assert report["summary"]["commands_executed"] == 1
    assert report["summary"]["commands_skipped"] == 0
    assert report["commands"][0]["boundary_id"] == "ready"
    assert "ready-ran" in report["commands"][0]["stdout_tail"]


def test_execute_runs_ready_boundary_and_redacts_secret(tmp_path: Path) -> None:
    verifier = load_module()
    registry = _write_registry(
        tmp_path,
        required_env=["SAMPLE_TOKEN"],
        command=f"{sys.executable} -c \"import os; print(os.environ['SAMPLE_TOKEN'])\"",
    )

    report = verifier.run(
        registry,
        execute=True,
        env={"SAMPLE_TOKEN": "super-secret-token"},
        workspace_root=tmp_path,
    )

    serialized = json.dumps(report)
    assert report["status"] == "pass"
    assert report["summary"]["commands_executed"] == 1
    assert report["summary"]["commands_passed"] == 1
    assert "super-secret-token" not in serialized
    assert "<redacted:SAMPLE_TOKEN>" in serialized


def test_cli_writes_dry_run_markdown(tmp_path: Path) -> None:
    verifier = load_module()
    json_out = tmp_path / "live-verify.json"
    markdown_out = tmp_path / "live-verify.md"

    exit_code = verifier.main(
        [
            "--registry",
            str(REGISTRY_PATH),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert exit_code == 0
    assert payload["mode"] == "dry_run"
    assert "External Credential Live Verifier" in markdown
    assert "blocked_missing_required_env" in markdown


def test_checked_in_dry_run_artifacts_match_current_plan() -> None:
    verifier = load_module()

    expected = verifier.run(REGISTRY_PATH, env={})
    checked_json = json.loads(DRY_RUN_JSON_PATH.read_text(encoding="utf-8"))
    checked_markdown = DRY_RUN_MARKDOWN_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")

    assert _stable_report(checked_json) == _stable_report(expected)
    assert checked_markdown == verifier.render_markdown(expected)


def test_checked_in_ready_only_execute_artifacts_match_current_run() -> None:
    verifier = load_module()

    expected = verifier.run(REGISTRY_PATH, env=_env_without_external_tokens(), ready_only=True, execute=True)
    checked_json = json.loads(READY_ONLY_JSON_PATH.read_text(encoding="utf-8"))
    checked_markdown = READY_ONLY_MARKDOWN_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")

    assert _stable_report(checked_json) == _stable_report(expected)
    assert checked_markdown == verifier.render_markdown(expected)


def _write_registry(
    tmp_path: Path,
    *,
    required_env: list[str],
    status: str = "credential_gated",
    optional_env_any_of: list[str] | None = None,
    command: str,
) -> Path:
    evidence = tmp_path / "evidence.md"
    evidence.write_text("do not claim external completion\n", encoding="utf-8")
    payload = {
        "schema_version": 1,
        "generated_at": "2026-06-05T04:00:00+09:00",
        "objective": "test registry",
        "boundaries": [
            {
                "id": "sample",
                "title": "Sample",
                "status": status,
                "owner": "operator",
                "required_env": required_env,
                "optional_env_any_of": optional_env_any_of or [],
                "blocked_until": ["operator supplies credentials"],
                "verification_commands": [command],
                "claim_policy": "do not claim complete without live credentials",
                "evidence": [
                    {
                        "path": "evidence.md",
                        "must_contain": ["do not claim external completion"],
                    }
                ],
            }
        ],
    }
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps(payload), encoding="utf-8")
    return registry


def _stable_report(report: dict) -> dict:
    return {
        "schema_version": report["schema_version"],
        "registry_path": report["registry_path"],
        "mode": report["mode"],
        "selection": report["selection"],
        "status": report["status"],
        "summary": report["summary"],
        "boundaries": report["boundaries"],
        "commands": [
            {
                "boundary_id": command["boundary_id"],
                "command": command["command"],
                "status": command["status"],
                "returncode": command["returncode"],
                "skip_reason": command["skip_reason"],
            }
            for command in report["commands"]
        ],
        "errors": report["errors"],
    }


def _env_without_external_tokens() -> dict[str, str]:
    env = dict(os.environ)
    for name in [
        "CANVA_CLIENT_ID",
        "CANVA_CLIENT_SECRET",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    ]:
        env.pop(name, None)
    return env


def _write_mixed_registry(tmp_path: Path) -> Path:
    evidence = tmp_path / "evidence.md"
    evidence.write_text("do not claim external completion\n", encoding="utf-8")
    payload = {
        "schema_version": 1,
        "generated_at": "2026-06-05T04:00:00+09:00",
        "objective": "test registry",
        "boundaries": [
            {
                "id": "blocked",
                "title": "Blocked",
                "status": "credential_gated",
                "owner": "operator",
                "required_env": ["MISSING_TOKEN"],
                "optional_env_any_of": [],
                "blocked_until": ["operator supplies credentials"],
                "verification_commands": [f"{sys.executable} -c \"print('should-not-run')\""],
                "claim_policy": "do not claim complete without live credentials",
                "evidence": [
                    {
                        "path": "evidence.md",
                        "must_contain": ["do not claim external completion"],
                    }
                ],
            },
            {
                "id": "ready",
                "title": "Ready",
                "status": "future_scoped",
                "owner": "operator",
                "required_env": [],
                "optional_env_any_of": [],
                "blocked_until": ["operator confirms local dry-run is enough"],
                "verification_commands": [f"{sys.executable} -c \"print('ready-ran')\""],
                "claim_policy": "do not claim complete without live credentials",
                "evidence": [
                    {
                        "path": "evidence.md",
                        "must_contain": ["do not claim external completion"],
                    }
                ],
            },
        ],
    }
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps(payload), encoding="utf-8")
    return registry
