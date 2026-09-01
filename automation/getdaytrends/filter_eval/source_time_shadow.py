#!/usr/bin/env python3
"""Add source publication time to new shadow rows without backfilling history.

``shadow_store.py`` is shared with an unfinished runtime-path change in this
worktree.  This small adapter keeps that file untouched: it adds one nullable-
by-contract text column to a concrete SQLite store, delegates the normal insert
to ``FilterShadowStore.record()``, and fills the timestamp only when that insert
created a new row.  Existing rows therefore remain byte-for-byte unchanged in
their original fields and receive only SQLite's empty-string column default.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .shadow_store import SCHEMA, record_filter_candidate_fail_open

logger = logging.getLogger(__name__)

SOURCE_PUBLISHED_AT_COLUMN = "source_published_at"
_ADD_SOURCE_PUBLISHED_AT = (
    f"ALTER TABLE filter_candidates ADD COLUMN {SOURCE_PUBLISHED_AT_COLUMN} TEXT NOT NULL DEFAULT ''"
)


def _one_line(value: object) -> str:
    return " ".join(str(value or "").split())


def _normalized_timestamp(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        timestamp = value if value.tzinfo else value.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC).isoformat()
    raw = _one_line(value)
    if not raw:
        return ""
    try:
        timestamp = datetime.fromisoformat(raw)
    except ValueError:
        return ""
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC).isoformat()


def _sqlite_store_identity(store: object) -> tuple[Path, str] | None:
    db_path = getattr(store, "db_path", None)
    policy_fingerprint = _one_line(getattr(store, "policy_fingerprint", ""))
    if db_path is None or not policy_fingerprint:
        return None
    try:
        return Path(db_path), policy_fingerprint
    except TypeError:
        return None


def _ensure_source_time_column(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path, timeout=2.0) as conn:
        conn.execute(SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(filter_candidates)")}
        if SOURCE_PUBLISHED_AT_COLUMN not in columns:
            conn.execute(_ADD_SOURCE_PUBLISHED_AT)


def ensure_source_time_column_fail_open(store: object | None) -> bool:
    """Ensure the additive column exists even when a source returns no rows."""
    if store is None:
        return False
    identity = _sqlite_store_identity(store)
    if identity is None:
        return False
    try:
        _ensure_source_time_column(identity[0])
        return True
    except (OSError, sqlite3.Error) as exc:
        logger.warning("source-time shadow 스키마 준비 실패(기본 기록은 계속): %s", exc)
        return False


def record_filter_candidate_with_source_time_fail_open(
    store: object | None,
    *,
    source_published_at: object = None,
    **candidate: object,
) -> bool:
    """Record one candidate and enrich only a newly inserted concrete row.

    Unknown timestamps are deliberately stored as ``""``.  Instrumentation
    failures never escape into collection, matching the base shadow contract.
    """
    if store is None:
        return False

    identity = _sqlite_store_identity(store)
    ensure_source_time_column_fail_open(store)

    inserted = bool(record_filter_candidate_fail_open(store, **candidate))
    timestamp = _normalized_timestamp(source_published_at)
    if not inserted or identity is None or not timestamp:
        return inserted

    db_path, policy_fingerprint = identity
    try:
        with sqlite3.connect(db_path, timeout=2.0) as conn:
            conn.execute(
                f"""
                UPDATE filter_candidates
                   SET {SOURCE_PUBLISHED_AT_COLUMN} = ?
                 WHERE source = ?
                   AND candidate_id = ?
                   AND policy_fingerprint = ?
                   AND {SOURCE_PUBLISHED_AT_COLUMN} = ''
                """,
                (
                    timestamp,
                    _one_line(candidate.get("source")),
                    _one_line(candidate.get("candidate_id")),
                    policy_fingerprint,
                ),
            )
    except (OSError, sqlite3.Error) as exc:
        logger.warning("source-time shadow 보강 실패(기본 기록은 유지): %s", exc)
    return inserted


__all__ = [
    "SOURCE_PUBLISHED_AT_COLUMN",
    "ensure_source_time_column_fail_open",
    "record_filter_candidate_with_source_time_fail_open",
]
