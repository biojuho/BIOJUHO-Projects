import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = PROJECT_ROOT / "ops" / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "getdaytrends_update_credentials.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("getdaytrends_update_credentials", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _new_url(project_ref="abc123projectref", password="new-password"):
    return "".join(
        [
            "postgresql://",
            "postgres",
            ".",
            project_ref,
            ":",
            password,
            "@",
            "aws-1-ap-northeast-2.pooler.supabase.com",
            ":6543/postgres",
        ]
    )


def _env_text(project_ref="abc123projectref"):
    return "\n".join(
        [
            f"SUPABASE_URL=https://{project_ref}.supabase.co",
            f"DATABASE_URL={_new_url(project_ref=project_ref, password='old-password')}",
            "DAILYNEWS_DISABLED_LLM_PROVIDERS=google,openai,grok",
            "",
        ]
    )


def _env_text_without_supabase(project_ref="abc123projectref"):
    return "\n".join(
        [
            f"DATABASE_URL={_new_url(project_ref=project_ref, password='old-password')}",
            "DAILYNEWS_DISABLED_LLM_PROVIDERS=google,openai,grok",
            "",
        ]
    )


def test_post_update_command_uses_current_date_stamp():
    mod = load_module()

    assert f"current-full-matrix-{mod.CURRENT_DATE_STAMP}.json" in mod.POST_UPDATE_COMMAND
    assert "--continue-on-failure" in mod.POST_UPDATE_COMMAND
    assert "--allow-blocked-external" in mod.POST_UPDATE_COMMAND
    assert (
        f"docs/reports/{mod.CURRENT_DATE_STAMP[:7]}/"
        f"WORKSPACE_EXTERNAL_CREDENTIAL_RECOVERY_REFRESH_CURRENT_FULL_MATRIX_{mod.CURRENT_DATE_STAMP}.md"
        in mod.POST_UPDATE_COMMAND
    )


