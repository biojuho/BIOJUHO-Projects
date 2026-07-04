from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import provider_preflight  # noqa: E402


def fake_secret(*parts: str) -> str:
    return "".join(parts)


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
    fake_key = fake_secret("sk_", "live_", "should_not_be_written")

    def runner(spec: provider_preflight.CommandSpec, timeout_seconds: int) -> provider_preflight.CommandExecution:
        assert timeout_seconds == 7
        return provider_preflight.CommandExecution(
            exit_code=0,
            duration_ms=12,
            stdout=f"token={fake_key}",
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
    fake_webhook_secret = fake_secret("whsec", "_abc123")
    fake_gh_token = fake_secret("ghp", "_abc123")

    def runner(spec: provider_preflight.CommandSpec, timeout_seconds: int) -> provider_preflight.CommandExecution:
        return provider_preflight.CommandExecution(
            exit_code=None,
            duration_ms=0,
            command_found=False,
            error="gh executable was not found on PATH token=github_pat_abc123",
            stdout=f"secret={fake_webhook_secret}",
            stderr=f"private_key={fake_gh_token}",
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
    assert payload["failed_checks"][0]["remediation"].startswith("Install the gh CLI")
    assert all(check["failure_reason"] == "missing_cli" for check in checks)
    assert all(check["remediation"].startswith("Install the gh CLI") for check in checks)
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
    assert "VERCEL_TOKEN" in payload["failed_checks"][0]["remediation"]
    assert all(check["failure_reason"] == "auth_context_missing" for check in checks)
    assert all("VERCEL_TOKEN" in check["remediation"] for check in checks)


def test_provider_preflight_detects_vercel_project_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("VERCEL_ORG_ID", raising=False)
    monkeypatch.delenv("VERCEL_PROJECT_ID", raising=False)
    project_json = tmp_path / ".vercel" / "project.json"
    project_json.parent.mkdir()
    project_json.write_text(
        json.dumps({"orgId": "team_example", "projectId": "prj_example"}),
        encoding="utf-8",
    )

    assert provider_preflight._has_vercel_project_context(tmp_path) is True
    assert provider_preflight._has_vercel_project_context(tmp_path / "missing") is False


def test_provider_preflight_execute_command_marks_vercel_contexts_missing(monkeypatch) -> None:
    spec = provider_preflight.command_specs_for_provider("vercel")[0]

    monkeypatch.setattr(provider_preflight, "_resolve_executable", lambda executable: "vercel.cmd")
    monkeypatch.setattr(provider_preflight, "_has_vercel_auth_context", lambda: False)
    monkeypatch.setattr(provider_preflight, "_has_vercel_project_context", lambda: False)

    execution = provider_preflight.execute_command(spec, timeout_seconds=1)
    payload = provider_preflight.check_payload(spec, execution)

    assert execution.auth_context_missing is True
    assert execution.project_context_missing is True
    assert payload["failure_reason"] == "auth_context_missing"
    assert payload["project_context_missing"] is True
    assert "vercel link" in payload["remediation"]
    assert "VERCEL_ORG_ID" in payload["remediation"]


def test_provider_preflight_counts_vercel_project_context_missing() -> None:
    def runner(spec: provider_preflight.CommandSpec, timeout_seconds: int) -> provider_preflight.CommandExecution:
        if provider_preflight._vercel_command_needs_project_context(spec):
            return provider_preflight.CommandExecution(
                exit_code=None,
                duration_ms=0,
                project_context_missing=True,
                error="vercel project context is not configured",
            )
        return provider_preflight.CommandExecution(exit_code=0, duration_ms=1)

    payload = provider_preflight.run_preflight(("vercel",), runner=runner)
    markdown = provider_preflight.render_markdown_report(payload)

    assert payload["ok"] is False
    assert payload["summary"]["auth_context_missing_count"] == 0
    assert payload["summary"]["project_context_missing_count"] == 1
    assert payload["failed_checks"][0]["failure_reason"] == "project_context_missing"
    assert payload["failed_checks"][0]["project_context_missing"] is True
    assert "Project context missing: `1`" in markdown
    assert "project_context=`missing`" in markdown
    assert "vercel link" in markdown


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
    assert payload["failed_checks"][0]["docs_url"] == "https://docs.railway.com/variables"
    assert "railway login" in payload["failed_checks"][0]["remediation"]
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


def test_provider_preflight_markdown_report_lists_sanitized_failed_checks() -> None:
    fake_key = fake_secret("sk_", "live_", "should_not_render")

    def runner(spec: provider_preflight.CommandSpec, timeout_seconds: int) -> provider_preflight.CommandExecution:
        return provider_preflight.CommandExecution(
            exit_code=1,
            duration_ms=4,
            stderr=f"Unauthorized token={fake_key}. Please login.",
        )

    payload = provider_preflight.run_preflight(
        ("railway",),
        include_output_preview=True,
        runner=runner,
    )
    markdown = provider_preflight.render_markdown_report(payload)

    assert "# DeSci Provider Preflight" in markdown
    assert "Providers ready: `0/1`" in markdown
    assert "`railway` `railway whoami`: `auth_context_missing`" in markdown
    assert "Run `railway login`" in markdown
    assert "stdout_preview" not in markdown
    assert "stderr_preview" not in markdown
    assert fake_key not in markdown
    assert "Unauthorized" not in markdown


def test_provider_preflight_writes_markdown_report_atomically(tmp_path: Path) -> None:
    output = tmp_path / "provider-preflight.md"
    payload = provider_preflight.run_preflight(
        ("github",),
        runner=lambda spec, timeout_seconds: provider_preflight.CommandExecution(exit_code=0, duration_ms=1),
    )

    provider_preflight.write_markdown_report(output, payload)

    markdown = output.read_text(encoding="utf-8")
    assert markdown.startswith("# DeSci Provider Preflight")
    assert "Status: `true`" in markdown
    assert not (output.parent / "provider-preflight.md.tmp").exists()


def test_provider_preflight_parse_args_defaults_to_all_providers() -> None:
    args = provider_preflight.parse_args([])

    assert args.provider is None
    assert args.timeout == 15
    assert args.include_output_preview is False
    assert args.markdown_out is None


def test_provider_preflight_console_prints_failed_check_docs(monkeypatch, capsys) -> None:
    def fake_run_preflight(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "ok": False,
            "providers": [
                {
                    "provider": "vercel",
                    "ok": False,
                    "checks": [
                        {
                            "command": "vercel whoami",
                            "ok": False,
                            "failure_reason": "auth_context_missing",
                            "remediation": "Set `VERCEL_TOKEN` or run `vercel login`.",
                            "docs_url": "https://vercel.com/docs/cli/env",
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(provider_preflight, "run_preflight", fake_run_preflight)

    code = provider_preflight.main(["--provider", "vercel"])

    output = capsys.readouterr().out
    assert code == 1
    assert "vercel whoami: FAIL auth_context_missing docs=https://vercel.com/docs/cli/env" in output
    assert "next=Set `VERCEL_TOKEN` or run `vercel login`." in output


def test_provider_preflight_cli_writes_markdown(monkeypatch, tmp_path: Path, capsys) -> None:
    markdown_out = tmp_path / "provider-preflight.md"

    def fake_run_preflight(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "ok": True,
            "generated_at": "2026-07-04T00:00:00+00:00",
            "summary": {
                "provider_count": 1,
                "ready_provider_count": 1,
                "check_count": 1,
                "passed_check_count": 1,
                "failed_check_count": 0,
                "missing_cli_count": 0,
                "auth_context_missing_count": 0,
            },
            "providers": [
                {
                    "provider": "github",
                    "ok": True,
                    "docs_url": "https://docs.github.com/actions/security-guides/using-secrets-in-github-actions",
                    "checks": [{"command": "gh auth status", "ok": True}],
                }
            ],
            "failed_checks": [],
        }

    monkeypatch.setattr(provider_preflight, "run_preflight", fake_run_preflight)

    code = provider_preflight.main(["--provider", "github", "--markdown-out", str(markdown_out)])

    output = capsys.readouterr().out
    assert code == 0
    assert f"[provider-preflight] markdown written: {markdown_out}" in output
    assert "Providers ready: `1/1`" in markdown_out.read_text(encoding="utf-8")
