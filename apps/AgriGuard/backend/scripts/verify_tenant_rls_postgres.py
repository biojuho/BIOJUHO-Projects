# ruff: noqa: S608  # SQL identifiers are hardcoded smoke-test constants, not user input
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tenant_rls import RLS_GLOBAL_OPERATOR_SETTING, RLS_OWNER_IDS_SETTING, apply_tenant_rls_context

SMOKE_TABLE = "agriguard_rls_smoke_products"
SMOKE_POLICY = "agriguard_rls_smoke_products_tenant_scope"
TENANT_ONE_USER = {"uid": "tenant-one", "role": "sensor_operator"}
TENANT_TWO_USER = {"uid": "tenant-two", "role": "sensor_operator"}
GLOBAL_OPERATOR_USER = {"uid": "ops-user", "role": "quality_manager"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_postgres_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql://" + database_url.removeprefix("postgres://")
    return database_url


def is_postgres_url(database_url: str) -> bool:
    normalized = normalize_postgres_url(database_url)
    return normalized.startswith("postgresql://") or normalized.startswith("postgresql+")


def _empty_report(status: str, *, reason: str, database_url_present: bool) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": _now(),
        "status": status,
        "reason": reason,
        "database_url_present": database_url_present,
        "smoke_table": SMOKE_TABLE,
        "session_settings": [RLS_OWNER_IDS_SETTING, RLS_GLOBAL_OPERATOR_SETTING],
        "checks": [],
    }


def _policy_predicate() -> str:
    owner_ids = f"nullif(current_setting('{RLS_OWNER_IDS_SETTING}', true), '')"
    return (
        f"current_setting('{RLS_GLOBAL_OPERATOR_SETTING}', true) = 'true' "
        f"OR ({SMOKE_TABLE}.owner_id IS NOT NULL AND {owner_ids} IS NOT NULL "
        f"AND {SMOKE_TABLE}.owner_id = ANY(string_to_array({owner_ids}, ',')))"
    )


def _create_smoke_fixture(connection) -> None:
    predicate = _policy_predicate()
    connection.execute(text(f"DROP TABLE IF EXISTS {SMOKE_TABLE}"))
    connection.execute(
        text(
            f"""
            CREATE TEMPORARY TABLE {SMOKE_TABLE} (
                id text PRIMARY KEY,
                owner_id text NOT NULL,
                product_name text NOT NULL
            ) ON COMMIT PRESERVE ROWS
            """
        )
    )
    connection.execute(
        text(
            f"""
            INSERT INTO {SMOKE_TABLE} (id, owner_id, product_name)
            VALUES
                ('tenant-one-product', 'tenant-one', 'Tenant One Greens'),
                ('tenant-two-product', 'tenant-two', 'Tenant Two Berries')
            """
        )
    )
    connection.execute(text(f"ALTER TABLE {SMOKE_TABLE} ENABLE ROW LEVEL SECURITY"))
    connection.execute(text(f"ALTER TABLE {SMOKE_TABLE} FORCE ROW LEVEL SECURITY"))
    connection.execute(text(f"CREATE POLICY {SMOKE_POLICY} ON {SMOKE_TABLE} FOR ALL USING ({predicate}) WITH CHECK ({predicate})"))
    connection.commit()


def _role_info(connection) -> dict[str, Any]:
    row = connection.execute(
        text(
            """
            SELECT
                current_database() AS database_name,
                current_user AS role_name,
                COALESCE((SELECT rolsuper FROM pg_roles WHERE rolname = current_user), false) AS is_superuser,
                COALESCE((SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user), false) AS has_bypassrls
            """
        )
    ).mappings().one()
    return dict(row)


def _fetch_ids(db) -> list[str]:
    rows = db.execute(text(f"SELECT id FROM {SMOKE_TABLE} ORDER BY id")).all()
    return [str(row[0]) for row in rows]


