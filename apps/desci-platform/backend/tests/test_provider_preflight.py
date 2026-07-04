from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import provider_preflight  # noqa: E402


def test_provider_preflight_reuses_release_handoff_guidance() -> None:
    specs = provider_preflight.command_specs_for_provider("vercel")

    assert [spec.command for spec in specs] == [
        ("vercel", "whoami"),
        ("vercel", "env", "ls", "production"),
    ]
    assert all(spec.docs_url == "https://vercel.com/docs/cli/env" for spec in specs)


def test_provider_preflight_prefers_windows_cmd_shim(monkeypatch) -> None:
    if provider_preflight.os.name != "nt":
        return

    def fake_which(executable: str) -> str | None:
        if executable == "vercel":
            return r"C:\Users\bioju\AppData\Roaming\npm\vercel"
        if executable == "vercel.cmd":
            return r"C:\Users\bioju\AppData\Roaming\npm\vercel.cmd"
        return None

    monkeypatch.setattr(provider_preflight.shutil, "which", fake_which)

    assert provider_preflight._resolve_executable("vercel").endswith(r"\vercel.cmd")


def test_provider_preflight_reports_ready_providers_without_output_preview() -> None:
    def runner(spec: provider_preflight.CommandSpec, timeout_seconds: int) -> provider_preflight.CommandExecution:
        assert timeout_seconds == 7
        return provider_preflight.CommandExecution(
            exit_code=0,
            duration_ms=12,
            stdout="token=sk_live_should_not_be_written",
            stderr="",
        )

    payload = provider_preflight.run_preflight(
        ("github",),
        timeout_seconds=7,
        include_output_preview=False,
        runner=runner,
    )

    assert payload["ok"] is True
    assert payload["summary"]["provider_count"] == 1
    assert payload["summary"]["ready_provider_count"] == 1
    assert payload["summary"]["failed_check_count"] == 0
    assert payload["failed_checks"] == []
    assert "stdout_preview" not in payload["providers"][0]["checks"][0]


def test_provider_preflight_marks_missing_cli_and_redacts_preview() -> None:
    def runner(spec: provider_preflight.CommandSpec, timeout_seconds: int) -> provider_preflight.CommandExecution:
        return provider_preflight.CommandExecution(
            exit_code=None,
            duration_ms=0,
            command_found=False,
            error="gh executable was not found on PATH token=github_pat_abc123",
            stdout="secret=whsec_abc123",
            stderr="private_key=ghp_abc123",
        )

    payload = provider_preflight.run_preflight(
        ("github",),
        include_output_preview=True,
        runner=runner,
    )
    checks = payload["providers"][0]["checks"]

    assert payload["ok"] is False
    assert payload["summary"]["missing_cli_count"] == len(checks)
    assert payload["failed_checks"][0]["failure_reason"] == "missing_cli"
    assert all(check["failure_reason"] == "missing_cli" for check in checks)
    assert all("github_pat_" not in check.get("error", "") for check in checks)
    assert all("whsec_" not in check.get("stdout_preview", "") for check in checks)
    assert all("ghp_" not in check.get("stderr_preview", "") for check in checks)
    assert all("[REDACTED]" in check.get("error", "") for check in checks)


def test_provider_preflight_marks_missing_auth_context() -> None:
    def runner(spec: provider_preflight.CommandSpec, timeout_seconds: int) -> provider_preflight.CommandExecution:
        return provider_preflight.CommandExecution(
            exit_code=None,
            duration_ms=0,
            auth_context_missing=True,
            error="vercel auth context is not configured; set VERCEL_TOKEN or run vercel login",
        )

    payload = provider_preflight.run_preflight(
        ("vercel",),
        runner=runner,
    )
    checks = payload["providers"][0]["checks"]

    assert payload["ok"] is False
    assert payload["summary"]["auth_context_missing_count"] == len(checks)
    assert payload["failed_checks"][0]["failure_reason"] == "auth_context_missing"
    assert all(check["failure_reason"] == "auth_context_missing" for check in checks)


def test_provider_preflight_classifies_unauthorized_output_as_missing_auth_context() -> None:
    def runner(spec: provider_preflight.CommandSpec, timeout_seconds: int) -> provider_preflight.CommandExecution:
        return provider_preflight.CommandExecution(
            exit_code=1,
            duration_ms=4,
            stderr="Unauthorized. Please login with `railway login`",
        )

    payload = provider_preflight.run_preflight(
        ("railway",),
        runner=runner,
    )

    assert payload["ok"] is False
    assert payload["summary"]["auth_context_missing_count"] == payload["summary"]["failed_check_count"]
    assert payload["summary"]["missing_cli_count"] == 0
    assert payload["failed_checks"][0]["failure_reason"] == "auth_context_missing"
    assert all(
        check["failure_reason"] == "auth_context_missing"
        for check in payload["providers"][0]["checks"]
    )


def test_provider_preflight_writes_json_report_atomically(tmp_path: Path) -> None:
    output = tmp_path / "provider-preflight.json"
    payload = provider_preflight.run_preflight(
        ("github",),
        runner=lambda spec, timeout_seconds: provider_preflight.CommandExecution(exit_code=0, duration_ms=1),
    )

    provider_preflight.write_json_report(output, payload)

    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["schema_version"] == 1
    assert written["ok"] is True
    assert not (output.parent / "provider-preflight.json.tmp").exists()


def test_provider_preflight_parse_args_defaults_to_all_providers() -> None:
    args = provider_preflight.parse_args([])

    assert args.provider is None
    assert args.timeout == 15
    assert args.include_output_preview is False
