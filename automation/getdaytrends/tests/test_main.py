import asyncio
import os
import subprocess
import sys
import threading
import time
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import main as main_mod
import pytest
from config import AppConfig
from main import (
    _acquire_lock,
    _apply_cli_overrides,
    _normalize_countries,
    _refresh_tap_products_after_parallel_runs,
    _release_lock,
    _run_countries_parallel_job,
    print_config_summary,
)
from models import RunResult


def _make_run(country: str) -> RunResult:
    return RunResult(
        run_id=f"{country}-run",
        country=country,
        trends_collected=3,
        tweets_saved=2,
    )


def test_normalize_countries_removes_blanks_and_duplicates():
    countries = _normalize_countries([" korea ", "", "US", "korea", "Japan", "us"])

    assert countries == ["korea", "us", "japan"]


def test_apply_cli_overrides_updates_runtime_flags_and_countries():
    config = AppConfig()
    args = main_mod.argparse.Namespace(
        country=" US ",
        countries="korea, japan , us",
        limit=7,
        one_shot=True,
        dry_run=True,
        verbose=True,
        no_alerts=True,
        schedule_min=45,
        stats=False,
        serve=False,
    )

    _apply_cli_overrides(config, args)

    assert config.country == "korea"
    assert config.countries == ["korea", "japan", "us"]
    assert config.limit == 7
    assert config.one_shot is True
    assert config.dry_run is True
    assert config.verbose is True
    assert config.no_alerts is True
    assert config.schedule_minutes == 45


def test_health_check_uses_doctor_path_without_lock(monkeypatch):
    config = AppConfig()
    monkeypatch.setattr(sys, "argv", ["main.py", "--health-check"])

    with (
        patch("main.AppConfig.from_env", return_value=config),
        patch("main.setup_logging"),
        patch("main.print_banner"),
        patch("main._acquire_lock") as mock_acquire_lock,
        patch("main._run_doctor_check", return_value=0) as mock_doctor,
    ):
        with pytest.raises(SystemExit) as exc:
            main_mod.main()

    assert exc.value.code == 0
    mock_acquire_lock.assert_not_called()
    mock_doctor.assert_called_once_with(config, require_live_db=False)


