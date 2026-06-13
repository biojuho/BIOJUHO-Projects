from __future__ import annotations

import io
import json
import os
import sys
from argparse import Namespace
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
OPS_SCRIPTS = WORKSPACE_ROOT / "ops" / "scripts"
if str(OPS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OPS_SCRIPTS))

import complete_goal_gate_common as gate_common
import getdaytrends_update_credentials as credentials


def _write_envs(tmp_path: Path) -> tuple[Path, Path]:
    root_env = tmp_path / ".env"
    local_env = tmp_path / "automation" / "getdaytrends" / ".env"
    local_env.parent.mkdir(parents=True, exist_ok=True)
    root_env.write_text("SUPABASE_URL=https://projectref.supabase.co\n", encoding="utf-8")
    local_env.write_text("DAILYNEWS_DISABLED_LLM_PROVIDERS=google\n", encoding="utf-8")
    return root_env, local_env


def _write_json_artifact(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _pooler_url(password: str, project_ref: str = "projectref") -> str:
    return "".join(
        [
            "postgresql://",
            "postgres",
            ".",
            project_ref,
            ":",
            password,
            "@",
            "aws-0-us-east-1.pooler.supabase.com",
            ":6543/postgres",
        ]
    )


def _clear_update_env(monkeypatch) -> None:
    for name in credentials.UPDATE_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_input_status_exposes_non_secret_change_marker(tmp_path: Path) -> None:
    root_env, local_env = _write_envs(tmp_path)
    staged_url = _pooler_url("value-one")

    payload = credentials.build_input_status(
        workspace_root=tmp_path,
        env_path=root_env,
        local_env_path=local_env,
        environ={"GETDAYTRENDS_NEW_DATABASE_URL": staged_url},
    )

    assert payload["status"] == "changed"
    assert payload["rerun_recommended"] is True
    assert payload["safe_to_skip_strict_readiness_until_credential_inputs_change"] is False
    assert payload["input_signal_fingerprint"]
    assert payload["input_signal"]["credential_env_present"] is True
    assert payload["input_signal"]["present_update_env_vars"] == ["GETDAYTRENDS_NEW_DATABASE_URL"]
    assert payload["input_signal"]["material_scope"] == "redacted_env_fingerprints_and_artifact_mtime_flags"
    assert payload["launch_blocker_summary"]["status"] == "credential_input_changed"
    assert payload["operator_next_action"] == "run_post_update_verification"
    assert "super-secret" not in json.dumps(payload, ensure_ascii=False)
    assert staged_url not in json.dumps(payload, ensure_ascii=False)


def test_help_documents_input_status_current_alias(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        credentials.parse_args(["--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    normalized = " ".join(output.split())
    assert "--current-json-out" in output
    assert "current-alias JSON report" in output
    assert "writes both dated and current JSON aliases" in normalized


def test_latest_scheduler_artifact_prefers_payload_timestamp_over_mtime(tmp_path: Path) -> None:
    scheduler_dir = tmp_path / "scheduler"
    older = scheduler_dir / "run_2026-06-05_020000.json"
    newer = scheduler_dir / "run_2026-06-05_030000.json"
    _write_json_artifact(older, {"started_at": "2026-06-05T02:00:00+00:00"})
    _write_json_artifact(newer, {"started_at": "2026-06-05T03:00:00+00:00"})
    os.utime(newer, (1_700_000_000, 1_700_000_000))
    os.utime(older, (1_700_000_100, 1_700_000_100))

    assert credentials._latest_scheduler_artifact(scheduler_dir) == newer


def test_input_status_default_writes_dated_and_current_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _clear_update_env(monkeypatch)
    root_env, local_env = _write_envs(tmp_path)
    dated_json = tmp_path / "var" / "dated-status.json"
    current_json = tmp_path / "var" / "current-status.json"
    markdown_out = tmp_path / "status.md"
    monkeypatch.setattr(credentials, "DEFAULT_JSON_OUT", dated_json)
    monkeypatch.setattr(credentials, "DEFAULT_CURRENT_JSON_OUT", current_json)

    exit_code = credentials.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--input-status",
            "--markdown-out",
            str(markdown_out),
        ]
    )

    assert exit_code == 0
    dated_report = json.loads(dated_json.read_text(encoding="utf-8"))
    current_report = json.loads(current_json.read_text(encoding="utf-8"))
    assert dated_report["input_signal_fingerprint"] == current_report["input_signal_fingerprint"]
    assert dated_report["status"] == current_report["status"] == "unchanged"


def test_input_status_explicit_json_out_does_not_write_default_current_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _clear_update_env(monkeypatch)
    root_env, local_env = _write_envs(tmp_path)
    explicit_json = tmp_path / "explicit-status.json"
    current_json = tmp_path / "var" / "current-status.json"
    markdown_out = tmp_path / "status.md"
    monkeypatch.setattr(credentials, "DEFAULT_CURRENT_JSON_OUT", current_json)

    exit_code = credentials.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--input-status",
            "--json-out",
            str(explicit_json),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    assert exit_code == 0
    assert explicit_json.exists()
    assert not current_json.exists()


def test_windows_scoped_staged_credential_recommends_rerun(tmp_path: Path) -> None:
    root_env, local_env = _write_envs(tmp_path)
    staged_url = _pooler_url("windows-scope")

    payload = credentials.build_input_status(
        workspace_root=tmp_path,
        env_path=root_env,
        local_env_path=local_env,
        environ={},
        scoped_env={"User": {"GETDAYTRENDS_NEW_DATABASE_URL": staged_url}, "Machine": {}},
    )

    assert payload["status"] == "changed"
    assert payload["rerun_recommended"] is True
    assert payload["safe_to_skip_strict_readiness_until_credential_inputs_change"] is False
    assert payload["process_update_env_var_present"] is False
    assert payload["windows_update_env_var_present"] is True
    assert payload["any_update_env_var_present"] is True
    assert payload["credential_update_env_vars"]["GETDAYTRENDS_NEW_DATABASE_URL"]["source"] == "User"
    assert payload["input_signal"]["windows_present_update_env_vars"] == ["User:GETDAYTRENDS_NEW_DATABASE_URL"]
    assert staged_url not in json.dumps(payload, ensure_ascii=False)


def test_input_status_reports_external_readiness_blocker_without_failure_names(tmp_path: Path) -> None:
    root_env, local_env = _write_envs(tmp_path)
    _write_json_artifact(
        tmp_path / "automation" / "getdaytrends" / "logs" / "readiness" / "readiness_latest.json",
        {
            "status": "fail",
            "generated_at": "2026-06-10T20:28:49+09:00",
            "summary": {"total": 9, "passed": 7, "failed": 2, "warnings": 0},
        },
    )
    _write_json_artifact(
        tmp_path / "var" / "workspace-smoke-getdaytrends-launch-final.json",
        {
            "status": "complete",
            "generated_at": "2026-06-10T08:47:47+00:00",
            "summary": {
                "total": 7,
                "passed": 6,
                "failed": 1,
                "expected_external_failures": ["getdaytrends launch readiness gate"],
                "unexpected_failures": [],
            },
        },
    )

    payload = credentials.build_input_status(
        workspace_root=tmp_path,
        env_path=root_env,
        local_env_path=local_env,
        environ={},
    )

    summary = payload["launch_blocker_summary"]
    assert payload["status"] == "unchanged"
    assert summary["status"] == "external_readiness_blocked"
    assert summary["reason"] == "readiness_failed_without_new_credential_input"
    assert summary["readiness_status"] == "fail"
    assert summary["workspace_smoke_status"] == "complete"
    assert summary["expected_external_failures"] == 1
    assert summary["unexpected_failures"] == 0
    assert summary["blocking_evidence_kinds"] == ["readiness_failed"]
    assert summary["blocking_evidence_count"] == 1
    assert payload["operator_next_action"] == "stage_corrected_provider_console_database_url_then_run_local_update"
    assert "getdaytrends launch readiness gate" not in json.dumps(summary, ensure_ascii=False)


def test_input_status_summarizes_readiness_scheduler_artifact_without_paths(tmp_path: Path) -> None:
    root_env, local_env = _write_envs(tmp_path)
    artifact_path = tmp_path / "automation" / "getdaytrends" / "logs" / "scheduler" / "run_2026-06-10_233626.json"
    command = "python main.py --one-shot --country korea --limit 1 --dry-run"
    _write_json_artifact(
        artifact_path,
        {
            "artifact_path": str(artifact_path),
            "summary_fallback_used": False,
        },
    )
    _write_json_artifact(
        tmp_path / "automation" / "getdaytrends" / "logs" / "readiness" / "readiness_latest.json",
        {
            "status": "pass",
            "generated_at": "2026-06-10T23:43:20+09:00",
            "summary": {"total": 8, "passed": 8, "failed": 0, "warnings": 0},
            "checks": [
                {
                    "name": "scheduler_artifact",
                    "ok": True,
                    "level": "OK",
                    "message": "Latest scheduler artifact is successful and has matching logs.",
                    "evidence": {
                        "path": str(artifact_path),
                        "status": "success",
                        "exit_code": 0,
                        "command": command,
                    },
                }
            ],
        },
    )

    payload = credentials.build_input_status(
        workspace_root=tmp_path,
        env_path=root_env,
        local_env_path=local_env,
        environ={},
    )

    scheduler = payload["evidence_summary"]["readiness"]["scheduler_artifact"]
    assert scheduler == {
        "ok": True,
        "level": "OK",
        "status": "success",
        "exit_code": 0,
        "artifact_path_present": True,
        "artifact_path_matches_latest": True,
        "summary_fallback_used": False,
        "summary_fallback_used_present": True,
        "summary_fallback_used_valid": True,
        "selected_artifact_is_latest": True,
        "latest_artifact_path_present": True,
        "latest_artifact_path_matches_latest": True,
        "latest_summary_fallback_used": False,
        "latest_summary_fallback_used_present": True,
        "latest_summary_fallback_used_valid": True,
    }
    serialized = json.dumps(payload, ensure_ascii=False)
    assert str(artifact_path) not in serialized
    assert command not in serialized


def test_input_status_flags_stale_readiness_scheduler_artifact_without_paths(tmp_path: Path) -> None:
    root_env, local_env = _write_envs(tmp_path)
    scheduler_dir = tmp_path / "automation" / "getdaytrends" / "logs" / "scheduler"
    selected_artifact = scheduler_dir / "run_2026-06-10_023629.json"
    latest_artifact = scheduler_dir / "run_2026-06-10_233626.json"
    _write_json_artifact(
        selected_artifact,
        {
            "status": "success",
            "exit_code": 0,
        },
    )
    _write_json_artifact(
        latest_artifact,
        {
            "artifact_path": str(latest_artifact),
            "summary_fallback_used": False,
            "status": "success",
            "exit_code": 0,
        },
    )
    os.utime(selected_artifact, (1_700_000_000, 1_700_000_000))
    os.utime(latest_artifact, (1_700_000_100, 1_700_000_100))
    _write_json_artifact(
        tmp_path / "automation" / "getdaytrends" / "logs" / "readiness" / "readiness_latest.json",
        {
            "status": "fail",
            "generated_at": "2026-06-10T20:28:49+09:00",
            "summary": {"total": 9, "passed": 7, "failed": 2, "warnings": 0},
            "checks": [
                {
                    "name": "scheduler_artifact",
                    "ok": True,
                    "level": "OK",
                    "evidence": {
                        "path": str(selected_artifact),
                        "status": "success",
                        "exit_code": 0,
                    },
                }
            ],
        },
    )

    payload = credentials.build_input_status(
        workspace_root=tmp_path,
        env_path=root_env,
        local_env_path=local_env,
        environ={},
    )

    scheduler = payload["evidence_summary"]["readiness"]["scheduler_artifact"]
    assert scheduler["artifact_path_present"] is False
    assert scheduler["summary_fallback_used_present"] is False
    assert scheduler["selected_artifact_is_latest"] is False
    assert scheduler["latest_artifact_path_present"] is True
    assert scheduler["latest_artifact_path_matches_latest"] is True
    assert scheduler["latest_summary_fallback_used"] is False
    assert scheduler["latest_summary_fallback_used_present"] is True
    assert scheduler["latest_summary_fallback_used_valid"] is True
    summary = payload["launch_blocker_summary"]
    assert summary["blocking_evidence_kinds"] == ["readiness_failed"]
    assert summary["operator_attention_kinds"] == [
        "scheduler_artifact_evidence_stale",
        "readiness_selected_scheduler_schema_older_than_latest",
        "readiness_selected_scheduler_fallback_field_missing",
    ]
    assert summary["operator_attention_count"] == 3
    assert summary["readiness_scheduler_artifact_stale"] is True
    assert summary["latest_scheduler_artifact_evidence_complete"] is True
    serialized = json.dumps(payload, ensure_ascii=False)
    assert str(selected_artifact) not in serialized
    assert str(latest_artifact) not in serialized


def test_input_status_preserves_multiple_blocking_evidence_kinds_without_names(tmp_path: Path) -> None:
    root_env, local_env = _write_envs(tmp_path)
    _write_json_artifact(
        tmp_path / "automation" / "getdaytrends" / "logs" / "readiness" / "readiness_latest.json",
        {
            "status": "fail",
            "generated_at": "2026-06-10T20:28:49+09:00",
            "summary": {"total": 9, "passed": 7, "failed": 2, "warnings": 0},
        },
    )
    _write_json_artifact(
        tmp_path / "var" / "workspace-smoke-getdaytrends-launch-final.json",
        {
            "status": "complete",
            "generated_at": "2026-06-10T08:47:47+00:00",
            "summary": {
                "total": 7,
                "passed": 5,
                "failed": 2,
                "expected_external_failures": ["getdaytrends launch readiness gate"],
                "unexpected_failures": ["getdaytrends browser smoke"],
            },
        },
    )

    payload = credentials.build_input_status(
        workspace_root=tmp_path,
        env_path=root_env,
        local_env_path=local_env,
        environ={},
    )

    summary = payload["launch_blocker_summary"]
    assert summary["status"] == "external_readiness_blocked"
    assert summary["blocking_evidence_kinds"] == [
        "readiness_failed",
        "workspace_smoke_unexpected_failures",
    ]
    assert summary["blocking_evidence_count"] == 2
    assert summary["unexpected_failures"] == 1
    assert "getdaytrends browser smoke" not in json.dumps(summary, ensure_ascii=False)


def test_blank_staged_credential_is_visible_input_signal(tmp_path: Path) -> None:
    root_env, local_env = _write_envs(tmp_path)

    payload = credentials.build_input_status(
        workspace_root=tmp_path,
        env_path=root_env,
        local_env_path=local_env,
        environ={"GETDAYTRENDS_NEW_OPENAI_API_KEY": ""},
    )

    assert payload["status"] == "changed"
    assert payload["rerun_recommended"] is True
    assert payload["process_update_env_var_present"] is True
    assert payload["any_update_env_var_present"] is True
    assert payload["credential_update_env_vars"]["GETDAYTRENDS_NEW_OPENAI_API_KEY"] == {
        "present": True,
        "length": 0,
        "fingerprint": "",
        "source": "Process",
    }
    assert payload["input_signal"]["present_update_env_vars"] == ["GETDAYTRENDS_NEW_OPENAI_API_KEY"]


def test_blank_windows_scoped_staged_credential_is_visible_input_signal(tmp_path: Path) -> None:
    root_env, local_env = _write_envs(tmp_path)

    payload = credentials.build_input_status(
        workspace_root=tmp_path,
        env_path=root_env,
        local_env_path=local_env,
        environ={},
        scoped_env={"User": {}, "Machine": {"GETDAYTRENDS_NEW_GOOGLE_API_KEY": ""}},
    )

    assert payload["status"] == "changed"
    assert payload["rerun_recommended"] is True
    assert payload["process_update_env_var_present"] is False
    assert payload["windows_update_env_var_present"] is True
    assert payload["any_update_env_var_present"] is True
    assert payload["credential_update_env_vars"]["GETDAYTRENDS_NEW_GOOGLE_API_KEY"] == {
        "present": True,
        "length": 0,
        "fingerprint": "",
        "source": "Machine",
    }
    assert payload["windows_credential_update_env_vars"]["Machine"]["GETDAYTRENDS_NEW_GOOGLE_API_KEY"] == {
        "present": True,
        "length": 0,
        "fingerprint": "",
    }
    assert payload["input_signal"]["windows_present_update_env_vars"] == ["Machine:GETDAYTRENDS_NEW_GOOGLE_API_KEY"]


def test_update_accepts_staged_supabase_url_matching_staged_database_url(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root_env = tmp_path / ".env"
    local_env = tmp_path / "automation" / "getdaytrends" / ".env"
    local_env.parent.mkdir(parents=True, exist_ok=True)
    root_env.write_text("SUPABASE_URL=https://oldproject.supabase.co\n", encoding="utf-8")
    local_env.write_text("", encoding="utf-8")
    staged_database_url = _pooler_url("coordinated", project_ref="newproject")
    monkeypatch.setenv("GETDAYTRENDS_NEW_SUPABASE_URL", "https://newproject.supabase.co")
    monkeypatch.setenv("GETDAYTRENDS_NEW_DATABASE_URL", staged_database_url)

    report = credentials.update_credentials(
        Namespace(
            env_path=root_env,
            local_env_path=local_env,
            database_url_stdin=False,
            write=False,
            allow_host_change=False,
        )
    )

    assert report["status"] == "planned"
    assert report["updated_keys"] == ["DATABASE_URL", "SUPABASE_URL"]
    assert report["updated_key_sources"] == {
        "DATABASE_URL": "GETDAYTRENDS_NEW_DATABASE_URL",
        "SUPABASE_URL": "GETDAYTRENDS_NEW_SUPABASE_URL",
    }
    assert report["updated_key_source_scopes"] == {
        "DATABASE_URL": "Process",
        "SUPABASE_URL": "Process",
    }
    assert report["new_database_url_shape"]["project_refs_match"] is True
    assert report["new_database_url_shape"]["supabase_url_project_ref_fp"]
    assert "newproject" not in json.dumps(report, ensure_ascii=False)
    assert staged_database_url not in json.dumps(report, ensure_ascii=False)


def test_coordinated_supabase_and_database_write_redacts_report_and_writes_backup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root_env = tmp_path / ".env"
    local_env = tmp_path / "automation" / "getdaytrends" / ".env"
    report_path = tmp_path / "coordinated-write.json"
    local_env.parent.mkdir(parents=True, exist_ok=True)
    root_env.write_text("SUPABASE_URL=https://oldproject.supabase.co\n", encoding="utf-8")
    local_env.write_text("", encoding="utf-8")
    staged_supabase_url = "https://newproject.supabase.co"
    staged_database_url = _pooler_url("coordinated-write", project_ref="newproject")
    monkeypatch.setenv("GETDAYTRENDS_NEW_SUPABASE_URL", staged_supabase_url)
    monkeypatch.setenv("GETDAYTRENDS_NEW_DATABASE_URL", staged_database_url)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "updated"
    assert report["dry_run"] is False
    assert report["updated_keys"] == ["DATABASE_URL", "SUPABASE_URL"]
    assert report["updated_key_sources"] == {
        "DATABASE_URL": "GETDAYTRENDS_NEW_DATABASE_URL",
        "SUPABASE_URL": "GETDAYTRENDS_NEW_SUPABASE_URL",
    }
    assert report["updated_key_source_scopes"] == {
        "DATABASE_URL": "Process",
        "SUPABASE_URL": "Process",
    }
    assert report["new_database_url_shape"]["project_refs_match"] is True
    assert len(report["backup_paths"]) == 1
    backup_path = Path(report["backup_paths"][0])
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == ""
    local_env_text = local_env.read_text(encoding="utf-8")
    assert f"DATABASE_URL={staged_database_url}" in local_env_text
    assert f"SUPABASE_URL={staged_supabase_url}" in local_env_text
    serialized = json.dumps(report, ensure_ascii=False)
    assert "newproject" not in serialized
    assert "coordinated-write" not in serialized
    assert staged_database_url not in serialized
    assert staged_supabase_url not in serialized


def test_provider_only_update_reports_redacted_sources(tmp_path: Path, monkeypatch) -> None:
    root_env, local_env = _write_envs(tmp_path)
    staged_key = "".join(["sk", "-proj-", "redacted-source-test"])
    monkeypatch.setenv("GETDAYTRENDS_NEW_OPENAI_API_KEY", staged_key)
    monkeypatch.setenv("GETDAYTRENDS_NEW_GOOGLE_API_KEY", "google-provider-key")

    report = credentials.update_credentials(
        Namespace(
            env_path=root_env,
            local_env_path=local_env,
            database_url_stdin=False,
            write=False,
            allow_host_change=False,
        )
    )

    assert report["status"] == "planned"
    assert report["updated_keys"] == ["GOOGLE_API_KEY", "OPENAI_API_KEY"]
    assert report["updated_key_sources"] == {
        "GOOGLE_API_KEY": "GETDAYTRENDS_NEW_GOOGLE_API_KEY",
        "OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY",
    }
    assert report["updated_key_source_scopes"] == {
        "GOOGLE_API_KEY": "Process",
        "OPENAI_API_KEY": "Process",
    }
    serialized = json.dumps(report, ensure_ascii=False)
    assert staged_key not in serialized
    assert "google-provider-key" not in serialized


def test_provider_only_main_stdout_redacts_successful_plan(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    staged_openai = "".join(["sk", "-proj-", "stdout-provider-test"])
    staged_google = "google-stdout-provider-key"
    monkeypatch.setenv("GETDAYTRENDS_NEW_OPENAI_API_KEY", staged_openai)
    monkeypatch.setenv("GETDAYTRENDS_NEW_GOOGLE_API_KEY", staged_google)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
        ]
    )

    assert exit_code == 0
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "planned"
    assert stdout_report["updated_keys"] == ["GOOGLE_API_KEY", "OPENAI_API_KEY"]
    assert stdout_report["updated_key_sources"] == {
        "GOOGLE_API_KEY": "GETDAYTRENDS_NEW_GOOGLE_API_KEY",
        "OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY",
    }
    assert stdout_report["updated_key_source_scopes"] == {
        "GOOGLE_API_KEY": "Process",
        "OPENAI_API_KEY": "Process",
    }
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert staged_openai not in stdout_serialized
    assert staged_google not in stdout_serialized


def test_provider_only_main_json_out_redacts_successful_plan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    report_path = tmp_path / "provider-plan.json"
    staged_openai = "".join(["sk", "-proj-", "json-provider-test"])
    staged_google = "google-json-provider-key"
    monkeypatch.setenv("GETDAYTRENDS_NEW_OPENAI_API_KEY", staged_openai)
    monkeypatch.setenv("GETDAYTRENDS_NEW_GOOGLE_API_KEY", staged_google)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "planned"
    assert report["updated_keys"] == ["GOOGLE_API_KEY", "OPENAI_API_KEY"]
    assert report["updated_key_sources"] == {
        "GOOGLE_API_KEY": "GETDAYTRENDS_NEW_GOOGLE_API_KEY",
        "OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY",
    }
    assert report["updated_key_source_scopes"] == {
        "GOOGLE_API_KEY": "Process",
        "OPENAI_API_KEY": "Process",
    }
    serialized = json.dumps(report, ensure_ascii=False)
    assert staged_openai not in serialized
    assert staged_google not in serialized


def test_provider_only_main_write_json_out_redacts_report_and_writes_backup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    report_path = tmp_path / "provider-write.json"
    staged_openai = "".join(["sk", "-proj-", "write-provider-test"])
    staged_google = "google-write-provider-key"
    monkeypatch.setenv("GETDAYTRENDS_NEW_OPENAI_API_KEY", staged_openai)
    monkeypatch.setenv("GETDAYTRENDS_NEW_GOOGLE_API_KEY", staged_google)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "updated"
    assert report["dry_run"] is False
    assert report["updated_keys"] == ["GOOGLE_API_KEY", "OPENAI_API_KEY"]
    assert report["updated_key_sources"] == {
        "GOOGLE_API_KEY": "GETDAYTRENDS_NEW_GOOGLE_API_KEY",
        "OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY",
    }
    assert report["updated_key_source_scopes"] == {
        "GOOGLE_API_KEY": "Process",
        "OPENAI_API_KEY": "Process",
    }
    assert len(report["backup_paths"]) == 1
    backup_path = Path(report["backup_paths"][0])
    assert backup_path.exists()
    assert "OPENAI_API_KEY" not in backup_path.read_text(encoding="utf-8")
    local_env_text = local_env.read_text(encoding="utf-8")
    assert f"OPENAI_API_KEY={staged_openai}" in local_env_text
    assert f"GOOGLE_API_KEY={staged_google}" in local_env_text
    serialized = json.dumps(report, ensure_ascii=False)
    assert staged_openai not in serialized
    assert staged_google not in serialized


def test_provider_only_main_write_json_out_omits_backup_when_env_is_created(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root_env = tmp_path / ".env"
    local_env = tmp_path / "automation" / "getdaytrends" / ".env"
    report_path = tmp_path / "provider-created-env.json"
    local_env.parent.mkdir(parents=True, exist_ok=True)
    root_env.write_text("SUPABASE_URL=https://projectref.supabase.co\n", encoding="utf-8")
    staged_openai = "".join(["sk", "-proj-", "created-env-test"])
    monkeypatch.setenv("GETDAYTRENDS_NEW_OPENAI_API_KEY", staged_openai)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "updated"
    assert report["backup_paths"] == []
    assert local_env.exists()
    assert f"OPENAI_API_KEY={staged_openai}" in local_env.read_text(encoding="utf-8")
    assert staged_openai not in json.dumps(report, ensure_ascii=False)


def test_provider_update_rejects_multiline_staged_key_without_echoing_value(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    staged_key = "first-line\nsecond-line"
    monkeypatch.setenv("GETDAYTRENDS_NEW_OPENAI_API_KEY", staged_key)

    args = Namespace(
        env_path=root_env,
        local_env_path=local_env,
        database_url_stdin=False,
        write=False,
        allow_host_change=False,
    )

    try:
        credentials.update_credentials(args)
    except ValueError as exc:
        message = str(exc)
        assert "OPENAI_API_KEY from GETDAYTRENDS_NEW_OPENAI_API_KEY must be a single line" in message
        assert "first-line" not in message
        assert "second-line" not in message
    else:
        raise AssertionError("multiline staged provider key should be rejected")


def test_blank_provider_write_does_not_mutate_env_or_create_backup(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    blank_openai = "\t\t"
    report_path = tmp_path / "blank-provider-write.json"
    monkeypatch.setenv("GETDAYTRENDS_NEW_OPENAI_API_KEY", blank_openai)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    expected_sources = {"OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY"}
    expected_scopes = {"OPENAI_API_KEY": "Process"}
    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["error"] == "OPENAI_API_KEY from GETDAYTRENDS_NEW_OPENAI_API_KEY must not be blank"
    assert stdout_report["attempted_update_sources"] == expected_sources
    assert stdout_report["attempted_update_source_scopes"] == expected_scopes
    assert blank_openai not in stdout_report["error"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["error"] == "OPENAI_API_KEY from GETDAYTRENDS_NEW_OPENAI_API_KEY must not be blank"
    assert report["attempted_update_sources"] == expected_sources
    assert report["attempted_update_source_scopes"] == expected_scopes
    assert blank_openai not in report["error"]


def test_blank_database_url_write_does_not_mutate_env_or_create_backup(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    blank_database_url = "   "
    report_path = tmp_path / "blank-database-url-write.json"
    monkeypatch.setenv("GETDAYTRENDS_NEW_DATABASE_URL", blank_database_url)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    expected_sources = {"DATABASE_URL": "GETDAYTRENDS_NEW_DATABASE_URL"}
    expected_scopes = {"DATABASE_URL": "Process"}
    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["error"] == "DATABASE_URL from GETDAYTRENDS_NEW_DATABASE_URL must not be blank"
    assert stdout_report["attempted_update_sources"] == expected_sources
    assert stdout_report["attempted_update_source_scopes"] == expected_scopes
    assert blank_database_url not in stdout_report["error"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["error"] == "DATABASE_URL from GETDAYTRENDS_NEW_DATABASE_URL must not be blank"
    assert report["attempted_update_sources"] == expected_sources
    assert report["attempted_update_source_scopes"] == expected_scopes
    assert blank_database_url not in report["error"]


def test_blank_stdin_database_url_write_does_not_mutate_env_or_create_backup(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    blank_database_url = "\n\t"
    report_path = tmp_path / "blank-stdin-database-url-write.json"
    monkeypatch.setattr(sys, "stdin", io.StringIO(blank_database_url))

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--database-url-stdin",
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    expected_sources = {"DATABASE_URL": "stdin"}
    expected_scopes = {"DATABASE_URL": "stdin"}
    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["error"] == "DATABASE_URL from stdin must not be blank"
    assert stdout_report["attempted_update_sources"] == expected_sources
    assert stdout_report["attempted_update_source_scopes"] == expected_scopes
    assert blank_database_url not in stdout_report["error"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["error"] == "DATABASE_URL from stdin must not be blank"
    assert report["attempted_update_sources"] == expected_sources
    assert report["attempted_update_source_scopes"] == expected_scopes
    assert blank_database_url not in report["error"]


def test_blank_windows_scoped_database_url_write_does_not_mutate_env_or_create_backup(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    report_path = tmp_path / "blank-windows-database-url-write.json"
    _clear_update_env(monkeypatch)
    monkeypatch.setattr(
        gate_common,
        "read_windows_env_scopes",
        lambda: {"User": {}, "Machine": {"GETDAYTRENDS_NEW_DATABASE_URL": ""}},
    )

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    expected_sources = {"DATABASE_URL": "GETDAYTRENDS_NEW_DATABASE_URL"}
    expected_scopes = {"DATABASE_URL": "Machine"}
    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["error"] == "DATABASE_URL from GETDAYTRENDS_NEW_DATABASE_URL must not be blank"
    assert stdout_report["attempted_update_sources"] == expected_sources
    assert stdout_report["attempted_update_source_scopes"] == expected_scopes
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["error"] == "DATABASE_URL from GETDAYTRENDS_NEW_DATABASE_URL must not be blank"
    assert report["attempted_update_sources"] == expected_sources
    assert report["attempted_update_source_scopes"] == expected_scopes


def test_windows_scoped_database_url_write_reports_machine_scope_without_echoing_value(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    report_path = tmp_path / "windows-database-url-write.json"
    staged_url = _pooler_url("windows-db-write")
    _clear_update_env(monkeypatch)
    monkeypatch.setattr(
        gate_common,
        "read_windows_env_scopes",
        lambda: {"User": {}, "Machine": {"GETDAYTRENDS_NEW_DATABASE_URL": staged_url}},
    )

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "updated"
    assert report["dry_run"] is False
    assert report["updated_keys"] == ["DATABASE_URL"]
    assert report["updated_key_sources"] == {"DATABASE_URL": "GETDAYTRENDS_NEW_DATABASE_URL"}
    assert report["updated_key_source_scopes"] == {"DATABASE_URL": "Machine"}
    assert f"DATABASE_URL={staged_url}" in local_env.read_text(encoding="utf-8")
    assert staged_url not in json.dumps(report, ensure_ascii=False)
    assert "windows-db-write" not in json.dumps(report, ensure_ascii=False)


def test_blank_windows_scoped_provider_write_does_not_mutate_env_or_create_backup(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    report_path = tmp_path / "blank-windows-provider-write.json"
    _clear_update_env(monkeypatch)
    monkeypatch.setattr(
        gate_common,
        "read_windows_env_scopes",
        lambda: {"User": {}, "Machine": {"GETDAYTRENDS_NEW_OPENAI_API_KEY": ""}},
    )

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    expected_sources = {"OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY"}
    expected_scopes = {"OPENAI_API_KEY": "Machine"}
    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["error"] == "OPENAI_API_KEY from GETDAYTRENDS_NEW_OPENAI_API_KEY must not be blank"
    assert stdout_report["attempted_update_sources"] == expected_sources
    assert stdout_report["attempted_update_source_scopes"] == expected_scopes
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["error"] == "OPENAI_API_KEY from GETDAYTRENDS_NEW_OPENAI_API_KEY must not be blank"
    assert report["attempted_update_sources"] == expected_sources
    assert report["attempted_update_source_scopes"] == expected_scopes


def test_windows_scoped_provider_write_reports_machine_scope_without_echoing_value(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    report_path = tmp_path / "windows-provider-write.json"
    staged_key = "".join(["sk", "-proj-", "windows-provider-write"])
    _clear_update_env(monkeypatch)
    monkeypatch.setattr(
        gate_common,
        "read_windows_env_scopes",
        lambda: {"User": {}, "Machine": {"GETDAYTRENDS_NEW_OPENAI_API_KEY": staged_key}},
    )

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "updated"
    assert report["dry_run"] is False
    assert report["updated_keys"] == ["OPENAI_API_KEY"]
    assert report["updated_key_sources"] == {"OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY"}
    assert report["updated_key_source_scopes"] == {"OPENAI_API_KEY": "Machine"}
    assert f"OPENAI_API_KEY={staged_key}" in local_env.read_text(encoding="utf-8")
    serialized = json.dumps(report, ensure_ascii=False)
    assert staged_key not in serialized
    assert "windows-provider-write" not in serialized


def test_database_url_stdin_update_reports_source_without_echoing_value(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    staged_url = _pooler_url("stdin-source")
    monkeypatch.setattr(sys, "stdin", io.StringIO(staged_url))

    report = credentials.update_credentials(
        Namespace(
            env_path=root_env,
            local_env_path=local_env,
            database_url_stdin=True,
            write=False,
            allow_host_change=False,
        )
    )

    assert report["status"] == "planned"
    assert report["updated_keys"] == ["DATABASE_URL"]
    assert report["updated_key_sources"] == {"DATABASE_URL": "stdin"}
    assert report["updated_key_source_scopes"] == {"DATABASE_URL": "stdin"}
    assert report["new_database_url_shape"]["project_refs_match"] is True
    assert staged_url not in json.dumps(report, ensure_ascii=False)


def test_database_url_stdin_main_stdout_redacts_successful_plan(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    staged_url = _pooler_url("stdout-success")
    monkeypatch.setattr(sys, "stdin", io.StringIO(staged_url))

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--database-url-stdin",
        ]
    )

    assert exit_code == 0
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "planned"
    assert stdout_report["updated_key_sources"] == {"DATABASE_URL": "stdin"}
    assert stdout_report["updated_key_source_scopes"] == {"DATABASE_URL": "stdin"}
    assert stdout_report["new_database_url_shape"]["project_refs_match"] is True
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert "stdout-success" not in stdout_serialized
    assert staged_url not in stdout_serialized


def test_database_url_stdin_main_json_out_redacts_successful_plan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    report_path = tmp_path / "stdin-plan.json"
    staged_url = _pooler_url("json-success")
    monkeypatch.setattr(sys, "stdin", io.StringIO(staged_url))

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--database-url-stdin",
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "planned"
    assert report["updated_keys"] == ["DATABASE_URL"]
    assert report["updated_key_sources"] == {"DATABASE_URL": "stdin"}
    assert report["updated_key_source_scopes"] == {"DATABASE_URL": "stdin"}
    assert report["new_database_url_shape"]["project_refs_match"] is True
    serialized = json.dumps(report, ensure_ascii=False)
    assert "json-success" not in serialized
    assert staged_url not in serialized


def test_database_url_stdin_main_write_json_out_redacts_report_and_writes_backup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    report_path = tmp_path / "stdin-write.json"
    staged_url = _pooler_url("write-success")
    monkeypatch.setattr(sys, "stdin", io.StringIO(staged_url))

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--database-url-stdin",
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "updated"
    assert report["dry_run"] is False
    assert report["updated_keys"] == ["DATABASE_URL"]
    assert report["updated_key_sources"] == {"DATABASE_URL": "stdin"}
    assert report["updated_key_source_scopes"] == {"DATABASE_URL": "stdin"}
    assert report["new_database_url_shape"]["project_refs_match"] is True
    assert len(report["backup_paths"]) == 1
    backup_path = Path(report["backup_paths"][0])
    assert backup_path.exists()
    assert "DATABASE_URL" not in backup_path.read_text(encoding="utf-8")
    local_env_text = local_env.read_text(encoding="utf-8")
    assert f"DATABASE_URL={staged_url}" in local_env_text
    serialized = json.dumps(report, ensure_ascii=False)
    assert "write-success" not in serialized
    assert staged_url not in serialized


def test_invalid_database_url_stdin_report_keeps_source_without_echoing_value(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    invalid_url = _pooler_url("first-line") + "\n" + _pooler_url("second-line")
    report_path = tmp_path / "invalid.json"
    monkeypatch.setattr(sys, "stdin", io.StringIO(invalid_url))

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--database-url-stdin",
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 1
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["attempted_update_sources"] == {"DATABASE_URL": "stdin"}
    assert stdout_report["attempted_update_source_scopes"] == {"DATABASE_URL": "stdin"}
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert "first-line" not in stdout_serialized
    assert "second-line" not in stdout_serialized
    assert invalid_url not in stdout_serialized
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["attempted_update_sources"] == {"DATABASE_URL": "stdin"}
    assert report["attempted_update_source_scopes"] == {"DATABASE_URL": "stdin"}
    serialized = json.dumps(report, ensure_ascii=False)
    assert "first-line" not in serialized
    assert "second-line" not in serialized
    assert invalid_url not in serialized


def test_invalid_database_url_stdin_write_does_not_mutate_env_or_create_backup(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    invalid_url = _pooler_url("first-line") + "\n" + _pooler_url("second-line")
    report_path = tmp_path / "invalid-stdin-write.json"
    monkeypatch.setattr(sys, "stdin", io.StringIO(invalid_url))

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--database-url-stdin",
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["attempted_update_sources"] == {"DATABASE_URL": "stdin"}
    assert stdout_report["attempted_update_source_scopes"] == {"DATABASE_URL": "stdin"}
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert "first-line" not in stdout_serialized
    assert "second-line" not in stdout_serialized
    assert invalid_url not in stdout_serialized
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["attempted_update_sources"] == {"DATABASE_URL": "stdin"}
    assert report["attempted_update_source_scopes"] == {"DATABASE_URL": "stdin"}
    serialized = json.dumps(report, ensure_ascii=False)
    assert "first-line" not in serialized
    assert "second-line" not in serialized
    assert invalid_url not in serialized


def test_invalid_staged_database_url_write_does_not_mutate_env_or_create_backup(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    invalid_url = _pooler_url("first-line") + "\n" + _pooler_url("second-line")
    report_path = tmp_path / "invalid-staged-database-write.json"
    monkeypatch.setenv("GETDAYTRENDS_NEW_DATABASE_URL", invalid_url)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["attempted_update_sources"] == {"DATABASE_URL": "GETDAYTRENDS_NEW_DATABASE_URL"}
    assert stdout_report["attempted_update_source_scopes"] == {"DATABASE_URL": "Process"}
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert "first-line" not in stdout_serialized
    assert "second-line" not in stdout_serialized
    assert invalid_url not in stdout_serialized
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["attempted_update_sources"] == {"DATABASE_URL": "GETDAYTRENDS_NEW_DATABASE_URL"}
    assert report["attempted_update_source_scopes"] == {"DATABASE_URL": "Process"}
    serialized = json.dumps(report, ensure_ascii=False)
    assert "first-line" not in serialized
    assert "second-line" not in serialized
    assert invalid_url not in serialized


def test_invalid_staged_database_url_with_valid_provider_write_does_not_partially_mutate_env(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    invalid_url = _pooler_url("first-line") + "\n" + _pooler_url("second-line")
    staged_openai = "".join(["sk", "-proj-", "partial-write-test"])
    report_path = tmp_path / "invalid-staged-database-with-provider-write.json"
    monkeypatch.setenv("GETDAYTRENDS_NEW_DATABASE_URL", invalid_url)
    monkeypatch.setenv("GETDAYTRENDS_NEW_OPENAI_API_KEY", staged_openai)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    expected_sources = {
        "DATABASE_URL": "GETDAYTRENDS_NEW_DATABASE_URL",
        "OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY",
    }
    expected_scopes = {
        "DATABASE_URL": "Process",
        "OPENAI_API_KEY": "Process",
    }
    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["attempted_update_sources"] == expected_sources
    assert stdout_report["attempted_update_source_scopes"] == expected_scopes
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert "first-line" not in stdout_serialized
    assert "second-line" not in stdout_serialized
    assert invalid_url not in stdout_serialized
    assert staged_openai not in stdout_serialized
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["attempted_update_sources"] == expected_sources
    assert report["attempted_update_source_scopes"] == expected_scopes
    serialized = json.dumps(report, ensure_ascii=False)
    assert "first-line" not in serialized
    assert "second-line" not in serialized
    assert invalid_url not in serialized
    assert staged_openai not in serialized


def test_valid_staged_database_url_with_invalid_provider_write_does_not_partially_mutate_env(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    staged_database_url = _pooler_url("valid-db-invalid-provider")
    invalid_openai = "first-line\nsecond-line"
    report_path = tmp_path / "valid-staged-database-with-invalid-provider-write.json"
    monkeypatch.setenv("GETDAYTRENDS_NEW_DATABASE_URL", staged_database_url)
    monkeypatch.setenv("GETDAYTRENDS_NEW_OPENAI_API_KEY", invalid_openai)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    expected_sources = {
        "DATABASE_URL": "GETDAYTRENDS_NEW_DATABASE_URL",
        "OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY",
    }
    expected_scopes = {
        "DATABASE_URL": "Process",
        "OPENAI_API_KEY": "Process",
    }
    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["attempted_update_sources"] == expected_sources
    assert stdout_report["attempted_update_source_scopes"] == expected_scopes
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert "valid-db-invalid-provider" not in stdout_serialized
    assert "first-line" not in stdout_serialized
    assert "second-line" not in stdout_serialized
    assert staged_database_url not in stdout_serialized
    assert invalid_openai not in stdout_serialized
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["attempted_update_sources"] == expected_sources
    assert report["attempted_update_source_scopes"] == expected_scopes
    serialized = json.dumps(report, ensure_ascii=False)
    assert "valid-db-invalid-provider" not in serialized
    assert "first-line" not in serialized
    assert "second-line" not in serialized
    assert staged_database_url not in serialized
    assert invalid_openai not in serialized


def test_valid_stdin_database_url_with_invalid_provider_write_does_not_partially_mutate_env(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    staged_database_url = _pooler_url("stdin-valid-db-invalid-provider")
    invalid_google = "first-line\nsecond-line"
    report_path = tmp_path / "valid-stdin-database-with-invalid-provider-write.json"
    monkeypatch.setattr(sys, "stdin", io.StringIO(staged_database_url))
    monkeypatch.setenv("GETDAYTRENDS_NEW_GOOGLE_API_KEY", invalid_google)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--database-url-stdin",
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    expected_sources = {
        "DATABASE_URL": "stdin",
        "GOOGLE_API_KEY": "GETDAYTRENDS_NEW_GOOGLE_API_KEY",
    }
    expected_scopes = {
        "DATABASE_URL": "stdin",
        "GOOGLE_API_KEY": "Process",
    }
    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["attempted_update_sources"] == expected_sources
    assert stdout_report["attempted_update_source_scopes"] == expected_scopes
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert "stdin-valid-db-invalid-provider" not in stdout_serialized
    assert "first-line" not in stdout_serialized
    assert "second-line" not in stdout_serialized
    assert staged_database_url not in stdout_serialized
    assert invalid_google not in stdout_serialized
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["attempted_update_sources"] == expected_sources
    assert report["attempted_update_source_scopes"] == expected_scopes
    serialized = json.dumps(report, ensure_ascii=False)
    assert "stdin-valid-db-invalid-provider" not in serialized
    assert "first-line" not in serialized
    assert "second-line" not in serialized
    assert staged_database_url not in serialized
    assert invalid_google not in serialized


def test_valid_stdin_database_url_with_invalid_supabase_write_does_not_partially_mutate_env(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    staged_database_url = _pooler_url("stdin-valid-db-invalid-supabase")
    invalid_supabase_url = "https://example.com/not-supabase"
    report_path = tmp_path / "valid-stdin-database-with-invalid-supabase-write.json"
    monkeypatch.setattr(sys, "stdin", io.StringIO(staged_database_url))
    monkeypatch.setenv("GETDAYTRENDS_NEW_SUPABASE_URL", invalid_supabase_url)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--database-url-stdin",
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    expected_sources = {
        "DATABASE_URL": "stdin",
        "SUPABASE_URL": "GETDAYTRENDS_NEW_SUPABASE_URL",
    }
    expected_scopes = {
        "DATABASE_URL": "stdin",
        "SUPABASE_URL": "Process",
    }
    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["attempted_update_sources"] == expected_sources
    assert stdout_report["attempted_update_source_scopes"] == expected_scopes
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert "stdin-valid-db-invalid-supabase" not in stdout_serialized
    assert invalid_supabase_url not in stdout_serialized
    assert staged_database_url not in stdout_serialized
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["attempted_update_sources"] == expected_sources
    assert report["attempted_update_source_scopes"] == expected_scopes
    serialized = json.dumps(report, ensure_ascii=False)
    assert "stdin-valid-db-invalid-supabase" not in serialized
    assert invalid_supabase_url not in serialized
    assert staged_database_url not in serialized


def test_valid_supabase_url_with_invalid_provider_write_does_not_partially_mutate_env(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    staged_supabase_url = "https://newproject.supabase.co"
    invalid_openai = "first-line\nsecond-line"
    report_path = tmp_path / "valid-supabase-with-invalid-provider-write.json"
    monkeypatch.setenv("GETDAYTRENDS_NEW_SUPABASE_URL", staged_supabase_url)
    monkeypatch.setenv("GETDAYTRENDS_NEW_OPENAI_API_KEY", invalid_openai)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    expected_sources = {
        "OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY",
        "SUPABASE_URL": "GETDAYTRENDS_NEW_SUPABASE_URL",
    }
    expected_scopes = {
        "OPENAI_API_KEY": "Process",
        "SUPABASE_URL": "Process",
    }
    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["attempted_update_sources"] == expected_sources
    assert stdout_report["attempted_update_source_scopes"] == expected_scopes
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert "newproject" not in stdout_serialized
    assert "first-line" not in stdout_serialized
    assert "second-line" not in stdout_serialized
    assert staged_supabase_url not in stdout_serialized
    assert invalid_openai not in stdout_serialized
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["attempted_update_sources"] == expected_sources
    assert report["attempted_update_source_scopes"] == expected_scopes
    serialized = json.dumps(report, ensure_ascii=False)
    assert "newproject" not in serialized
    assert "first-line" not in serialized
    assert "second-line" not in serialized
    assert staged_supabase_url not in serialized
    assert invalid_openai not in serialized


def test_valid_openai_with_invalid_google_write_does_not_partially_mutate_env(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    staged_openai = "".join(["sk", "-proj-", "valid-openai-invalid-google"])
    invalid_google = "first-line\nsecond-line"
    report_path = tmp_path / "valid-openai-with-invalid-google-write.json"
    monkeypatch.setenv("GETDAYTRENDS_NEW_OPENAI_API_KEY", staged_openai)
    monkeypatch.setenv("GETDAYTRENDS_NEW_GOOGLE_API_KEY", invalid_google)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    expected_sources = {
        "GOOGLE_API_KEY": "GETDAYTRENDS_NEW_GOOGLE_API_KEY",
        "OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY",
    }
    expected_scopes = {
        "GOOGLE_API_KEY": "Process",
        "OPENAI_API_KEY": "Process",
    }
    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["attempted_update_sources"] == expected_sources
    assert stdout_report["attempted_update_source_scopes"] == expected_scopes
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert "valid-openai-invalid-google" not in stdout_serialized
    assert "first-line" not in stdout_serialized
    assert "second-line" not in stdout_serialized
    assert staged_openai not in stdout_serialized
    assert invalid_google not in stdout_serialized
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["attempted_update_sources"] == expected_sources
    assert report["attempted_update_source_scopes"] == expected_scopes
    serialized = json.dumps(report, ensure_ascii=False)
    assert "valid-openai-invalid-google" not in serialized
    assert "first-line" not in serialized
    assert "second-line" not in serialized
    assert staged_openai not in serialized
    assert invalid_google not in serialized


def test_invalid_provider_update_report_keeps_source_without_echoing_value(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    report_path = tmp_path / "invalid-provider.json"
    monkeypatch.setenv("GETDAYTRENDS_NEW_OPENAI_API_KEY", "first-line\nsecond-line")

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 1
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["attempted_update_sources"] == {"OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY"}
    assert stdout_report["attempted_update_source_scopes"] == {"OPENAI_API_KEY": "Process"}
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert "first-line" not in stdout_serialized
    assert "second-line" not in stdout_serialized
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["attempted_update_sources"] == {"OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY"}
    assert report["attempted_update_source_scopes"] == {"OPENAI_API_KEY": "Process"}
    serialized = json.dumps(report, ensure_ascii=False)
    assert "first-line" not in serialized
    assert "second-line" not in serialized


def test_invalid_provider_write_does_not_mutate_env_or_create_backup(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    report_path = tmp_path / "invalid-provider-write.json"
    monkeypatch.setenv("GETDAYTRENDS_NEW_OPENAI_API_KEY", "first-line\nsecond-line")

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["attempted_update_sources"] == {"OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY"}
    assert stdout_report["attempted_update_source_scopes"] == {"OPENAI_API_KEY": "Process"}
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert "first-line" not in stdout_serialized
    assert "second-line" not in stdout_serialized
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["attempted_update_sources"] == {"OPENAI_API_KEY": "GETDAYTRENDS_NEW_OPENAI_API_KEY"}
    assert report["attempted_update_source_scopes"] == {"OPENAI_API_KEY": "Process"}
    serialized = json.dumps(report, ensure_ascii=False)
    assert "first-line" not in serialized
    assert "second-line" not in serialized


def test_update_rejects_invalid_staged_supabase_url(tmp_path: Path, monkeypatch) -> None:
    root_env, local_env = _write_envs(tmp_path)
    monkeypatch.setenv("GETDAYTRENDS_NEW_SUPABASE_URL", "https://example.com/not-supabase")

    args = Namespace(
        env_path=root_env,
        local_env_path=local_env,
        database_url_stdin=False,
        write=False,
        allow_host_change=False,
    )

    try:
        credentials.update_credentials(args)
    except ValueError as exc:
        assert "SUPABASE_URL must be shaped like" in str(exc)
    else:
        raise AssertionError("invalid staged SUPABASE_URL should be rejected")


def test_invalid_staged_supabase_url_write_does_not_mutate_env_or_create_backup(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root_env, local_env = _write_envs(tmp_path)
    original_local_env = local_env.read_text(encoding="utf-8")
    invalid_url = "https://example.com/not-supabase"
    report_path = tmp_path / "invalid-supabase-write.json"
    monkeypatch.setenv("GETDAYTRENDS_NEW_SUPABASE_URL", invalid_url)

    exit_code = credentials.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(report_path),
        ]
    )

    assert exit_code == 1
    assert local_env.read_text(encoding="utf-8") == original_local_env
    assert not list(local_env.parent.glob(f"{local_env.name}.bak-*"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert stdout_report["status"] == "invalid"
    assert stdout_report["dry_run"] is False
    assert stdout_report["attempted_update_sources"] == {"SUPABASE_URL": "GETDAYTRENDS_NEW_SUPABASE_URL"}
    assert stdout_report["attempted_update_source_scopes"] == {"SUPABASE_URL": "Process"}
    stdout_serialized = json.dumps(stdout_report, ensure_ascii=False)
    assert invalid_url not in stdout_serialized
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid"
    assert report["dry_run"] is False
    assert report["attempted_update_sources"] == {"SUPABASE_URL": "GETDAYTRENDS_NEW_SUPABASE_URL"}
    assert report["attempted_update_source_scopes"] == {"SUPABASE_URL": "Process"}
    serialized = json.dumps(report, ensure_ascii=False)
    assert invalid_url not in serialized


def test_input_signal_fingerprint_changes_with_staged_credential(tmp_path: Path) -> None:
    root_env, local_env = _write_envs(tmp_path)

    first = credentials.build_input_status(
        workspace_root=tmp_path,
        env_path=root_env,
        local_env_path=local_env,
        environ={
            "GETDAYTRENDS_NEW_DATABASE_URL": _pooler_url("first")
        },
    )
    second = credentials.build_input_status(
        workspace_root=tmp_path,
        env_path=root_env,
        local_env_path=local_env,
        environ={
            "GETDAYTRENDS_NEW_DATABASE_URL": _pooler_url("second")
        },
    )

    assert first["input_signal_fingerprint"] != second["input_signal_fingerprint"]


def test_input_status_markdown_includes_change_marker(tmp_path: Path) -> None:
    root_env, local_env = _write_envs(tmp_path)
    payload = credentials.build_input_status(
        workspace_root=tmp_path,
        env_path=root_env,
        local_env_path=local_env,
        environ={},
    )
    report = tmp_path / "status.md"

    credentials._write_markdown(report, payload)

    text = report.read_text(encoding="utf-8")
    assert "Input signal fingerprint" in text
    assert "Process update env present" in text
    assert "Windows update env present" in text
    assert "Safe to skip strict readiness until credential inputs change" in text
    assert "Credential update env vars: `none`" in text
    assert "Windows update env vars: `none`" in text
    assert "Readiness evidence: `missing`" in text
    assert "Workspace smoke evidence: `missing`" in text
    assert "Launch blocker summary" in text
    assert "Operator next action" in text
    assert "Next command after provider fix" in text
    assert "Next verification after local update" in text
    assert payload["input_signal_fingerprint"] in text


def test_input_status_markdown_lists_redacted_update_sources_without_values(tmp_path: Path) -> None:
    root_env, local_env = _write_envs(tmp_path)
    process_key = "process-provider-markdown-key"
    windows_key = "windows-provider-markdown-key"
    payload = credentials.build_input_status(
        workspace_root=tmp_path,
        env_path=root_env,
        local_env_path=local_env,
        environ={"GETDAYTRENDS_NEW_OPENAI_API_KEY": process_key},
        scoped_env={"User": {}, "Machine": {"GETDAYTRENDS_NEW_GOOGLE_API_KEY": windows_key}},
    )
    report = tmp_path / "status.md"

    credentials._write_markdown(report, payload)

    text = report.read_text(encoding="utf-8")
    assert (
        "Credential update env vars: `GETDAYTRENDS_NEW_GOOGLE_API_KEY, GETDAYTRENDS_NEW_OPENAI_API_KEY`"
        in text
    )
    assert "Windows update env vars: `Machine:GETDAYTRENDS_NEW_GOOGLE_API_KEY`" in text
    assert "Safe to skip strict readiness until credential inputs change: `False`" in text
    assert process_key not in text
    assert windows_key not in text


def test_input_status_markdown_includes_evidence_summary_counts(tmp_path: Path) -> None:
    root_env, local_env = _write_envs(tmp_path)
    payload = credentials.build_input_status(
        workspace_root=tmp_path,
        env_path=root_env,
        local_env_path=local_env,
        environ={},
    )
    payload["evidence_summary"] = {
        "readiness": {
            "exists": True,
            "status": "fail",
            "generated_at": "2026-06-10T20:28:49+09:00",
            "summary": {"total": 9, "passed": 7, "failed": 2, "warnings": 0},
                "scheduler_artifact": {
                    "ok": True,
                    "status": "success",
                    "selected_artifact_is_latest": False,
                    "artifact_path_present": False,
                    "artifact_path_matches_latest": False,
                    "summary_fallback_used": False,
                    "summary_fallback_used_present": False,
                    "summary_fallback_used_valid": True,
                    "latest_artifact_path_present": True,
                    "latest_artifact_path_matches_latest": True,
                "latest_summary_fallback_used": False,
                "latest_summary_fallback_used_present": True,
                "latest_summary_fallback_used_valid": True,
            },
        },
        "workspace_smoke": {
            "exists": True,
            "status": "complete",
            "generated_at": "2026-06-10T08:47:47+00:00",
            "summary": {
                "total": 7,
                "passed": 6,
                "failed": 1,
                "expected_external_failures": ["getdaytrends launch readiness gate"],
                "unexpected_failures": [],
            },
        },
    }
    payload["launch_blocker_summary"] = credentials._launch_blocker_summary(False, payload["evidence_summary"])
    payload["operator_next_action"] = payload["launch_blocker_summary"]["operator_next_action"]
    report = tmp_path / "status.md"

    credentials._write_markdown(report, payload)

    text = report.read_text(encoding="utf-8")
    assert "Readiness evidence: `status=fail" in text
    assert "total=9" in text
    assert "passed=7" in text
    assert "failed=2" in text
    assert "warnings=0" in text
    assert "scheduler_artifact_ok=True" in text
    assert "scheduler_artifact_status=success" in text
    assert "scheduler_artifact_selected_artifact_is_latest=False" in text
    assert "scheduler_artifact_artifact_path_present=False" in text
    assert "scheduler_artifact_artifact_path_matches_latest=False" in text
    assert "scheduler_artifact_summary_fallback_used=False" in text
    assert "scheduler_artifact_summary_fallback_used_present=False" in text
    assert "scheduler_artifact_summary_fallback_used_valid=True" in text
    assert "scheduler_artifact_latest_artifact_path_present=True" in text
    assert "scheduler_artifact_latest_artifact_path_matches_latest=True" in text
    assert "scheduler_artifact_latest_summary_fallback_used=False" in text
    assert "scheduler_artifact_latest_summary_fallback_used_present=True" in text
    assert "scheduler_artifact_latest_summary_fallback_used_valid=True" in text
    assert "Workspace smoke evidence: `status=complete" in text
    assert "expected_external_failures=1" in text
    assert "unexpected_failures=0" in text
    assert "Launch blocker summary: `status=external_readiness_blocked" in text
    assert "blocking_evidence_count=1" in text
    assert "blocking_evidence_kinds=readiness_failed" in text
    assert "operator_attention_count=3" in text
    assert "readiness_scheduler_artifact_stale=True" in text
    assert "latest_scheduler_artifact_evidence_complete=True" in text
    assert (
        "operator_attention_kinds=scheduler_artifact_evidence_stale|"
        "readiness_selected_scheduler_schema_older_than_latest|"
        "readiness_selected_scheduler_fallback_field_missing"
    ) in text
    assert "Operator next action: `stage_corrected_provider_console_database_url_then_run_local_update`" in text
    assert "getdaytrends launch readiness gate" not in text
