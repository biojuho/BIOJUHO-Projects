#!/usr/bin/env python3
"""Fail-open local storage for pre-filter candidate decisions.

The store deliberately keeps only the text needed for a later human topic
label. It is not part of the product response path and never stores labels.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from runtime_paths import resolve_runtime_paths  # type: ignore[no-redef]

HERE = Path(__file__).resolve().parent
GETDAYTRENDS_DIR = HERE.parent
DEFAULT_DB_PATH = resolve_runtime_paths().filter_eval_shadow
DEFAULT_POLICY_PATH = GETDAYTRENDS_DIR / "content_filters.py"

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS filter_candidates (
    observed_at TEXT NOT NULL,
    source TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    title TEXT NOT NULL,
    extra_text TEXT NOT NULL,
    filter_verdict TEXT NOT NULL CHECK (filter_verdict IN ('allow', 'block')),
    filter_reason TEXT NOT NULL,
    policy_fingerprint TEXT NOT NULL,
    PRIMARY KEY (source, candidate_id, policy_fingerprint)
)
"""


def _one_line(value: object) -> str:
    """Keep TSV/SQLite text bounded to one normalized line."""
    return " ".join(str(value or "").split())


def fingerprint_file(path: Path = DEFAULT_POLICY_PATH) -> str:
    """Return the policy source fingerprint used for version separation."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FilterShadowStore:
    """Append-only, deduplicated candidate decisions in a local SQLite DB."""

    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        *,
        policy_path: Path = DEFAULT_POLICY_PATH,
        policy_fingerprint_value: str | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.policy_fingerprint: str | None = policy_fingerprint_value
        if self.policy_fingerprint is None:
            try:
                self.policy_fingerprint = fingerprint_file(policy_path)
            except OSError as exc:
                # 계측 초기화가 제품 모듈 import를 막아서는 안 된다. 정책 지문이
                # 없으면 서로 다른 판정을 구분할 수 없으므로 기록만 비활성화한다.
                logger.warning("filter shadow 정책 지문 생성 실패(기록 비활성): %s", exc)

    def record(
        self,
        *,
        source: str,
        candidate_id: str,
        title: str,
        extra_text: str = "",
        filter_verdict: str,
        filter_reason: str = "",
        observed_at: datetime | None = None,
    ) -> bool:
        """Record one decision; return False on duplicates or any local failure.

        All errors are contained here so measurement cannot stop collection.
        """
        try:
            if not self.policy_fingerprint:
                raise ValueError("policy_fingerprint가 없어 기록할 수 없음")
            source_value = _one_line(source)
            candidate_value = _one_line(candidate_id)
            title_value = _one_line(title)
            verdict_value = _one_line(filter_verdict)
            if not source_value or not candidate_value or not title_value:
                raise ValueError("source, candidate_id and title are required")
            if verdict_value not in {"allow", "block"}:
                raise ValueError(f"invalid filter verdict: {verdict_value!r}")

            timestamp = observed_at or datetime.now(UTC)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            timestamp = timestamp.astimezone(UTC)

            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.db_path, timeout=2.0) as conn:
                conn.execute(SCHEMA)
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO filter_candidates (
                        observed_at, source, candidate_id, title, extra_text,
                        filter_verdict, filter_reason, policy_fingerprint
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        timestamp.isoformat(),
                        source_value,
                        candidate_value,
                        title_value,
                        _one_line(extra_text),
                        verdict_value,
                        _one_line(filter_reason),
                        self.policy_fingerprint,
                    ),
                )
                return cursor.rowcount == 1
        except (OSError, sqlite3.Error, ValueError) as exc:
            logger.warning("filter shadow 기록 실패(제품 수집은 계속): %s", exc)
            return False


def record_filter_candidate_fail_open(store: object | None, **candidate: object) -> bool:
    """Call an injected shadow store without letting it affect product flow."""
    if store is None:
        return False
    try:
        record = getattr(store, "record")
        return bool(record(**candidate))
    except Exception as exc:  # injected/local instrumentation must never escape
        logger.warning("filter shadow 호출 실패(제품 수집은 계속): %s", exc)
        return False


__all__ = [
    "DEFAULT_DB_PATH",
    "DEFAULT_POLICY_PATH",
    "FilterShadowStore",
    "SCHEMA",
    "fingerprint_file",
    "record_filter_candidate_fail_open",
]
