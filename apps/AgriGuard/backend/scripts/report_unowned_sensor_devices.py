from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import case, func, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import models  # noqa: E402  # must come after sys.path injection
from database import SessionLocal, get_database_url  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report or backfill AgriGuard sensor_devices rows without owner_id.",
    )
    parser.add_argument("--limit", type=int, default=25, help="Maximum sample rows to include in the report.")
    parser.add_argument("--json-out", type=Path, help="Optional path to write a machine-readable report.")
    parser.add_argument("--markdown-out", type=Path, help="Optional path to write a Markdown report.")
    parser.add_argument("--owner-id", help="Owner ID to assign when planning or applying a backfill.")
    parser.add_argument(
        "--sensor-id",
        action="append",
        default=[],
        help="Specific unowned sensor_id to backfill. Repeat for multiple sensors.",
    )
    parser.add_argument(
        "--all-unowned",
        action="store_true",
        help="Target every unowned sensor for backfill. Requires --apply to mutate data.",
    )
    parser.add_argument("--apply", action="store_true", help="Apply the owner backfill. Omit for dry-run only.")
    parser.add_argument(
        "--fail-on-unowned",
        action="store_true",
        help="Exit non-zero if any unowned sensor remains after optional backfill.",
    )
    return parser.parse_args()


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _sensor_summary(sensor: models.SensorDevice) -> dict[str, Any]:
    return {
        "sensor_id": sensor.sensor_id,
        "label": sensor.label,
        "zone": sensor.zone,
        "expected_interval_minutes": sensor.expected_interval_minutes,
        "is_active": bool(sensor.is_active),
        "registered_at": _isoformat(sensor.registered_at),
        "last_seen_at": _isoformat(sensor.last_seen_at),
        "updated_at": _isoformat(sensor.updated_at),
    }


def _normalize_owner_id(owner_id: str | None) -> str:
    normalized = str(owner_id or "").strip()
    if not normalized:
        raise ValueError("--owner-id is required and must not be blank for a backfill plan.")
    return normalized


def _normalize_sensor_ids(sensor_ids: list[str] | tuple[str, ...]) -> list[str]:
    normalized_ids = []
    seen = set()
    for sensor_id in sensor_ids:
        normalized = str(sensor_id or "").strip()
        if not normalized:
            raise ValueError("--sensor-id values must not be blank.")
        if normalized not in seen:
            normalized_ids.append(normalized)
            seen.add(normalized)
    return normalized_ids


def _database_target() -> str:
    database_url = os.environ.get("DATABASE_URL") or get_database_url()
    if "@" not in database_url:
        return database_url
    scheme, suffix = database_url.split("://", 1)
    _, host_part = suffix.rsplit("@", 1)
    return f"{scheme}://***@{host_part}"


def build_unowned_sensor_report(db: Session, *, limit: int = 25) -> dict[str, Any]:
    total = (
        db.query(func.count(models.SensorDevice.sensor_id))
        .filter(models.SensorDevice.owner_id.is_(None))
        .scalar()
        or 0
    )
    active_count = (
        db.query(func.count(models.SensorDevice.sensor_id))
        .filter(models.SensorDevice.owner_id.is_(None), models.SensorDevice.is_active.is_(True))
        .scalar()
        or 0
    )
    zone_rows = (
        db.query(
            func.coalesce(models.SensorDevice.zone, "Unassigned").label("zone"),
            func.count(models.SensorDevice.sensor_id).label("count"),
            func.sum(case((models.SensorDevice.is_active.is_(True), 1), else_=0)).label("active_count"),
        )
        .filter(models.SensorDevice.owner_id.is_(None))
        .group_by(func.coalesce(models.SensorDevice.zone, "Unassigned"))
        .order_by(func.count(models.SensorDevice.sensor_id).desc(), func.coalesce(models.SensorDevice.zone, "Unassigned"))
        .all()
    )
    sensors = (
        db.query(models.SensorDevice)
        .filter(models.SensorDevice.owner_id.is_(None))
        .order_by(models.SensorDevice.is_active.desc(), models.SensorDevice.updated_at.desc(), models.SensorDevice.sensor_id.asc())
        .limit(max(0, limit))
        .all()
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "database_target": _database_target(),
        "status": "pass" if total == 0 else "warn",
        "unowned_sensor_count": total,
        "active_unowned_sensor_count": active_count,
        "disabled_unowned_sensor_count": total - active_count,
        "sample_limit": max(0, limit),
        "zone_counts": [
            {
                "zone": row.zone,
                "count": int(row.count or 0),
                "active_count": int(row.active_count or 0),
            }
            for row in zone_rows
        ],
        "items": [_sensor_summary(sensor) for sensor in sensors],
    }


