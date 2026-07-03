from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import verify_tenant_rls_postgres
from tenant_rls import RLS_GLOBAL_OPERATOR_SETTING, RLS_OWNER_IDS_SETTING

BACKEND_DIR = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_postgres_url_normalization_and_detection():
    assert verify_tenant_rls_postgres.normalize_postgres_url("postgres://user:pw@example/db") == (
        "postgresql://user:pw@example/db"
    )
    assert verify_tenant_rls_postgres.is_postgres_url("postgres://user:pw@example/db") is True
    assert verify_tenant_rls_postgres.is_postgres_url("postgresql+psycopg2://user:pw@example/db") is True
    assert verify_tenant_rls_postgres.is_postgres_url("sqlite:///tmp.db") is False


def test_policy_predicate_uses_shared_settings():
    predicate = verify_tenant_rls_postgres._policy_predicate()

    assert f"current_setting('{RLS_OWNER_IDS_SETTING}', true)" in predicate
    assert f"current_setting('{RLS_GLOBAL_OPERATOR_SETTING}', true) = 'true'" in predicate
    assert "string_to_array" in predicate


def test_skipped_report_markdown_explains_missing_postgres_url():
    report = verify_tenant_rls_postgres.run_live_smoke("")
    markdown = verify_tenant_rls_postgres.render_markdown(report)

    assert report["status"] == "skipped"
    assert "No PostgreSQL URL provided" in report["reason"]
    assert "AgriGuard PostgreSQL Tenant RLS Smoke" in markdown
    assert "skipped" in markdown


def test_tenant_rls_postgres_smoke_cli_writes_skipped_outputs(tmp_path):
    json_out = tmp_path / "rls-smoke.json"
    markdown_out = tmp_path / "rls-smoke.md"

    result = subprocess.run(
        [
            PYTHON,
            "scripts/verify_tenant_rls_postgres.py",
            "--pg-url",
            "",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.startswith("# AgriGuard PostgreSQL Tenant RLS Smoke")
    assert "[WARNING]" not in result.stdout
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["status"] == "skipped"
    assert payload["database_url_present"] is False
    assert "No PostgreSQL URL provided" in markdown_out.read_text(encoding="utf-8")


def test_tenant_rls_postgres_smoke_cli_require_live_fails_without_url(tmp_path):
    result = subprocess.run(
        [PYTHON, "scripts/verify_tenant_rls_postgres.py", "--pg-url", "", "--require-live"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "No PostgreSQL URL provided" in result.stdout