def _query_with_context(session_factory, current_user: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    with session_factory() as db:
        context = apply_tenant_rls_context(db, current_user)
        ids = _fetch_ids(db)
        db.commit()
        return ids, asdict(context)


def _query_without_context(session_factory) -> list[str]:
    with session_factory() as db:
        ids = _fetch_ids(db)
        db.commit()
        return ids


def _check(name: str, expected: list[str], actual: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "expected_ids": expected,
        "actual_ids": actual,
        "ok": actual == expected,
    }


def run_live_smoke(database_url: str) -> dict[str, Any]:
    if not database_url:
        return _empty_report(
            "skipped",
            reason="No PostgreSQL URL provided. Set DATABASE_URL or pass --pg-url.",
            database_url_present=False,
        )
    if not is_postgres_url(database_url):
        return _empty_report(
            "skipped",
            reason="Provided URL is not a PostgreSQL SQLAlchemy URL.",
            database_url_present=True,
        )

    normalized_url = normalize_postgres_url(database_url)
    engine = create_engine(normalized_url, pool_size=1, max_overflow=0, pool_pre_ping=True, future=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    try:
        with engine.connect() as connection:
            role_info = _role_info(connection)
            if role_info["is_superuser"] or role_info["has_bypassrls"]:
                return {
                    **_empty_report(
                        "blocked",
                        reason="Current PostgreSQL role bypasses RLS; use a non-superuser role without BYPASSRLS.",
                        database_url_present=True,
                    ),
                    "role": role_info,
                }
            _create_smoke_fixture(connection)

        no_context_before = _query_without_context(session_factory)
        tenant_one_ids, tenant_one_context = _query_with_context(session_factory, TENANT_ONE_USER)
        no_context_after = _query_without_context(session_factory)
        tenant_two_ids, tenant_two_context = _query_with_context(session_factory, TENANT_TWO_USER)
        operator_ids, operator_context = _query_with_context(session_factory, GLOBAL_OPERATOR_USER)

        checks = [
            _check("no_context_denies_all_before_setting", [], no_context_before),
            _check("tenant_one_sees_only_tenant_one_product", ["tenant-one-product"], tenant_one_ids),
            _check("transaction_local_settings_reset_after_commit", [], no_context_after),
            _check("tenant_two_sees_only_tenant_two_product", ["tenant-two-product"], tenant_two_ids),
            _check("global_operator_sees_all_products", ["tenant-one-product", "tenant-two-product"], operator_ids),
        ]
        status = "pass" if all(item["ok"] for item in checks) else "fail"
        return {
            "schema_version": 1,
            "generated_at": _now(),
            "status": status,
            "database_url_present": True,
            "role": role_info,
            "smoke_table": SMOKE_TABLE,
            "smoke_policy": SMOKE_POLICY,
            "pool": {"pool_size": 1, "max_overflow": 0, "pool_pre_ping": True},
            "session_settings": [RLS_OWNER_IDS_SETTING, RLS_GLOBAL_OPERATOR_SETTING],
            "contexts": {
                "tenant_one": tenant_one_context,
                "tenant_two": tenant_two_context,
                "global_operator": operator_context,
            },
            "checks": checks,
        }
    except SQLAlchemyError as exc:
        return {
            **_empty_report("fail", reason=f"PostgreSQL RLS smoke failed: {exc}", database_url_present=True),
            "error_type": exc.__class__.__name__,
        }
    finally:
        engine.dispose()


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AgriGuard PostgreSQL Tenant RLS Smoke",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Status: `{report['status']}`",
        f"- Smoke table: `{report['smoke_table']}`",
        f"- Session settings: `{', '.join(report['session_settings'])}`",
    ]
    if report.get("reason"):
        lines.append(f"- Reason: {report['reason']}")
    role = report.get("role")
    if role:
        lines.extend(
            [
                f"- Database: `{role['database_name']}`",
                f"- Role: `{role['role_name']}`",
                f"- Role bypasses RLS: `{role['is_superuser'] or role['has_bypassrls']}`",
            ]
        )
    lines.extend(["", "## Checks", "", "| Check | Expected IDs | Actual IDs | Result |", "|-------|--------------|------------|--------|"])
    for check in report["checks"]:
        result = "pass" if check["ok"] else "fail"
        lines.append(
            f"| `{check['name']}` | `{json.dumps(check['expected_ids'])}` | `{json.dumps(check['actual_ids'])}` | `{result}` |"
        )
    if not report["checks"]:
        lines.append("| n/a | `[]` | `[]` | `skipped` |")
    return "\n".join(lines) + "\n"


def _write_text(path: Path | None, text_value: str) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text_value, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify AgriGuard tenant RLS settings against a live PostgreSQL URL.")
    parser.add_argument(
        "--pg-url",
        nargs="?",
        const="",
        default=os.environ.get("DATABASE_URL", ""),
        help="PostgreSQL URL. Defaults to $DATABASE_URL; omit the value to force a skipped no-URL smoke.",
    )
    parser.add_argument("--json-out", type=Path, help="Optional JSON report path.")
    parser.add_argument("--markdown-out", type=Path, help="Optional Markdown report path.")
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Exit non-zero when no PostgreSQL URL is provided or RLS proof is blocked.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_live_smoke(args.pg_url)
    markdown = render_markdown(report)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_text(args.markdown_out, markdown)
    print(markdown, end="")

    if report["status"] == "pass":
        return 0
    if report["status"] in {"skipped", "blocked"} and not args.require_live:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