def build_backfill_plan(
    db: Session,
    *,
    owner_id: str,
    sensor_ids: list[str] | tuple[str, ...] = (),
    all_unowned: bool = False,
) -> dict[str, Any]:
    normalized_owner_id = _normalize_owner_id(owner_id)
    normalized_sensor_ids = _normalize_sensor_ids(list(sensor_ids))
    if all_unowned and normalized_sensor_ids:
        raise ValueError("--all-unowned cannot be combined with --sensor-id.")
    if not all_unowned and not normalized_sensor_ids:
        raise ValueError("Backfill requires --all-unowned or at least one --sensor-id.")

    query = db.query(models.SensorDevice).filter(models.SensorDevice.owner_id.is_(None))
    if normalized_sensor_ids:
        query = query.filter(models.SensorDevice.sensor_id.in_(normalized_sensor_ids))
    target_sensors = query.order_by(models.SensorDevice.sensor_id.asc()).all()
    target_ids = [sensor.sensor_id for sensor in target_sensors]

    missing_or_owned_ids = []
    if normalized_sensor_ids:
        target_id_set = set(target_ids)
        missing_or_owned_ids = [sensor_id for sensor_id in normalized_sensor_ids if sensor_id not in target_id_set]
        if missing_or_owned_ids:
            raise ValueError(
                "Backfill targets must exist and be unowned before apply: " + ", ".join(missing_or_owned_ids)
            )

    return {
        "owner_id": normalized_owner_id,
        "target_mode": "all_unowned" if all_unowned else "explicit_sensor_ids",
        "target_count": len(target_ids),
        "target_sensor_ids": target_ids,
    }


def apply_owner_backfill(
    db: Session,
    *,
    owner_id: str,
    sensor_ids: list[str] | tuple[str, ...] = (),
    all_unowned: bool = False,
) -> dict[str, Any]:
    plan = build_backfill_plan(db, owner_id=owner_id, sensor_ids=sensor_ids, all_unowned=all_unowned)
    if plan["target_count"] == 0:
        plan.update({"applied": True, "updated_count": 0, "applied_at": datetime.now(UTC).isoformat()})
        return plan

    applied_at = datetime.now(UTC)
    result = db.execute(
        update(models.SensorDevice)
        .where(
            models.SensorDevice.owner_id.is_(None),
            models.SensorDevice.sensor_id.in_(plan["target_sensor_ids"]),
        )
        .values(owner_id=plan["owner_id"], updated_at=applied_at)
    )
    db.commit()
    plan.update(
        {
            "applied": True,
            "updated_count": int(result.rowcount or 0),
            "applied_at": applied_at.isoformat(),
        }
    )
    return plan


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AgriGuard Unowned Sensor Devices Report",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Database target: `{report['database_target']}`",
        f"- Status: {report['status']}",
        f"- Unowned sensors: {report['unowned_sensor_count']}",
        f"- Active unowned sensors: {report['active_unowned_sensor_count']}",
        f"- Disabled unowned sensors: {report['disabled_unowned_sensor_count']}",
    ]

    backfill = report.get("backfill")
    if backfill:
        lines.extend(
            [
                "",
                "## Backfill",
                "",
                f"- Mode: {backfill.get('target_mode')}",
                f"- Owner ID: `{backfill.get('owner_id')}`",
                f"- Applied: {backfill.get('applied', False)}",
                f"- Target count: {backfill.get('target_count', 0)}",
                f"- Updated count: {backfill.get('updated_count', 0)}",
            ]
        )

    lines.extend(["", "## Zone Counts", "", "| Zone | Count | Active |", "|------|-------|--------|"])
    for row in report["zone_counts"]:
        lines.append(f"| {row['zone']} | {row['count']} | {row['active_count']} |")

    lines.extend(
        [
            "",
            "## Sample Sensors",
            "",
            "| Sensor ID | State | Zone | Last seen |",
            "|-----------|-------|------|-----------|",
        ]
    )
    for sensor in report["items"]:
        state = "active" if sensor["is_active"] else "disabled"
        lines.append(
            f"| `{sensor['sensor_id']}` | {state} | {sensor['zone'] or 'Unassigned'} | {sensor['last_seen_at'] or 'Never'} |"
        )

    return "\n".join(lines) + "\n"


def _write_outputs(report: dict[str, Any], *, json_out: Path | None, markdown_out: Path | None) -> None:
    markdown = render_markdown(report)
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if markdown_out:
        markdown_out.parent.mkdir(parents=True, exist_ok=True)
        markdown_out.write_text(markdown, encoding="utf-8")
    print(markdown, end="")


def main() -> int:
    args = parse_args()
    try:
        with SessionLocal() as db:
            backfill = None
            if args.owner_id and (args.sensor_id or args.all_unowned):
                if args.apply:
                    backfill = apply_owner_backfill(
                        db,
                        owner_id=args.owner_id,
                        sensor_ids=args.sensor_id,
                        all_unowned=args.all_unowned,
                    )
                else:
                    backfill = build_backfill_plan(
                        db,
                        owner_id=args.owner_id,
                        sensor_ids=args.sensor_id,
                        all_unowned=args.all_unowned,
                    )
                    backfill["applied"] = False
                    backfill["updated_count"] = 0

            report = build_unowned_sensor_report(db, limit=args.limit)
            if backfill:
                report["backfill"] = backfill

        _write_outputs(report, json_out=args.json_out, markdown_out=args.markdown_out)
        if args.fail_on_unowned and report["unowned_sensor_count"] > 0:
            return 2
        return 0
    except ValueError as exc:
        print(f"Unowned sensor report failed: {exc}", file=sys.stderr)
        return 2
    except SQLAlchemyError as exc:
        detail = str(exc.__cause__ or exc).splitlines()[0]
        print(
            "Unowned sensor report failed: database schema is not ready or query failed: "
            f"{detail}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
