import json
import subprocess
from unittest.mock import patch

from scripts import smoke_cli


def test_build_cases_defaults_to_fast_cli_gate():
    cases = smoke_cli._build_cases(include_dry_run=False)

    assert [case.name for case in cases] == ["version", "doctor", "health_check", "stats"]
    assert all(case.name != "dry_run" for case in cases)


def test_build_cases_can_include_slow_dry_run_gate():
    cases = smoke_cli._build_cases(include_dry_run=True)

    assert [case.name for case in cases][-1] == "dry_run"
    assert "--dry-run" in cases[-1].args
    assert cases[-1].timeout == smoke_cli.DRY_RUN_TIMEOUT_SECONDS
    assert cases[-1].timeout >= 300


def test_mask_sensitive_text_redacts_database_identity():
    passworded_database_url = "postgresql://" + "user:pass@example.com/db"
    pooler_user = "postgres." + "project-secret"
    visible_pooler_user = "postgres." + "project-visible"
    openai_key = "sk-" + "secretopenai123456"
    google_api_key = "AI" + "zaABCDEFGHIJKLMNOPQRST"
    team_id = "1c3c0277" + "-c0a6-4041-ba8b-eac0623e3f2c"
    masked = smoke_cli._mask_sensitive_text(
        f"{passworded_database_url} failed: tenant/user {pooler_user} not found "
        f"owner {visible_pooler_user} {openai_key} {google_api_key} "
        f"Your team {team_id} has reached its monthly spending limit"
    )

    assert "user:pass" not in masked
    assert pooler_user not in masked
    assert visible_pooler_user not in masked
    assert openai_key not in masked
    assert google_api_key not in masked
    assert team_id not in masked
    assert "postgres.<project_ref>" in masked
    assert "tenant/user ***" in masked
    assert "sk-***" in masked
    assert "AIza***" in masked
    assert "team ***" in masked


def test_output_tail_strips_ansi_and_masks_before_truncating():
    team_id = "1c3c0277" + "-c0a6-4041-ba8b-eac0623e3f2c"
    openai_key = "sk-" + "secretopenai123456"
    raw = (
        "\x1b[32mINFO\x1b[0m "
        f"Your team {team_id} has used all available credits "
        f"{openai_key}"
    )

    tail = smoke_cli._output_tail(raw, limit=120)

    assert "\x1b[" not in tail
    assert team_id not in tail
    assert openai_key not in tail
    assert "team ***" in tail
    assert "sk-***" in tail


def test_run_case_sets_no_color_env_and_sanitizes_tails(monkeypatch):
    captured = {}
    team_id = "1c3c0277" + "-c0a6-4041-ba8b-eac0623e3f2c"

    def fake_run(*args, **kwargs):
        captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="\x1b[32mOK\x1b[0m",
            stderr=f"Your team {team_id} has reached its monthly spending limit",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = smoke_cli._run_case(smoke_cli.SmokeCase("doctor", ("--doctor",), 30), "python")

    assert captured["env"]["NO_COLOR"] == "1"
    assert captured["env"]["LOGURU_COLORIZE"] == "false"
    assert "\x1b[" not in result["stdout_tail"]
    assert team_id not in result["stderr_tail"]
    assert "team ***" in result["stderr_tail"]


def test_run_smoke_writes_report(tmp_path):
    report_path = tmp_path / "smoke.json"

    def fake_run_case(case, python_exe):
        return {
            "name": case.name,
            "command": f"{python_exe} main.py {' '.join(case.args)}",
            "timeout_seconds": case.timeout,
            "duration_seconds": 0.01,
            "exit_code": 0,
            "ok": True,
            "stdout_tail": "",
            "stderr_tail": "",
        }

    with patch("scripts.smoke_cli._run_case", side_effect=fake_run_case):
        payload = smoke_cli.run_smoke(include_dry_run=False, report_path=report_path, python_exe="python")

    assert payload["status"] == "pass"
    assert report_path.exists()
    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert written["status"] == "pass"
    assert [result["name"] for result in written["results"]] == ["version", "doctor", "health_check", "stats"]


def test_run_smoke_summarizes_runtime_fallbacks_in_report(tmp_path):
    report_path = tmp_path / "smoke.json"

    def fake_run_case(case, python_exe):
        stderr_tail = ""
        if case.name == "stats":
            stderr_tail = (
                "PostgreSQL connection failed; falling back to local SQLite for this run "
                "(tenant/user *** not found)"
            )
        return {
            "name": case.name,
            "command": f"{python_exe} main.py {' '.join(case.args)}",
            "timeout_seconds": case.timeout,
            "duration_seconds": 0.01,
            "exit_code": 0,
            "ok": True,
            "stdout_tail": "",
            "stderr_tail": stderr_tail,
        }

    with patch("scripts.smoke_cli._run_case", side_effect=fake_run_case):
        payload = smoke_cli.run_smoke(include_dry_run=False, report_path=report_path, python_exe="python")

    assert payload["runtime_fallback_count"] == 1
    assert payload["runtime_fallbacks"] == [
        {
            "check": "stats",
            "stream": "stderr_tail",
            "kind": "database.sqlite_fallback",
            "snippet": (
                "PostgreSQL connection failed; falling back to local SQLite for this run "
                "(tenant/user *** not found)"
            ),
        }
    ]
    assert json.loads(report_path.read_text(encoding="utf-8"))["runtime_fallback_count"] == 1


def test_main_returns_nonzero_when_any_case_fails(tmp_path):
    report_path = tmp_path / "smoke.json"

    with patch(
        "scripts.smoke_cli.run_smoke",
        return_value={
            "status": "fail",
            "results": [{"name": "doctor", "ok": False, "duration_seconds": 0.01}],
        },
    ):
        code = smoke_cli.main(["--report", str(report_path), "--python", "python"])

    assert code == 1
