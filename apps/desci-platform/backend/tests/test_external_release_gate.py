from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import external_release_gate  # noqa: E402
import provider_preflight  # noqa: E402


def _provider_runner_ok(
    spec: provider_preflight.CommandSpec,
    timeout_seconds: int,
) -> provider_preflight.CommandExecution:
    assert timeout_seconds == 5
    return provider_preflight.CommandExecution(exit_code=0, duration_ms=1)


def _provider_runner_missing_auth(
    spec: provider_preflight.CommandSpec,
    timeout_seconds: int,
) -> provider_preflight.CommandExecution:
    return provider_preflight.CommandExecution(
        exit_code=None,
        duration_ms=0,
        auth_context_missing=True,
        error=f"{spec.provider} auth missing",
    )


def _provider_runner_missing_auth_and_project(
    spec: provider_preflight.CommandSpec,
    timeout_seconds: int,
) -> provider_preflight.CommandExecution:
    return provider_preflight.CommandExecution(
        exit_code=None,
        duration_ms=0,
        auth_context_missing=True,
        project_context_missing=True,
        error=f"{spec.provider} auth and project context missing",
    )


def test_external_release_gate_normalizes_all_targets() -> None:
    assert external_release_gate.normalize_targets(["all"]) == ["railway", "vercel", "amoy", "github"]
    assert external_release_gate.provider_targets_for(["railway", "amoy", "github"]) == ["railway", "github"]


def test_external_release_gate_passes_when_env_and_provider_checks_are_ready(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("GITLEAKS_LICENSE=license-token\n", encoding="utf-8")

    payload = external_release_gate.run_external_gate(
        targets=("github",),
        env_files=[env_file],
        include_process_env=False,
        provider_timeout_seconds=5,
        provider_runner=_provider_runner_ok,
    )

    assert payload["ok"] is True
    assert payload["failed_surfaces"] == []
    assert payload["summary"]["deploy_failed"] == 0
    assert payload["summary"]["provider_ready"] == 1
    assert payload["summary"]["provider_check_count"] == 2
    assert payload["summary"]["provider_missing_cli_count"] == 0
    assert payload["summary"]["provider_auth_context_missing_count"] == 0
    assert payload["summary"]["provider_project_context_missing_count"] == 0
    assert payload["provider_preflight"]["summary"]["passed_check_count"] == 2


def test_external_release_gate_fails_closed_for_deploy_and_provider_blockers(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    payload = external_release_gate.run_external_gate(
        targets=("github",),
        env_files=[env_file],
        include_process_env=False,
        provider_timeout_seconds=5,
        provider_runner=_provider_runner_missing_auth,
    )

    assert payload["ok"] is False
    assert payload["failed_surfaces"] == ["deploy_readiness", "provider_preflight"]
    assert payload["deploy_readiness"]["summary"]["failed_checks"] == ["github_gitleaks_license"]
    assert payload["summary"]["provider_check_count"] == 2
    assert payload["summary"]["provider_missing_cli_count"] == 0
    assert payload["summary"]["provider_auth_context_missing_count"] == 2
    assert payload["summary"]["provider_project_context_missing_count"] == 0
    assert payload["provider_preflight"]["summary"]["auth_context_missing_count"] == 2
    assert payload["provider_preflight"]["failed_checks"][0]["failure_reason"] == "auth_context_missing"


def test_external_release_gate_propagates_provider_project_context_count(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    payload = external_release_gate.run_external_gate(
        targets=("vercel",),
        env_files=[env_file],
        include_process_env=False,
        provider_timeout_seconds=5,
        provider_runner=_provider_runner_missing_auth_and_project,
    )

    assert payload["ok"] is False
    assert payload["summary"]["provider_auth_context_missing_count"] == 2
    assert payload["summary"]["provider_project_context_missing_count"] == 2
    assert payload["provider_preflight"]["summary"]["project_context_missing_count"] == 2
    assert all(check["project_context_missing"] is True for check in payload["provider_preflight"]["failed_checks"])


def test_external_release_gate_text_report_includes_provider_preflight_counts(
    capsys,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    payload = external_release_gate.run_external_gate(
        targets=("github",),
        env_files=[env_file],
        include_process_env=False,
        provider_timeout_seconds=5,
        provider_runner=_provider_runner_missing_auth,
    )

    external_release_gate.print_text_report(payload)

    output = capsys.readouterr().out
    assert "provider_checks=2" in output
    assert "missing_cli=0" in output
    assert "auth_context_missing=2" in output
    assert "project_context_missing=0" in output


def test_external_release_gate_skips_provider_preflight_for_amoy_only(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    payload = external_release_gate.run_external_gate(
        targets=("amoy",),
        env_files=[env_file],
        include_process_env=False,
        provider_timeout_seconds=5,
        provider_runner=_provider_runner_missing_auth,
    )

    assert payload["ok"] is False
    assert payload["failed_surfaces"] == ["deploy_readiness"]
    assert payload["provider_targets"] == []
    assert payload["provider_preflight"]["skipped"] is True
    assert payload["provider_preflight"]["summary"]["provider_count"] == 0


def test_external_release_gate_loads_provider_template_dir_after_default_env_files(tmp_path: Path) -> None:
    provider_dir = tmp_path / "provider-templates"
    provider_dir.mkdir()
    github_env = provider_dir / "github.env"
    github_env.write_text("GITLEAKS_LICENSE=license-token\n", encoding="utf-8")

    env_files = external_release_gate.resolve_env_files(
        [tmp_path / "missing.env"],
        provider_template_dir=provider_dir,
    )
    payload = external_release_gate.run_external_gate(
        targets=("github",),
        env_files=env_files,
        include_process_env=False,
        provider_timeout_seconds=5,
        provider_runner=_provider_runner_ok,
    )

    assert env_files == [tmp_path / "missing.env", github_env]
    assert payload["ok"] is True
    assert payload["deploy_readiness"]["summary"]["failed_checks"] == []


def test_external_release_gate_rejects_missing_provider_template_dir() -> None:
    code = external_release_gate.main(["--provider-template-dir", "missing-provider-templates"])

    assert code == 2


def test_external_release_gate_writes_json_report_atomically(tmp_path: Path) -> None:
    output = tmp_path / "external-release-gate.json"
    payload = external_release_gate.run_external_gate(
        targets=("github",),
        env_files=[tmp_path / "missing.env"],
        include_process_env=False,
        provider_timeout_seconds=5,
        provider_runner=_provider_runner_ok,
    )

    external_release_gate.write_json_report(output, payload)

    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["schema_version"] == 1
    assert written["ok"] is False
    assert not (output.parent / "external-release-gate.json.tmp").exists()


def test_external_release_gate_parse_args_defaults() -> None:
    args = external_release_gate.parse_args([])

    assert args.target == []
    assert args.env_file == []
    assert args.provider_timeout == 12
    assert args.ignore_process_env is False
