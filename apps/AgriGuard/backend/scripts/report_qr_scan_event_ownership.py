from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import models
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

PRODUCT_OWNER_PATH = "product_id -> products.owner_id"
SENSOR_OWNER_PATH = "sensor_id -> sensor_devices.owner_id"
METADATA_OWNER_PATH = "metadata_json.owner_id"
UNRESOLVED_OWNER_PATH = "unresolved"
RLS_VISIBILITY_TENANT_OWNED = "tenant_owned"
RLS_VISIBILITY_GLOBAL_DIAGNOSTIC = "global_diagnostic"
RLS_VISIBILITY_BLOCKED = "blocked"
PUBLIC_DIAGNOSTIC_SOURCES = {"consumer_verify_page", "qr_reader"}
PUBLIC_DIAGNOSTIC_EVENT_TYPES = {"scan_failure", "scan_start", "scan_recovery"}
PUBLIC_DIAGNOSTIC_ERROR_CODES = {
    "",
    "camera_denied",
    "invalid_or_expired_qr",
    "invalid_qr",
    "manual_entry",
    "network_error",
    "permission_denied",
    "scan_blurred",
    "timeout",
}
PUBLIC_DIAGNOSTIC_TOKEN_STATUSES = {"", "missing", "unknown"}


def _is_postgres_url(database_url: str) -> bool:
    return database_url.startswith("postgresql://") or database_url.startswith("postgresql+")


def _build_session_factory(database_url: str, *, connect_timeout_seconds: int):
    connect_args: dict[str, Any] = {}
    if _is_postgres_url(database_url):
        connect_args["connect_timeout"] = connect_timeout_seconds
    engine = create_engine(database_url, connect_args=connect_args)
    return engine, sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _database_target(database_url: str) -> str:
    if "@" not in database_url or "://" not in database_url:
        return database_url
    scheme, suffix = database_url.split("://", 1)
    _, host_part = suffix.rsplit("@", 1)
    return f"{scheme}://***@{host_part}"