def test_help_documents_input_status_current_alias(capsys):
    mod = load_module()

    with pytest.raises(SystemExit) as exc_info:
        mod.parse_args(["--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    normalized = " ".join(output.split())
    assert "--current-json-out" in output
    assert "current-alias JSON report" in output
    assert "writes both dated and current JSON aliases" in normalized


def test_latest_scheduler_artifact_prefers_payload_timestamp_over_mtime(tmp_path):
    mod = load_module()
    scheduler_dir = tmp_path / "scheduler"
    older = scheduler_dir / "run_2026-06-05_020000.json"
    newer = scheduler_dir / "run_2026-06-05_030000.json"
    older.parent.mkdir(parents=True)
    older.write_text(json.dumps({"started_at": "2026-06-05T02:00:00+00:00"}), encoding="utf-8")
    newer.write_text(json.dumps({"started_at": "2026-06-05T03:00:00+00:00"}), encoding="utf-8")
    os.utime(newer, (1_700_000_000, 1_700_000_000))
    os.utime(older, (1_700_000_100, 1_700_000_100))

    assert mod._latest_scheduler_artifact(scheduler_dir) == newer


def test_launch_blocker_summary_exposes_scheduler_stale_and_latest_complete_flags():
    mod = load_module()
    summary = mod._launch_blocker_summary(
        False,
        {
            "readiness": {
                "exists": True,
                "status": "fail",
                "summary": {"failed": 2},
                "scheduler_artifact": {
                    "selected_artifact_is_latest": False,
                    "latest_artifact_path_present": True,
                    "latest_artifact_path_matches_latest": True,
                    "latest_summary_fallback_used_present": True,
                    "latest_summary_fallback_used_valid": True,
                },
            },
            "workspace_smoke": {"exists": True, "status": "complete", "summary": {"unexpected_failures": []}},
        },
    )

    assert summary["status"] == "external_readiness_blocked"
    assert summary["readiness_scheduler_artifact_stale"] is True
    assert summary["latest_scheduler_artifact_evidence_complete"] is True


def test_input_status_reports_no_rerun_without_leaking_values(tmp_path):
    mod = load_module()
    root = tmp_path
    local_env = root / "automation" / "getdaytrends" / ".env"
    local_env.parent.mkdir(parents=True)
    local_env.write_text(_env_text(), encoding="utf-8")
    env_path = root / ".env"
    env_path.write_text(_env_text(), encoding="utf-8")
    report = mod.build_input_status(workspace_root=root, env_path=env_path, local_env_path=local_env, environ={})
    serialized = json.dumps(report)
    assert report["status"] == "unchanged"
    assert report["rerun_recommended"] is False
    assert "old-password" not in serialized


def test_input_status_default_writes_dated_and_current_json(tmp_path, monkeypatch):
    mod = load_module()
    root = tmp_path
    local_env = root / "automation" / "getdaytrends" / ".env"
    local_env.parent.mkdir(parents=True)
    local_env.write_text(_env_text(), encoding="utf-8")
    env_path = root / ".env"
    env_path.write_text(_env_text(), encoding="utf-8")
    dated_json = tmp_path / "var" / "dated-status.json"
    current_json = tmp_path / "var" / "current-status.json"
    markdown_out = tmp_path / "status.md"
    monkeypatch.setattr(mod, "DEFAULT_JSON_OUT", dated_json)
    monkeypatch.setattr(mod, "DEFAULT_CURRENT_JSON_OUT", current_json)

    rc = mod.main(
        [
            "--workspace-root",
            str(root),
            "--env-path",
            str(env_path),
            "--local-env-path",
            str(local_env),
            "--input-status",
            "--markdown-out",
            str(markdown_out),
        ]
    )

    assert rc == 0
    dated_report = json.loads(dated_json.read_text(encoding="utf-8"))
    current_report = json.loads(current_json.read_text(encoding="utf-8"))
    assert dated_report["input_signal_fingerprint"] == current_report["input_signal_fingerprint"]
    assert dated_report["status"] == current_report["status"] == "unchanged"


def test_input_status_explicit_json_out_does_not_write_default_current_json(tmp_path, monkeypatch):
    mod = load_module()
    root = tmp_path
    local_env = root / "automation" / "getdaytrends" / ".env"
    local_env.parent.mkdir(parents=True)
    local_env.write_text(_env_text(), encoding="utf-8")
    env_path = root / ".env"
    env_path.write_text(_env_text(), encoding="utf-8")
    explicit_json = tmp_path / "explicit-status.json"
    current_json = tmp_path / "var" / "current-status.json"
    markdown_out = tmp_path / "status.md"
    monkeypatch.setattr(mod, "DEFAULT_CURRENT_JSON_OUT", current_json)

    rc = mod.main(
        [
            "--workspace-root",
            str(root),
            "--env-path",
            str(env_path),
            "--local-env-path",
            str(local_env),
            "--input-status",
            "--json-out",
            str(explicit_json),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    assert rc == 0
    assert explicit_json.exists()
    assert not current_json.exists()


def test_write_updates_local_database_url_with_redacted_report(tmp_path, monkeypatch, capsys):
    mod = load_module()
    root_env = tmp_path / ".env"
    local_env = tmp_path / "automation" / "getdaytrends" / ".env"
    local_env.parent.mkdir(parents=True)
    root_env.write_text(_env_text(), encoding="utf-8")
    local_env.write_text(_env_text(), encoding="utf-8")
    new_url = _new_url(password="rotated-secret")
    monkeypatch.setenv("GETDAYTRENDS_NEW_DATABASE_URL", new_url)
    rc = mod.main(["--env-path", str(root_env), "--local-env-path", str(local_env), "--write", "--json-out", str(tmp_path / "report.json")])
    output = capsys.readouterr().out
    assert rc == 0
    assert new_url in local_env.read_text(encoding="utf-8")
    assert "rotated-secret" not in output
    assert new_url not in output


def test_write_uses_root_supabase_url_when_local_env_omits_it(tmp_path, monkeypatch, capsys):
    mod = load_module()
    root_env = tmp_path / ".env"
    local_env = tmp_path / "automation" / "getdaytrends" / ".env"
    local_env.parent.mkdir(parents=True)
    root_env.write_text(_env_text(), encoding="utf-8")
    local_env.write_text(_env_text_without_supabase(), encoding="utf-8")
    new_url = _new_url(password="root-fallback-secret")
    monkeypatch.setenv("GETDAYTRENDS_NEW_DATABASE_URL", new_url)
    report_path = tmp_path / "root-fallback-report.json"

    rc = mod.main(["--env-path", str(root_env), "--local-env-path", str(local_env), "--write", "--json-out", str(report_path)])

    output = capsys.readouterr().out
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert rc == 0
    assert report["supabase_url_source"] == "root_env"
    assert report["new_database_url_shape"]["project_refs_match"] is True
    assert new_url in local_env.read_text(encoding="utf-8")
    assert "root-fallback-secret" not in output
    assert new_url not in output


def test_write_reads_scoped_env_fallback_without_leaking(tmp_path, monkeypatch, capsys):
    mod = load_module()
    root_env = tmp_path / ".env"
    local_env = tmp_path / "automation" / "getdaytrends" / ".env"
    local_env.parent.mkdir(parents=True)
    root_env.write_text(_env_text(), encoding="utf-8")
    local_env.write_text(_env_text(), encoding="utf-8")
    new_url = _new_url(password="scoped-get-secret")
    monkeypatch.setattr(mod, "scoped_env_value", lambda name, **kwargs: new_url if name == "GETDAYTRENDS_NEW_DATABASE_URL" else "")
    rc = mod.main(["--env-path", str(root_env), "--local-env-path", str(local_env), "--write", "--json-out", str(tmp_path / "scoped-report.json")])
    output = capsys.readouterr().out
    assert rc == 0
    assert new_url in local_env.read_text(encoding="utf-8")
    assert "scoped-get-secret" not in output
    assert new_url not in output


def test_rejects_bad_pooler_port_without_writing_or_leaking(tmp_path, monkeypatch, capsys):
    mod = load_module()
    local_env = tmp_path / "automation" / "getdaytrends" / ".env"
    local_env.parent.mkdir(parents=True)
    original = _env_text()
    local_env.write_text(original, encoding="utf-8")
    root_env = tmp_path / ".env"
    root_env.write_text(original, encoding="utf-8")
    bad_url = "".join(
        [
            "postgresql://",
            "postgres",
            ".",
            "abc123projectref",
            ":",
            "bad-secret",
            "@",
            "aws-1-ap-northeast-2.pooler.supabase.com",
            ":5432/postgres",
        ]
    )
    monkeypatch.setenv("GETDAYTRENDS_NEW_DATABASE_URL", bad_url)
    rc = mod.main(
        [
            "--env-path",
            str(root_env),
            "--local-env-path",
            str(local_env),
            "--write",
            "--json-out",
            str(tmp_path / "bad-report.json"),
        ]
    )
    output = capsys.readouterr().out
    assert rc == 1
    assert "Transaction pooler port 6543" in output
    assert local_env.read_text(encoding="utf-8") == original
    assert "bad-secret" not in output


def test_accepts_dedicated_transaction_pooler_with_host_change_confirmation(tmp_path):
    mod = load_module()
    local_env = tmp_path / "automation" / "getdaytrends" / ".env"
    local_env.parent.mkdir(parents=True)
    root_env = tmp_path / ".env"
    original = _env_text()
    local_env.write_text(original, encoding="utf-8")
    root_env.write_text(original, encoding="utf-8")
    dedicated_url = "".join(
        [
            "postgresql://",
            "postgres",
            ":",
            "dedicated-secret",
            "@",
            "db.abc123projectref.supabase.co",
            ":6543/postgres",
        ]
    )

    _, assignments = mod._read_lines(local_env)
    shape, warnings = mod._validate_database_url(dedicated_url, assignments, allow_host_change=True)

    assert shape["pooler_kind"] == "dedicated_transaction_pooler"
    assert shape["username_kind"] == "postgres"
    assert shape["project_refs_match"] is True
    assert warnings == ["database host changed from the previous DATABASE_URL"]
