from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tenant_rls import RLS_GLOBAL_OPERATOR_SETTING, RLS_OWNER_IDS_SETTING

SESSION_OWNER_SETTING = RLS_OWNER_IDS_SETTING
SESSION_GLOBAL_SETTING = RLS_GLOBAL_OPERATOR_SETTING


@dataclass(frozen=True)
class RLSTablePolicy:
    table: str
    policy_name: str
    owner_path: str
    using_expression: str
    check_expression: str | None = None


def _global_operator_expression() -> str:
    return f"current_setting('{SESSION_GLOBAL_SETTING}', true) = 'true'"


def _owner_membership_expression(owner_sql: str) -> str:
    owner_ids = f"nullif(current_setting('{SESSION_OWNER_SETTING}', true), '')"
    return (
        f"({owner_sql}) IS NOT NULL AND {owner_ids} IS NOT NULL "
        f"AND ({owner_sql}) = ANY(string_to_array({owner_ids}, ','))"
    )


def _direct_owner_policy(table: str) -> RLSTablePolicy:
    owner_sql = f"{table}.owner_id"
    expression = f"{_global_operator_expression()} OR ({_owner_membership_expression(owner_sql)})"
    return RLSTablePolicy(
        table=table,
        policy_name=f"agriguard_{table}_tenant_scope",
        owner_path="owner_id",
        using_expression=expression,
        check_expression=expression,
    )


def _product_relation_policy(table: str, product_column: str = "product_id") -> RLSTablePolicy:
    owner_sql = "p.owner_id"
    tenant_product_exists = (
        "EXISTS ("
        f"SELECT 1 FROM products p WHERE p.id = {table}.{product_column} "
        f"AND {_owner_membership_expression(owner_sql)}"
        ")"
    )
    expression = f"{_global_operator_expression()} OR ({tenant_product_exists})"
    return RLSTablePolicy(
        table=table,
        policy_name=f"agriguard_{table}_tenant_scope",
        owner_path=f"{product_column} -> products.owner_id",
        using_expression=expression,
        check_expression=expression,
    )


def build_policy_manifest(*, force_rls: bool = False) -> dict:
    policies = [
        _direct_owner_policy("products"),
        _direct_owner_policy("sensor_devices"),
        _product_relation_policy("qr_tokens"),
        _product_relation_policy("tracking_events"),
        _product_relation_policy("certificates"),
    ]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "session_settings": {
            SESSION_OWNER_SETTING: "comma-separated owner IDs available to the current request",
            SESSION_GLOBAL_SETTING: "true only for platform-wide operator/admin sessions",
        },
        "force_rls": force_rls,
        "policies": [asdict(policy) for policy in policies],
        "deferred_tables": [
            {
                "table": "qr_scan_events",
                "reason": (
                    "mixed consumer, product, MQTT, and sensor-admin audit rows need a dedicated audit-event "
                    "ownership model before a safe table-wide RLS policy can be generated"
                ),
            }
        ],
    }


def _policy_sql(policy: dict, *, force_rls: bool) -> list[str]:
    table = policy["table"]
    policy_name = policy["policy_name"]
    using_expression = policy["using_expression"]
    check_expression = policy["check_expression"] or using_expression
    lines = [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;",
    ]
    if force_rls:
        lines.append(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    lines.extend(
        [
            f"DROP POLICY IF EXISTS {policy_name} ON {table};",
            f"CREATE POLICY {policy_name} ON {table}",
            "  FOR ALL",
            f"  USING ({using_expression})",
            f"  WITH CHECK ({check_expression});",
        ]
    )
    return lines


def render_sql(manifest: dict) -> str:
    lines = [
        "-- AgriGuard PostgreSQL RLS policy draft.",
        "-- Review with production roles before applying as a migration.",
        f"-- Request session settings: {SESSION_OWNER_SETTING}, {SESSION_GLOBAL_SETTING}",
        "",
    ]
    for policy in manifest["policies"]:
        lines.extend(_policy_sql(policy, force_rls=manifest["force_rls"]))
        lines.append("")
    lines.extend(
        [
            "-- Deferred table:",
            "-- qr_scan_events requires an audit-event ownership model before RLS is enabled.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_markdown(manifest: dict) -> str:
    lines = [
        "# AgriGuard PostgreSQL RLS Policy Draft",
        "",
        f"- Generated at: {manifest['generated_at']}",
        f"- Force RLS: {manifest['force_rls']}",
        f"- Owner setting: `{SESSION_OWNER_SETTING}`",
        f"- Global operator setting: `{SESSION_GLOBAL_SETTING}`",
        "",
        "## Policies",
        "",
        "| Table | Owner path | Policy |",
        "|-------|------------|--------|",
    ]
    for policy in manifest["policies"]:
        lines.append(f"| `{policy['table']}` | `{policy['owner_path']}` | `{policy['policy_name']}` |")
    lines.extend(["", "## Deferred Tables", ""])
    for item in manifest["deferred_tables"]:
        lines.append(f"- `{item['table']}`: {item['reason']}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a reviewable AgriGuard PostgreSQL RLS policy draft.")
    parser.add_argument("--sql-out", type=Path, help="Optional path for rendered SQL.")
    parser.add_argument("--json-out", type=Path, help="Optional path for policy manifest JSON.")
    parser.add_argument("--markdown-out", type=Path, help="Optional path for Markdown summary.")
    parser.add_argument(
        "--force-rls",
        action="store_true",
        help="Include ALTER TABLE ... FORCE ROW LEVEL SECURITY in the draft.",
    )
    return parser.parse_args()


def _write(path: Path | None, text: str) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    manifest = build_policy_manifest(force_rls=args.force_rls)
    sql = render_sql(manifest)
    markdown = render_markdown(manifest)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write(args.sql_out, sql)
    _write(args.markdown_out, markdown)

    print(sql, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
