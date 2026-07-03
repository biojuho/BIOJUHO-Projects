from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import render_rls_policy_draft

BACKEND_DIR = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_rls_policy_manifest_covers_tenant_owned_tables():
    manifest = render_rls_policy_draft.build_policy_manifest()

    assert manifest["schema_version"] == 1
    assert manifest["force_rls"] is False
    assert {policy["table"] for policy in manifest["policies"]} == {
        "products",
        "sensor_devices",
        "qr_tokens",
        "tracking_events",
        "certificates",
    }
    assert manifest["session_settings"]["app.current_owner_ids"]
    assert manifest["session_settings"]["app.is_global_operator"]
    assert manifest["deferred_tables"] == [
        {
            "table": "qr_scan_events",
            "reason": (
                "mixed consumer, product, MQTT, and sensor-admin audit rows need a dedicated audit-event "
                "ownership model before a safe table-wide RLS policy can be generated"
            ),
        }
    ]


def test_rls_policy_sql_uses_owner_scope_and_product_joins():
    sql = render_rls_policy_draft.render_sql(render_rls_policy_draft.build_policy_manifest(force_rls=True))

    assert "ALTER TABLE products ENABLE ROW LEVEL SECURITY;" in sql
    assert "ALTER TABLE products FORCE ROW LEVEL SECURITY;" in sql
    assert "CREATE POLICY agriguard_products_tenant_scope ON products" in sql
    assert "CREATE POLICY agriguard_sensor_devices_tenant_scope ON sensor_devices" in sql
    assert "CREATE POLICY agriguard_qr_tokens_tenant_scope ON qr_tokens" in sql
    assert "EXISTS (SELECT 1 FROM products p WHERE p.id = qr_tokens.product_id" in sql
    assert "EXISTS (SELECT 1 FROM products p WHERE p.id = tracking_events.product_id" in sql
    assert "EXISTS (SELECT 1 FROM products p WHERE p.id = certificates.product_id" in sql
    assert "current_setting('app.current_owner_ids', true)" in sql
    assert "current_setting('app.is_global_operator', true) = 'true'" in sql
    assert "CREATE POLICY agriguard_qr_scan_events" not in sql


def test_rls_policy_cli_writes_json_sql_and_markdown(tmp_path):
    json_out = tmp_path / "rls.json"
    sql_out = tmp_path / "rls.sql"
    markdown_out = tmp_path / "rls.md"

    result = subprocess.run(
        [
            PYTHON,
            "scripts/render_rls_policy_draft.py",
            "--force-rls",
            "--json-out",
            str(json_out),
            "--sql-out",
            str(sql_out),
            "--markdown-out",
            str(markdown_out),
        ],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.startswith("-- AgriGuard PostgreSQL RLS policy draft.")
    assert "[WARNING]" not in result.stdout
    manifest = json.loads(json_out.read_text(encoding="utf-8"))
    assert manifest["force_rls"] is True
    assert "FORCE ROW LEVEL SECURITY" in sql_out.read_text(encoding="utf-8")
    markdown = markdown_out.read_text(encoding="utf-8")
    assert "AgriGuard PostgreSQL RLS Policy Draft" in markdown
    assert "`qr_scan_events`" in markdown