def _string_value(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _redact(value: object, *, prefix: int = 8, suffix: int = 4) -> str | None:
    normalized = _string_value(value)
    if normalized is None:
        return None
    if len(normalized) <= prefix + suffix + 3:
        return normalized
    return f"{normalized[:prefix]}...{normalized[-suffix:]}"


def _metadata(event: models.QRScanEvent) -> tuple[dict[str, Any], bool]:
    try:
        decoded = json.loads(event.metadata_json or "{}")
    except json.JSONDecodeError:
        return {}, True
    return (decoded, False) if isinstance(decoded, dict) else ({}, True)


def _sensor_id_from_event(event: models.QRScanEvent, metadata: dict[str, Any]) -> str | None:
    metadata_sensor_id = _string_value(metadata.get("sensor_id"))
    if metadata_sensor_id:
        return metadata_sensor_id
    if event.source == "mqtt_ingest":
        return _string_value(event.qr_value)
    return None


def _owner_maps(db: Session) -> tuple[dict[str, str], dict[str, str]]:
    product_owners = {
        product_id: owner_id
        for product_id, owner_id in db.query(models.Product.id, models.Product.owner_id).all()
        if _string_value(product_id) and _string_value(owner_id)
    }
    sensor_owners = {
        sensor_id: owner_id
        for sensor_id, owner_id in db.query(models.SensorDevice.sensor_id, models.SensorDevice.owner_id).all()
        if _string_value(sensor_id) and _string_value(owner_id)
    }
    return product_owners, sensor_owners


def _candidate_owners(
    event: models.QRScanEvent,
    metadata: dict[str, Any],
    *,
    product_owners: dict[str, str],
    sensor_owners: dict[str, str],
) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []

    product_id = _string_value(event.product_id)
    if product_id and product_id in product_owners:
        candidates.append({"path": PRODUCT_OWNER_PATH, "owner_id": product_owners[product_id], "key": product_id})

    sensor_id = _sensor_id_from_event(event, metadata)
    if sensor_id and sensor_id in sensor_owners:
        candidates.append({"path": SENSOR_OWNER_PATH, "owner_id": sensor_owners[sensor_id], "key": sensor_id})

    metadata_owner = _string_value(metadata.get("owner_id"))
    if metadata_owner:
        candidates.append({"path": METADATA_OWNER_PATH, "owner_id": metadata_owner, "key": "owner_id"})

    return candidates


def _is_public_diagnostic_event(event: models.QRScanEvent, metadata: dict[str, Any]) -> bool:
    source = _string_value(event.source) or ""
    event_type = _string_value(event.event_type) or ""
    error_code = (_string_value(event.error_code) or "").lower()
    token_status = (_string_value(metadata.get("token_status")) or "").lower()
    has_object_pointer = bool(_string_value(event.product_id) or _sensor_id_from_event(event, metadata))

    return (
        source in PUBLIC_DIAGNOSTIC_SOURCES
        and event_type in PUBLIC_DIAGNOSTIC_EVENT_TYPES
        and not has_object_pointer
        and error_code in PUBLIC_DIAGNOSTIC_ERROR_CODES
        and token_status in PUBLIC_DIAGNOSTIC_TOKEN_STATUSES
    )


def _rls_visibility(
    *,
    status: str,
    invalid_metadata: bool,
    event: models.QRScanEvent,
    metadata: dict[str, Any],
) -> str:
    if invalid_metadata or status == "conflict":
        return RLS_VISIBILITY_BLOCKED
    if status == "owned":
        return RLS_VISIBILITY_TENANT_OWNED
    if _is_public_diagnostic_event(event, metadata):
        return RLS_VISIBILITY_GLOBAL_DIAGNOSTIC
    return RLS_VISIBILITY_BLOCKED


def classify_qr_scan_event(
    event: models.QRScanEvent,
    *,
    product_owners: dict[str, str],
    sensor_owners: dict[str, str],
) -> dict[str, Any]:
    metadata, invalid_metadata = _metadata(event)
    candidates = _candidate_owners(
        event,
        metadata,
        product_owners=product_owners,
        sensor_owners=sensor_owners,
    )
    candidate_owner_ids = sorted({candidate["owner_id"] for candidate in candidates})
    selected = candidates[0] if candidates else None
    conflict = len(candidate_owner_ids) > 1
    status = "unresolved" if selected is None else "conflict" if conflict else "owned"
    rls_visibility = _rls_visibility(
        status=status,
        invalid_metadata=invalid_metadata,
        event=event,
        metadata=metadata,
    )

    return {
        "event_id": event.id,
        "source": event.source,
        "event_type": event.event_type,
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        "product_id": event.product_id,
        "qr_value_preview": _redact(event.qr_value),
        "metadata_sensor_id": _string_value(metadata.get("sensor_id")),
        "owner_id": selected["owner_id"] if selected else None,
        "owner_path": selected["path"] if selected else UNRESOLVED_OWNER_PATH,
        "candidate_owners": candidates,
        "candidate_owner_ids": candidate_owner_ids,
        "status": status,
        "rls_visibility": rls_visibility,
        "invalid_metadata": invalid_metadata,
        "requires_review": rls_visibility == RLS_VISIBILITY_BLOCKED,
    }


def _event_query(db: Session, *, max_events: int | None):
    query = db.query(models.QRScanEvent).order_by(models.QRScanEvent.occurred_at.desc(), models.QRScanEvent.id.asc())
    if max_events is not None:
        query = query.limit(max_events)
    return query.all()


def build_qr_scan_event_ownership_report(
    db: Session,
    *,
    database_url: str | None = None,
    sample_limit: int = 20,
    max_events: int | None = None,
) -> dict[str, Any]:
    product_owners, sensor_owners = _owner_maps(db)
    events = _event_query(db, max_events=max_events)
    classifications = [
        classify_qr_scan_event(event, product_owners=product_owners, sensor_owners=sensor_owners)
        for event in events
    ]

    status_counts = Counter(item["status"] for item in classifications)
    visibility_counts = Counter(item["rls_visibility"] for item in classifications)
    owner_path_counts = Counter(item["owner_path"] for item in classifications)
    source_counts = Counter(item["source"] for item in classifications)
    unresolved_source_counts = Counter(item["source"] for item in classifications if item["status"] == "unresolved")
    conflict_source_counts = Counter(item["source"] for item in classifications if item["status"] == "conflict")
    invalid_metadata_count = sum(1 for item in classifications if item["invalid_metadata"])
    blocked_event_count = visibility_counts[RLS_VISIBILITY_BLOCKED]
    global_diagnostic_event_count = visibility_counts[RLS_VISIBILITY_GLOBAL_DIAGNOSTIC]
    review_items = [item for item in classifications if item["requires_review"]][:sample_limit]
    blocked_for_rls = bool(blocked_event_count)

    return {
        "schema_version": 1,
        "generated_at": _now(),
        "database_target": _database_target(database_url) if database_url else None,
        "status": "warn" if blocked_for_rls else "pass",
        "blocked_for_qr_scan_events_rls": blocked_for_rls,
        "max_events": max_events,
        "sample_limit": sample_limit,
        "total_events": len(classifications),
        "owned_event_count": status_counts["owned"],
        "unresolved_event_count": status_counts["unresolved"],
        "conflict_event_count": status_counts["conflict"],
        "invalid_metadata_count": invalid_metadata_count,
        "global_diagnostic_event_count": global_diagnostic_event_count,
        "blocked_event_count": blocked_event_count,
        "rls_visibility_counts": dict(sorted(visibility_counts.items())),
        "owner_path_counts": dict(sorted(owner_path_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "unresolved_source_counts": dict(sorted(unresolved_source_counts.items())),
        "conflict_source_counts": dict(sorted(conflict_source_counts.items())),
        "review_items": review_items,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AgriGuard QR Scan Event Ownership Report",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Database target: `{report.get('database_target') or 'not recorded'}`",
        f"- Status: `{report['status']}`",
        f"- Blocks `qr_scan_events` RLS: `{report['blocked_for_qr_scan_events_rls']}`",
        f"- Total events inspected: `{report['total_events']}`",
        f"- Owned events: `{report['owned_event_count']}`",
        f"- Unresolved events: `{report['unresolved_event_count']}`",
        f"- Conflict events: `{report['conflict_event_count']}`",
        f"- Invalid metadata events: `{report['invalid_metadata_count']}`",
        f"- Global diagnostic events: `{report['global_diagnostic_event_count']}`",
        f"- Blocked events: `{report['blocked_event_count']}`",
        "",
        "## Owner Path Counts",
        "",
        "| Owner path | Count |",
        "|------------|------:|",
    ]
    for owner_path, count in report["owner_path_counts"].items():
        lines.append(f"| `{owner_path}` | {count} |")
    if not report["owner_path_counts"]:
        lines.append("| n/a | 0 |")

    lines.extend(
        [
            "",
            "## RLS Visibility Counts",
            "",
            "| Visibility | Count |",
            "|------------|------:|",
        ]
    )
    for visibility, count in report["rls_visibility_counts"].items():
        lines.append(f"| `{visibility}` | {count} |")
    if not report["rls_visibility_counts"]:
        lines.append("| n/a | 0 |")

    lines.extend(
        [
            "",
            "## Source Counts",
            "",
            "| Source | Count |",
            "|--------|------:|",
        ]
    )
    for source, count in report["source_counts"].items():
        lines.append(f"| `{source}` | {count} |")
    if not report["source_counts"]:
        lines.append("| n/a | 0 |")

    lines.extend(
        [
            "",
            "## Review Samples",
            "",
            "| Event | Source | Type | Visibility | Owner path | Owner | Reason |",
            "|-------|--------|------|------------|------------|-------|--------|",
        ]
    )
    for item in report["review_items"]:
        reasons = []
        if item["status"] == "unresolved":
            reasons.append("unresolved")
        if item["status"] == "conflict":
            reasons.append("owner_conflict")
        if item["invalid_metadata"]:
            reasons.append("invalid_metadata")
        lines.append(
            "| `{event_id}` | `{source}` | `{event_type}` | `{visibility}` | `{owner_path}` | `{owner_id}` | `{reason}` |".format(
                event_id=item["event_id"],
                source=item["source"],
                event_type=item["event_type"],
                visibility=item["rls_visibility"],
                owner_path=item["owner_path"],
                owner_id=item["owner_id"] or "",
                reason=", ".join(reasons),
            )
        )
    if not report["review_items"]:
        lines.append("| n/a | n/a | n/a | n/a | n/a | n/a | none |")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report tenant ownership coverage for AgriGuard qr_scan_events rows.")
    parser.add_argument(
        "--database-url",
        help="Database URL to inspect. Defaults to AgriGuard DATABASE_URL resolution after backend env loading.",
    )
    parser.add_argument(
        "--connect-timeout-seconds",
        type=int,
        default=5,
        help="PostgreSQL connect timeout when --database-url or DATABASE_URL points at PostgreSQL.",
    )
    parser.add_argument("--json-out", type=Path, help="Optional JSON report path.")
    parser.add_argument("--markdown-out", type=Path, help="Optional Markdown report path.")
    parser.add_argument("--sample-limit", type=int, default=20, help="Maximum unresolved/conflict samples to include.")
    parser.add_argument("--max-events", type=int, help="Optional cap for inspected events, newest first.")
    parser.add_argument("--fail-on-blocked", action="store_true", help="Exit non-zero if any event blocks qr_scan_events RLS.")
    parser.add_argument("--fail-on-unresolved", action="store_true", help="Exit non-zero if unresolved events are present.")
    parser.add_argument("--fail-on-conflict", action="store_true", help="Exit non-zero if conflicting owner candidates are present.")
    parser.add_argument("--fail-on-invalid-metadata", action="store_true", help="Exit non-zero if invalid metadata JSON is present.")
    return parser.parse_args()


def _write_text(path: Path | None, value: str) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_outputs(report: dict[str, Any], *, json_out: Path | None, markdown_out: Path | None) -> None:
    markdown = render_markdown(report)
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_text(markdown_out, markdown)
    print(markdown, end="")


def main() -> int:
    args = parse_args()
    database_url = args.database_url
    if not database_url:
        from database import get_database_url

        database_url = get_database_url()
    engine = None
    try:
        engine, SessionLocal = _build_session_factory(database_url, connect_timeout_seconds=args.connect_timeout_seconds)
        with SessionLocal() as db:
            report = build_qr_scan_event_ownership_report(
                db,
                database_url=database_url,
                sample_limit=args.sample_limit,
                max_events=args.max_events,
            )
        _write_outputs(report, json_out=args.json_out, markdown_out=args.markdown_out)
    except SQLAlchemyError as exc:
        detail = str(exc.__cause__ or exc).splitlines()[0]
        print(
            "QR scan event ownership report failed: database schema is not ready or query failed: "
            f"{detail}",
            file=sys.stderr,
        )
        return 2
    finally:
        if engine is not None:
            engine.dispose()

    if args.fail_on_blocked and report["blocked_event_count"]:
        return 1
    if args.fail_on_unresolved and report["unresolved_event_count"]:
        return 1
    if args.fail_on_conflict and report["conflict_event_count"]:
        return 1
    if args.fail_on_invalid_metadata and report["invalid_metadata_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