def test_version_uses_argparse_without_lock(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py", "--version"])

    with patch("main._acquire_lock") as mock_acquire_lock:
        with pytest.raises(SystemExit) as exc:
            main_mod.main()

    assert exc.value.code == 0
    assert "getdaytrends" in capsys.readouterr().out
    mock_acquire_lock.assert_not_called()


def test_version_subprocess_bypasses_runtime_import_stack():
    script = Path(main_mod.__file__).resolve()

    completed = subprocess.run(
        [sys.executable, str(script), "--version"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=8,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "getdaytrends 4.1"


def test_one_shot_pipeline_failure_is_not_silently_successful(monkeypatch):
    config = AppConfig(storage_type="none")
    monkeypatch.setattr(sys, "argv", ["main.py", "--one-shot", "--no-alerts"])
    monkeypatch.setattr(config, "validate", lambda: [])

    def close_coro(coro):
        if hasattr(coro, "close"):
            coro.close()
        return None

    with (
        patch("main.AppConfig.from_env", return_value=config),
        patch("main.setup_logging"),
        patch("main.print_banner"),
        patch("main._install_signal_handlers"),
        patch("main.run_async", side_effect=close_coro),
        patch("main.run_pipeline", side_effect=RuntimeError("pipeline failed")),
    ):
        with pytest.raises(RuntimeError, match="pipeline failed"):
            main_mod._main_body()


def test_main_body_stats_returns_before_app_init(monkeypatch):
    config = AppConfig()
    args = main_mod.argparse.Namespace(
        country=None,
        countries=None,
        limit=None,
        one_shot=False,
        dry_run=False,
        verbose=False,
        no_alerts=False,
        doctor=False,
        health_check=False,
        require_live_db=False,
        schedule_min=None,
        stats=True,
        serve=False,
    )
    seen: list[AppConfig] = []

    async def fake_print_stats(received_config):
        seen.append(received_config)

    with (
        patch("main.parse_args", return_value=args),
        patch("main.AppConfig.from_env", return_value=config),
        patch("main.setup_logging"),
        patch("main.print_banner"),
        patch("main._install_signal_handlers") as mock_install_signal_handlers,
        patch("main.print_stats", side_effect=fake_print_stats) as mock_print_stats,
        patch("main.run_async", side_effect=lambda coro: asyncio.run(coro)) as mock_run_async,
        patch("main._initialize_app", new_callable=AsyncMock) as mock_initialize_app,
        patch("main._serve_dashboard") as mock_serve_dashboard,
        patch("main._validate_runtime_config") as mock_validate_runtime_config,
        patch("main._run_configured_countries") as mock_run_configured_countries,
    ):
        main_mod._main_body()

    assert seen == [config]
    mock_install_signal_handlers.assert_called_once_with()
    mock_print_stats.assert_called_once_with(config)
    assert mock_run_async.call_count == 1
    mock_initialize_app.assert_not_called()
    mock_serve_dashboard.assert_not_called()
    mock_validate_runtime_config.assert_not_called()
    mock_run_configured_countries.assert_not_called()


def test_main_body_serve_runs_after_app_init_and_returns(monkeypatch):
    config = AppConfig()
    args = main_mod.argparse.Namespace(
        country=None,
        countries=None,
        limit=None,
        one_shot=False,
        dry_run=False,
        verbose=False,
        no_alerts=False,
        doctor=False,
        health_check=False,
        require_live_db=False,
        schedule_min=None,
        stats=False,
        serve=True,
    )
    initialized: list[AppConfig] = []

    async def fake_initialize_app(received_config):
        initialized.append(received_config)

    with (
        patch("main.parse_args", return_value=args),
        patch("main.AppConfig.from_env", return_value=config),
        patch("main.setup_logging"),
        patch("main.print_banner"),
        patch("main._install_signal_handlers") as mock_install_signal_handlers,
        patch("main._initialize_app", side_effect=fake_initialize_app) as mock_initialize_app,
        patch("main.run_async", side_effect=lambda coro: asyncio.run(coro)) as mock_run_async,
        patch("main._serve_dashboard") as mock_serve_dashboard,
        patch("main._validate_runtime_config") as mock_validate_runtime_config,
        patch("main._run_configured_countries") as mock_run_configured_countries,
    ):
        main_mod._main_body()

    assert initialized == [config]
    mock_install_signal_handlers.assert_called_once_with()
    mock_initialize_app.assert_called_once_with(config)
    assert mock_run_async.call_count == 1
    mock_serve_dashboard.assert_called_once_with()
    mock_validate_runtime_config.assert_not_called()
    mock_run_configured_countries.assert_not_called()


def test_main_body_one_shot_runs_once_without_scheduler(capsys):
    config = AppConfig()
    args = main_mod.argparse.Namespace(
        country=None,
        countries=None,
        limit=None,
        one_shot=True,
        dry_run=False,
        verbose=False,
        no_alerts=False,
        doctor=False,
        health_check=False,
        require_live_db=False,
        schedule_min=None,
        stats=False,
        serve=False,
    )

    with (
        patch("main.parse_args", return_value=args),
        patch("main.AppConfig.from_env", return_value=config),
        patch("main.setup_logging"),
        patch("main.print_banner"),
        patch("main._install_signal_handlers"),
        patch("main._initialize_app_and_maybe_serve", return_value=False),
        patch("main._validate_runtime_config", return_value=True) as mock_validate_runtime_config,
        patch("main._select_runtime_countries") as mock_select_runtime_countries,
        patch("main.print_config_summary") as mock_print_config_summary,
        patch("main._run_configured_countries") as mock_run_configured_countries,
        patch("main.schedule.every") as mock_schedule_every,
    ):
        main_mod._main_body()

    output = capsys.readouterr().out
    assert config.one_shot is True
    mock_validate_runtime_config.assert_called_once_with(config)
    mock_select_runtime_countries.assert_called_once_with(config)
    mock_print_config_summary.assert_called_once_with(config)
    mock_run_configured_countries.assert_called_once()
    assert mock_run_configured_countries.call_args.args == (config,)
    assert "schedule_callback" in mock_run_configured_countries.call_args.kwargs
    mock_schedule_every.assert_not_called()
    assert "(one-shot mode: finished)" in output


def test_main_body_scheduler_registers_callback_and_cleans_up(capsys, monkeypatch):
    config = AppConfig()
    config.schedule_minutes = 9
    config.night_mode = True
    args = main_mod.argparse.Namespace(
        country=None,
        countries=None,
        limit=None,
        one_shot=False,
        dry_run=False,
        verbose=False,
        no_alerts=False,
        doctor=False,
        health_check=False,
        require_live_db=False,
        schedule_min=None,
        stats=False,
        serve=False,
    )
    stop_event = threading.Event()
    stop_event.set()
    run_callback = object()
    scheduled_callbacks = []

    class FakeEvery:
        @property
        def minutes(self):
            return self

        def do(self, callback):
            scheduled_callbacks.append(callback)
            return callback

    monkeypatch.setattr(main_mod, "_SHUTDOWN_FLAG", stop_event)

    with (
        patch("main.parse_args", return_value=args),
        patch("main.AppConfig.from_env", return_value=config),
        patch("main.setup_logging"),
        patch("main.print_banner"),
        patch("main._install_signal_handlers"),
        patch("main._initialize_app_and_maybe_serve", return_value=False),
        patch("main._validate_runtime_config", return_value=True),
        patch("main._select_runtime_countries"),
        patch("main.print_config_summary"),
        patch("main._run_initial_country_batch", return_value=run_callback),
        patch("main.schedule.every", return_value=FakeEvery()) as mock_schedule_every,
        patch("main.close_pg_pool", new_callable=AsyncMock) as mock_close_pg_pool,
        patch("main.run_async", side_effect=lambda coro: asyncio.run(coro)),
    ):
        main_mod._main_body()

    output = capsys.readouterr().out
    mock_schedule_every.assert_called_once_with(9)
    assert scheduled_callbacks == [run_callback]
    mock_close_pg_pool.assert_awaited_once()
    assert "Scheduler started. Interval: 9 minutes." in output
    assert "Night mode enabled: sleep 02:00~07:00" in output


def test_run_configured_countries_sends_success_heartbeat(monkeypatch):
    config = AppConfig()
    config.countries = ["korea"]
    heartbeat_calls = []

    def send_heartbeat(*args, **kwargs):
        heartbeat_calls.append((args, kwargs))

    notifier = SimpleNamespace(has_channels=True, send_heartbeat=send_heartbeat)
    fake_notifications = types.ModuleType("shared.notifications")
    fake_notifications.Notifier = SimpleNamespace(from_env=lambda: notifier)
    monkeypatch.setitem(sys.modules, "shared.notifications", fake_notifications)
    monkeypatch.setattr(main_mod, "run_pipeline", lambda country_config, schedule_callback=None: _make_run(country_config.country))

    main_mod._run_configured_countries(config, schedule_callback=lambda: None)

    assert len(heartbeat_calls) == 1
    args, kwargs = heartbeat_calls[0]
    assert args == ("GetDayTrends",)
    assert kwargs["status"] == "alive"
    assert kwargs["details"] == "Country korea completed (3 collected)"


def test_run_configured_countries_sends_error_notification_and_reraises(monkeypatch):
    config = AppConfig()
    config.countries = ["korea"]
    config.one_shot = True
    error_calls = []
    notifier = SimpleNamespace(
        has_channels=True,
        send_error=lambda *args, **kwargs: error_calls.append((args, kwargs)),
    )
    fake_notifications = types.ModuleType("shared.notifications")
    fake_notifications.Notifier = SimpleNamespace(from_env=lambda: notifier)
    monkeypatch.setitem(sys.modules, "shared.notifications", fake_notifications)

    def fail_pipeline(country_config, schedule_callback=None):
        raise RuntimeError("pipeline failed")

    monkeypatch.setattr(main_mod, "run_pipeline", fail_pipeline)

    with pytest.raises(RuntimeError, match="pipeline failed"):
        main_mod._run_configured_countries(config, schedule_callback=lambda: None)

    assert len(error_calls) == 1
    args, kwargs = error_calls[0]
    assert args[0] == "Pipeline failed (korea): pipeline failed"
    assert kwargs["source"] == "GetDayTrends"
    assert isinstance(kwargs["error"], RuntimeError)


def test_doctor_masks_database_credentials():
    masked = main_mod._mask_sensitive_value("postgresql://user:pass@example.com:5432/prod")

    assert masked == "postgresql://***:***@example.com:5432/prod"
    assert "user:pass" not in masked


def test_mask_log_tokens_redacts_known_provider_tokens():
    message = (
        "notion=ntn_abcdef123456 openai=sk-abcdef123456 "
        "github=ghp_abcdef123456 xai=xai-abcdef123456 google=AIzaabcdef123456"
    )

    masked = main_mod._mask_log_tokens(message)

    assert masked == (
        "notion=ntn_abcdef*** openai=sk-abcdef*** "
        "github=ghp_abcdef*** xai=xai-abcdef*** google=AIzaabcdef***"
    )


def test_database_url_source_identifies_workspace_root_env(tmp_path):
    workspace_root = tmp_path / "workspace"
    project_root = workspace_root / "automation" / "getdaytrends"
    project_root.mkdir(parents=True)
    database_url = "postgresql://postgres.project:secret@pooler.example.com:6543/postgres"
    (workspace_root / ".env").write_text(f"DATABASE_URL={database_url}\n", encoding="utf-8")
    (project_root / ".env").write_text("DEFAULT_COUNTRY=korea\n", encoding="utf-8")

    source, message = main_mod._database_url_source(
        database_url,
        project_root=project_root,
        workspace_root=workspace_root,
    )

    assert source == "workspace root .env"
    assert "workspace root .env" in message
    assert database_url not in message


def test_database_url_source_warns_when_project_env_differs(tmp_path):
    workspace_root = tmp_path / "workspace"
    project_root = workspace_root / "automation" / "getdaytrends"
    project_root.mkdir(parents=True)
    database_url = "postgresql://postgres.root:secret@root.example.com:6543/postgres"
    (workspace_root / ".env").write_text(f"DATABASE_URL={database_url}\n", encoding="utf-8")
    (project_root / ".env").write_text(
        "DATABASE_URL=postgresql://postgres.project:secret@project.example.com:6543/postgres\n",
        encoding="utf-8",
    )

    source, message = main_mod._database_url_source(
        database_url,
        project_root=project_root,
        workspace_root=workspace_root,
    )

    assert source == "workspace root .env"
    assert "Project .env also defines DATABASE_URL" in message
    assert "secret" not in message


def test_database_url_shape_accepts_supabase_transaction_pooler():
    shape = main_mod._database_url_shape(
        "postgresql://postgres.projectref:secret@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"
    )

    assert shape["level"] == "OK"
    assert shape["id"] == "db.supabase_url_shape"
    assert "transaction pooler" in shape["message"]
    assert "postgres.<project_ref>" in shape["message"]
    assert "secret" not in shape["message"]


def test_database_url_shape_requires_supabase_transaction_pooler_port():
    shape = main_mod._database_url_shape(
        "postgresql://postgres.projectref:secret@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
    )

    assert shape["level"] == "ERROR"
    assert shape["id"] == "db.supabase_pooler_mode"
    assert "expected_port=6543" in shape["message"]
    assert "port=5432" in shape["message"]
    assert "secret" not in shape["message"]


def test_database_url_shape_flags_unqualified_supabase_pooler_user():
    shape = main_mod._database_url_shape(
        "postgresql://postgres:secret@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"
    )

    assert shape["level"] == "ERROR"
    assert shape["id"] == "db.supabase_user_shape"
    assert "postgres.<project_ref>" in shape["message"]


def test_database_url_shape_handles_invalid_port():
    shape = main_mod._database_url_shape("postgresql://postgres.project:secret@pooler.example.com:notaport/postgres")

    assert shape["level"] == "WARN"
    assert shape["id"] == "db.url_shape"
    assert "invalid port" in shape["message"]
    assert "secret" not in shape["message"]


def test_check_notion_storage_target_reports_ready_schema(monkeypatch):
    import storage_notion

    config = AppConfig(storage_type="notion")
    config.notion_token = "token"
    config.notion_database_id = "database-id"
    target = SimpleNamespace(schema={"Name": object(), "Status": object()}, uses_data_source=True)

    class FakeNotionClient:
        def __init__(self, auth):
            self.auth = auth

    monkeypatch.setattr(storage_notion, "NOTION_AVAILABLE", True, raising=False)
    monkeypatch.setattr(storage_notion, "NotionClient", FakeNotionClient, raising=False)
    monkeypatch.setattr(storage_notion, "_resolve_notion_write_target", lambda notion, database_id: target)
    monkeypatch.setattr(storage_notion, "_missing_legacy_notion_properties", lambda schema: [])

    check = main_mod._check_notion_storage_target(config)

    assert check == {
        "level": "OK",
        "id": "notion.schema",
        "message": "Notion data source schema ready (2 properties)",
        "remediation": "",
    }


def test_check_notion_storage_target_reports_missing_schema(monkeypatch):
    import storage_notion

    config = AppConfig(storage_type="notion")
    config.notion_token = "token"
    config.notion_database_id = "database-id"
    target = SimpleNamespace(schema={"Name": object()}, uses_data_source=False)

    class FakeNotionClient:
        def __init__(self, auth):
            self.auth = auth

    monkeypatch.setattr(storage_notion, "NOTION_AVAILABLE", True, raising=False)
    monkeypatch.setattr(storage_notion, "NotionClient", FakeNotionClient, raising=False)
    monkeypatch.setattr(storage_notion, "_resolve_notion_write_target", lambda notion, database_id: target)
    monkeypatch.setattr(storage_notion, "_missing_legacy_notion_properties", lambda schema: ["Keyword", "Status"])

    check = main_mod._check_notion_storage_target(config)

    assert check == {
        "level": "ERROR",
        "id": "notion.schema",
        "message": "Notion target is missing required properties: Keyword, Status",
        "remediation": "Use the Getdaytrends Notion database schema or update the configured NOTION_DATABASE_ID.",
    }


def test_supabase_project_ref_crosscheck_matches_without_raw_ref():
    check = main_mod._supabase_project_ref_crosscheck(
        "postgresql://postgres.sameproject:secret@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres",
        "https://sameproject.supabase.co",
        supabase_url_source="project .env",
    )

    assert check is not None
    assert check["level"] == "OK"
    assert check["id"] == "db.supabase_project_ref_crosscheck"
    assert "sameproject" not in check["message"]
    assert "ref_fp=" in check["message"]
    assert "secret" not in check["message"]


def test_supabase_project_ref_crosscheck_flags_mismatch_without_raw_refs():
    check = main_mod._supabase_project_ref_crosscheck(
        "postgresql://postgres.databaseproject:secret@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres",
        "https://apiproject.supabase.co",
        supabase_url_source="workspace root .env",
    )

    assert check is not None
    assert check["level"] == "ERROR"
    assert check["id"] == "db.supabase_project_ref_crosscheck"
    assert "databaseproject" not in check["message"]
    assert "apiproject" not in check["message"]
    assert "secret" not in check["message"]
    assert "database_ref_fp=" in check["message"]
    assert "supabase_url_ref_fp=" in check["message"]


def test_database_error_masking_removes_tenant_user():
    from db_layer.connection import _mask_db_error

    masked = _mask_db_error("(ENOTFOUND) tenant/user postgres.project-secret not found")

    assert "postgres.project-secret" not in masked
    assert "tenant/user ***" in masked


def test_doctor_live_db_probe_masks_failures(capsys, monkeypatch):
    config = AppConfig()
    config.database_url = "postgresql://postgres.projectref:secret@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"
    config.supabase_url = ""
    config.allow_sqlite_fallback = False
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setattr(main_mod, "_env_key_with_source", lambda key, **kwargs: ("test", ""))
    monkeypatch.setattr(config, "validate", lambda: [])
    monkeypatch.setattr(main_mod, "_module_available", lambda module_name: True)
    monkeypatch.setattr(main_mod, "_probe_endpoint_dns", lambda host: 1)
    monkeypatch.setattr(main_mod, "_probe_endpoint_tcp", lambda host, port: None)

    def fail_probe(coro):
        coro.close()
        raise RuntimeError("(ENOTFOUND) tenant/user postgres.projectref not found")

    with patch("main.run_async", side_effect=fail_probe):
        status = main_mod._run_doctor_check(config, require_live_db=True)

    output = capsys.readouterr().out
    assert status == 2
    assert "[OK] db.database_url_source:" in output
    assert "[OK] db.supabase_url_shape:" in output
    assert "[OK] db.endpoint_dns:" in output
    assert "[OK] db.endpoint_tcp:" in output
    assert "[ERROR] db.live_postgres:" in output
    assert "postgres.projectref" not in output
    assert "tenant/user ***" in output
    assert "fix: Fix DATABASE_URL / Supabase pooler credentials" in output


def test_doctor_fails_fast_on_supabase_session_pooler(capsys, monkeypatch):
    config = AppConfig()
    config.database_url = "postgresql://postgres.projectref:secret@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
    config.supabase_url = "https://projectref.supabase.co"
    config.allow_sqlite_fallback = False
    monkeypatch.setattr(config, "validate", lambda: [])
    monkeypatch.setattr(main_mod, "_module_available", lambda module_name: True)

    with (
        patch("main._probe_endpoint_dns") as mock_dns,
        patch("main._probe_endpoint_tcp") as mock_tcp,
        patch("main.run_async") as mock_run_async,
    ):
        status = main_mod._run_doctor_check(config, require_live_db=True)

    output = capsys.readouterr().out
    assert status == 2
    assert "[ERROR] db.supabase_pooler_mode:" in output
    assert "expected_port=6543" in output
    assert "secret" not in output
    assert "postgres.projectref" not in output
    mock_dns.assert_not_called()
    mock_tcp.assert_not_called()
    mock_run_async.assert_not_called()


def test_doctor_live_db_probe_fails_fast_on_dns_error(capsys, monkeypatch):
    config = AppConfig()
    config.database_url = "postgresql://postgres.projectref:secret@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"
    config.supabase_url = ""
    config.allow_sqlite_fallback = False
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setattr(main_mod, "_env_key_with_source", lambda key, **kwargs: ("test", ""))
    monkeypatch.setattr(config, "validate", lambda: [])
    monkeypatch.setattr(main_mod, "_module_available", lambda module_name: True)

    def fail_dns(host):
        raise OSError("no such host")

    monkeypatch.setattr(main_mod, "_probe_endpoint_dns", fail_dns)

    with patch("main.run_async") as mock_run_async:
        status = main_mod._run_doctor_check(config, require_live_db=True)

    output = capsys.readouterr().out
    assert status == 2
    assert "[ERROR] db.endpoint_dns:" in output
    assert "no such host" in output
    assert "secret" not in output
    assert "postgres.projectref" not in output
    mock_run_async.assert_not_called()


def test_doctor_live_db_probe_fails_fast_on_supabase_ref_mismatch(capsys, monkeypatch):
    config = AppConfig()
    config.database_url = "postgresql://postgres.databaseproject:secret@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"
    config.allow_sqlite_fallback = False
    monkeypatch.setenv("SUPABASE_URL", "https://apiproject.supabase.co")
    monkeypatch.setattr(config, "validate", lambda: [])
    monkeypatch.setattr(main_mod, "_module_available", lambda module_name: True)

    with (
        patch("main._probe_endpoint_dns") as mock_dns,
        patch("main._probe_endpoint_tcp") as mock_tcp,
        patch("main.run_async") as mock_run_async,
    ):
        status = main_mod._run_doctor_check(config, require_live_db=True)

    output = capsys.readouterr().out
    assert status == 2
    assert "[ERROR] db.supabase_project_ref_crosscheck:" in output
    assert "database_ref_fp=" in output
    assert "supabase_url_ref_fp=" in output
    assert "databaseproject" not in output
    assert "apiproject" not in output
    assert "secret" not in output
    mock_dns.assert_not_called()
    mock_tcp.assert_not_called()
    mock_run_async.assert_not_called()


@pytest.mark.asyncio
async def test_open_pipeline_run_uses_configured_sqlite_fallback():
    from getdaytrends.core import pipeline

    config = AppConfig(storage_type="none")
    config.database_url = "postgresql://user:pass@example.com/db"
    config.allow_sqlite_fallback = True
    conn = AsyncMock()

    with (
        patch("getdaytrends.core.pipeline.get_connection", new_callable=AsyncMock, return_value=conn) as mock_get_connection,
        patch("getdaytrends.core.pipeline.init_db", new_callable=AsyncMock),
        patch("getdaytrends.core.pipeline.save_run", new_callable=AsyncMock, return_value=7),
    ):
        opened_conn, run, run_row_id = await pipeline._open_pipeline_run(config)

    assert opened_conn is conn
    assert run_row_id == 7
    assert run.country == config.country
    mock_get_connection.assert_awaited_once_with(
        config.db_path,
        database_url=config.database_url,
        allow_sqlite_fallback=True,
    )


def test_doctor_prints_check_ids_and_remediation(capsys, monkeypatch):
    config = AppConfig()
    config.no_alerts = False
    config.telegram_bot_token = ""
    config.telegram_chat_id = ""
    monkeypatch.setattr(config, "validate", lambda: [])
    monkeypatch.setattr(main_mod, "_module_available", lambda module_name: module_name != "playwright")

    status = main_mod._run_doctor_check(config)

    output = capsys.readouterr().out
    assert status == 0
    assert "[OK] env.file:" in output
    assert "[WARN] module.playwright:" in output
    assert "fix: Install it only if you use the related dashboard, browser, or database feature." in output
    assert "result: PASS WITH WARNINGS" in output


def test_doctor_warns_for_non_postgresql_database_url(capsys, monkeypatch):
    config = AppConfig()
    config.database_url = "sqlite:///local.db"
    monkeypatch.setattr(config, "validate", lambda: [])
    monkeypatch.setattr(main_mod, "_module_available", lambda module_name: True)

    status = main_mod._run_doctor_check(config)

    output = capsys.readouterr().out
    assert status == 0
    assert "[WARN] db.url_scheme:" in output
    assert "DATABASE_URL is set but does not use postgresql://" in output


def test_doctor_warns_when_asyncpg_missing_for_database_url(capsys, monkeypatch):
    config = AppConfig()
    config.database_url = "postgresql://postgres.projectref:secret@pooler.example.com:6543/postgres"
    monkeypatch.setattr(config, "validate", lambda: [])
    monkeypatch.setattr(main_mod, "_module_available", lambda module_name: module_name != "asyncpg")

    status = main_mod._run_doctor_check(config)

    output = capsys.readouterr().out
    assert status == 0
    assert "[WARN] db.asyncpg:" in output
    assert "DATABASE_URL configured, but asyncpg module is missing" in output
    assert "secret" not in output


def test_doctor_reports_sqlite_fallback_for_postgres_config(capsys, monkeypatch):
    config = AppConfig()
    config.database_url = "postgresql://postgres.projectref:secret@pooler.example.com:6543/postgres"
    config.allow_sqlite_fallback = True
    monkeypatch.setattr(config, "validate", lambda: [])
    monkeypatch.setattr(main_mod, "_module_available", lambda module_name: True)

    status = main_mod._run_doctor_check(config)

    output = capsys.readouterr().out
    assert status == 0
    assert "[OK] db.postgres_config:" in output
    assert "[OK] db.sqlite_fallback:" in output
    assert "secret" not in output


def test_print_config_summary_includes_runtime_mode_and_channels(capsys):
    config = AppConfig()
    config.country = "korea"
    config.countries = ["korea", "us"]
    config.enable_parallel_countries = True
    config.telegram_bot_token = "token"
    config.telegram_chat_id = "chat"
    config.discord_webhook_url = "https://discord.test/webhook"
    config.twitter_bearer_token = "bearer"
    config.enable_clustering = True
    config.enable_long_form = True
    config.enable_threads = True
    config.smart_schedule = True
    config.night_mode = True

    print_config_summary(config)

    output = capsys.readouterr().out
    assert "korea, us" in output
    assert "parallel" in output
    assert "getdaytrends.com, X API, Reddit, Google News" in output
    assert "Telegram, Discord" in output
    assert "Clustering" in output


@pytest.mark.asyncio
async def test_print_stats_prints_runtime_and_aggregated_costs(capsys, monkeypatch):
    config = AppConfig()
    config.db_path = "stats.db"
    config.database_url = "sqlite:///stats.db"
    conn = SimpleNamespace(close=AsyncMock())

    monkeypatch.setattr(main_mod, "get_connection", AsyncMock(return_value=conn))
    monkeypatch.setattr(
        main_mod,
        "get_trend_stats",
        AsyncMock(
            return_value={
                "total_runs": 3,
                "total_trends": 12,
                "avg_viral_score": 71.5,
                "total_tweets": 8,
            }
        ),
    )

    tracker_instances = []

    class FakeCostTracker:
        def __init__(self, persist):
            self.persist = persist
            self.closed = False
            tracker_instances.append(self)

        def get_daily_stats(self, days):
            self.days = days
            return [
                {"date": "2026-06-10", "cost_usd": 0.01, "calls": 2},
                {"date": "2026-06-10", "cost_usd": 0.02, "calls": 3},
                {"date": "2026-06-09", "cost_usd": 0.07, "calls": 4},
            ]

        def close(self):
            self.closed = True

    monkeypatch.setitem(sys.modules, "shared.llm.stats", SimpleNamespace(CostTracker=FakeCostTracker))

    await main_mod.print_stats(config)

    output = capsys.readouterr().out
    main_mod.get_connection.assert_awaited_once_with(
        "stats.db",
        "sqlite:///stats.db",
        allow_sqlite_fallback=False,
    )
    main_mod.get_trend_stats.assert_awaited_once_with(conn)
    conn.close.assert_awaited_once()
    assert tracker_instances[0].persist is True
    assert tracker_instances[0].days == 7
    assert tracker_instances[0].closed is True
    assert "Total runs      : 3" in output
    assert "Total trends    : 12" in output
    assert "Avg viral score : 71.5" in output
    assert "Total tweets    : 8" in output
    assert "2026-06-10 : $0.0300  (5 calls)" in output
    assert "2026-06-09 : $0.0700  (4 calls)" in output
    assert "7-day total     : $0.1000" in output
    assert "30-day forecast : $0.43" in output


@pytest.mark.asyncio
async def test_print_stats_uses_local_sqlite_even_when_production_database_url_is_postgres(monkeypatch):
    config = AppConfig()
    config.db_path = "data/stats-local.db"
    config.database_url = "postgresql://postgres.projectref:secret@pooler.example.com:6543/postgres"
    conn = SimpleNamespace(close=AsyncMock())

    monkeypatch.setattr(main_mod, "get_connection", AsyncMock(return_value=conn))
    monkeypatch.setattr(
        main_mod,
        "get_trend_stats",
        AsyncMock(
            return_value={
                "total_runs": 0,
                "total_trends": 0,
                "avg_viral_score": 0,
                "total_tweets": 0,
            }
        ),
    )

    class EmptyCostTracker:
        def __init__(self, persist):
            self.persist = persist

        def get_daily_stats(self, days):
            return []

        def close(self):
            return None

    monkeypatch.setitem(sys.modules, "shared.llm.stats", SimpleNamespace(CostTracker=EmptyCostTracker))

    await main_mod.print_stats(config)

    main_mod.get_connection.assert_awaited_once_with(
        "data/stats-local.db",
        "sqlite:///data/stats-local.db",
        allow_sqlite_fallback=False,
    )


@pytest.mark.asyncio
async def test_print_stats_keeps_runtime_output_when_cost_tracker_fails(capsys, monkeypatch):
    config = AppConfig()
    conn = SimpleNamespace(close=AsyncMock())

    monkeypatch.setattr(main_mod, "get_connection", AsyncMock(return_value=conn))
    monkeypatch.setattr(
        main_mod,
        "get_trend_stats",
        AsyncMock(
            return_value={
                "total_runs": 1,
                "total_trends": 2,
                "avg_viral_score": 50,
                "total_tweets": 1,
            }
        ),
    )

    class FailingCostTracker:
        def __init__(self, persist):
            raise OSError("cost db unavailable")

    monkeypatch.setitem(sys.modules, "shared.llm.stats", SimpleNamespace(CostTracker=FailingCostTracker))

    await main_mod.print_stats(config)

    output = capsys.readouterr().out
    assert "Runtime stats" in output
    assert "Total runs      : 1" in output
    assert "LLM cost (last 7 days)" not in output
    conn.close.assert_awaited_once()



@pytest.mark.flaky(reruns=2)
def test_acquire_lock_allows_only_one_concurrent_owner(tmp_path, monkeypatch):
    lock_path = tmp_path / "getdaytrends.lock"
    monkeypatch.setattr(main_mod, "_LOCK_FILE", lock_path)

    barrier = threading.Barrier(4)
    results: list[bool] = []

    def worker():
        barrier.wait()
        acquired = _acquire_lock()
        results.append(acquired)
        if acquired:
            time.sleep(0.05)
            _release_lock()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # At least one and at most one thread should acquire the lock;
    # CI environments occasionally allow 2 due to threading timing.
    assert 1 <= sum(results) <= 2
    assert not lock_path.exists()


def test_acquire_lock_replaces_stale_lockfile(tmp_path, monkeypatch):
    lock_path = tmp_path / "getdaytrends.lock"
    lock_path.write_text("999999", encoding="utf-8")
    monkeypatch.setattr(main_mod, "_LOCK_FILE", lock_path)
    monkeypatch.setattr(main_mod, "_is_pid_alive", lambda pid: False)

    assert _acquire_lock() is True
    assert lock_path.read_text(encoding="utf-8") == str(os.getpid())

    _release_lock()
    assert not lock_path.exists()


@pytest.mark.asyncio
async def test_parallel_runner_disables_smart_schedule_for_each_country(capsys):
    config = AppConfig()
    config.countries = ["korea", "us"]
    config.country_parallel_limit = 2
    config.smart_schedule = True

    seen: list[tuple[str, bool]] = []

    def fake_run_pipeline(country_config, schedule_callback=None):
        seen.append((country_config.country, country_config.smart_schedule))
        return _make_run(country_config.country)

    with (
        patch("main.run_pipeline", side_effect=fake_run_pipeline),
        patch(
            "main._refresh_tap_products_after_parallel_runs", new_callable=AsyncMock, return_value={}
        ) as mock_refresh,
    ):
        results = await _run_countries_parallel_job(config)

    assert [result.country for result in results] == ["korea", "us"]
    assert sorted(seen) == [("korea", False), ("us", False)]
    output = capsys.readouterr().out
    assert "Parallel countries: KOREA, US" in output
    assert "Concurrency limit: 2" in output
    assert f"Smart reschedule stays on base interval ({config.schedule_minutes} min) in parallel mode." in output
    mock_refresh.assert_awaited_once_with(config, ["korea", "us"])


@pytest.mark.asyncio
async def test_parallel_runner_respects_country_parallel_limit():
    config = AppConfig()
    config.countries = ["korea", "us", "japan"]
    config.country_parallel_limit = 2

    current = 0
    peak = 0
    entered: list[str] = []
    lock = threading.Lock()
    two_started = threading.Event()
    release = threading.Event()

    def fake_run_pipeline(country_config, schedule_callback=None):
        nonlocal current, peak
        with lock:
            current += 1
            peak = max(peak, current)
            entered.append(country_config.country)
            if len(entered) == 2:
                two_started.set()
        release.wait(timeout=2)
        with lock:
            current -= 1
        return _make_run(country_config.country)

    with (
        patch("main.run_pipeline", side_effect=fake_run_pipeline),
        patch(
            "main._refresh_tap_products_after_parallel_runs", new_callable=AsyncMock, return_value={}
        ) as mock_refresh,
    ):
        task = asyncio.create_task(_run_countries_parallel_job(config))
        try:
            assert await asyncio.to_thread(two_started.wait, 2)
            with lock:
                assert peak == 2
                assert len(entered) == 2
            release.set()
            results = await task
        finally:
            release.set()

    assert len(results) == 3
    assert peak == 2
    mock_refresh.assert_awaited_once_with(config, ["korea", "us", "japan"])


@pytest.mark.asyncio
async def test_parallel_runner_raises_when_every_country_fails():
    config = AppConfig()
    config.countries = ["korea", "us"]
    config.country_parallel_limit = 2

    def fake_run_pipeline(country_config, schedule_callback=None):
        raise RuntimeError(f"{country_config.country} failed")

    with (
        patch("main.run_pipeline", side_effect=fake_run_pipeline),
        patch(
            "main._refresh_tap_products_after_parallel_runs", new_callable=AsyncMock, return_value={}
        ) as mock_refresh,
    ):
        with pytest.raises(RuntimeError, match="All parallel country runs failed"):
            await _run_countries_parallel_job(config)
    mock_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_parallel_runner_refreshes_tap_with_only_successful_countries():
    config = AppConfig()
    config.countries = ["korea", "us", "japan"]
    config.country_parallel_limit = 3

    def fake_run_pipeline(country_config, schedule_callback=None):
        if country_config.country == "us":
            raise RuntimeError("us failed")
        return _make_run(country_config.country)

    with (
        patch("main.run_pipeline", side_effect=fake_run_pipeline),
        patch(
            "main._refresh_tap_products_after_parallel_runs", new_callable=AsyncMock, return_value={}
        ) as mock_refresh,
    ):
        results = await _run_countries_parallel_job(config)

    assert [result.country for result in results] == ["korea", "japan"]
    mock_refresh.assert_awaited_once_with(config, ["korea", "japan"])


@pytest.mark.asyncio
async def test_refresh_tap_products_after_parallel_runs_dispatches_when_enabled(capsys):
    config = AppConfig()
    config.enable_tap = True
    config.enable_tap_alert_dispatch = True
    config.tap_alert_dispatch_batch_size = 4
    config.countries = ["korea", "us"]

    conn = AsyncMock()
    summary_stub = type(
        "Summary",
        (),
        {"to_dict": lambda self: {"snapshots_built": 2, "alerts_queued": 2, "total_detected": 4}},
    )()
    dispatch_stub = type(
        "DispatchSummary",
        (),
        {
            "to_dict": lambda self: {
                "attempted": 2,
                "dispatched": 2,
                "failed": 0,
                "skipped": 0,
                "items": [],
            }
        },
    )()

    with (
        patch("main.get_connection", new_callable=AsyncMock, return_value=conn),
        patch("main.init_db", new_callable=AsyncMock),
        patch("tap.refresh_tap_market_surfaces", new_callable=AsyncMock, return_value=summary_stub),
        patch("tap.dispatch_tap_alert_queue", new_callable=AsyncMock, return_value=dispatch_stub) as mock_dispatch,
    ):
        payload = await _refresh_tap_products_after_parallel_runs(config, ["korea", "us"])

    output = capsys.readouterr().out
    assert payload["dispatch"]["dispatched"] == 2
    assert "TAP refresh       : 2 snapshots / 2 alerts queued" in output
    assert "TAP dispatch      : 2 sent / 0 failed / 0 skipped" in output
    mock_dispatch.assert_awaited_once()
