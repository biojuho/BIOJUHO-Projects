from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_script_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "migrate_sqlite_to_supabase.py"
    spec = importlib.util.spec_from_file_location("getdaytrends_migrate_sqlite_to_supabase", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_help_exits_before_migration(monkeypatch, capsys):
    module = _load_script_module()

    async def fail_if_migration_runs(*args, **kwargs):
        raise AssertionError("migration must not run for --help")

    monkeypatch.setattr(module, "_run_migration", fail_if_migration_runs)

    with pytest.raises(SystemExit) as exc_info:
        module.main(["--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "Migrate getdaytrends SQLite data to Supabase PostgreSQL." in output
    assert "DATABASE_URL is not set" not in output
