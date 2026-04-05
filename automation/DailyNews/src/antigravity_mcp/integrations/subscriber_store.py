"""Subscriber management for the Adaptive Newsletter Funnel.

Backed by SQLite (same pipeline_state.db) for dev, with a clear migration
path to Supabase PostgreSQL when subscriber count warrants it.

Schema tables:
  - subscribers: email list with category preferences & engagement scores
  - newsletter_events: delivery/open/click tracking for feedback loop
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from antigravity_mcp.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain Model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Subscriber:
    """Newsletter subscriber domain model."""

    id: str
    email: str
    name: str = ""
    categories: list[str] = field(default_factory=list)
    status: str = "active"  # active | paused | unsubscribed
    source: str = "landing_page"  # landing_page | x_cta | manual
    engagement_score: float = 0.0  # 0.0~1.0 rolling EMA
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class SubscriberStore:
    """CRUD operations on the subscribers & newsletter_events tables.

    Uses the same thread-safe SQLite pattern as PipelineStateStore.
    """

    def __init__(self, *, db_path: Path | None = None) -> None:
        settings = get_settings()
        self._db_path = db_path or (settings.data_dir / "newsletter.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    # ── Connection management ─────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:  # noqa: BLE001
                    pass
                self._conn = None

    def __enter__(self) -> SubscriberStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ── Schema ────────────────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS subscribers (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    categories_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'active',
                    source TEXT NOT NULL DEFAULT 'landing_page',
                    engagement_score REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS newsletter_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscriber_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    newsletter_id TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (subscriber_id) REFERENCES subscribers(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_subscribers_status ON subscribers(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_subscriber ON newsletter_events(subscriber_id, created_at DESC)"
            )

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_categories_json(
        raw_categories: str | None,
        *,
        subscriber_id: str = "",
        email: str = "",
    ) -> tuple[list[str], bool]:
        import json

        if raw_categories in (None, ""):
            return [], True

        try:
            decoded = json.loads(raw_categories)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "Malformed subscriber categories_json for %s (%s): %s",
                email or "unknown-email",
                subscriber_id or "unknown-id",
                exc,
            )
            return [], False

        if decoded is None:
            return [], True

        if isinstance(decoded, str):
            decoded = [decoded]
        elif not isinstance(decoded, list):
            logger.warning(
                "Unexpected subscriber categories_json shape for %s (%s): %s",
                email or "unknown-email",
                subscriber_id or "unknown-id",
                type(decoded).__name__,
            )
            return [], False

        categories: list[str] = []
        for item in decoded:
            if not isinstance(item, str):
                logger.warning(
                    "Ignoring non-string category for %s (%s): %r",
                    email or "unknown-email",
                    subscriber_id or "unknown-id",
                    item,
                )
                continue
            normalized = item.strip()
            if normalized:
                categories.append(normalized)

        return categories, True

    @classmethod
    def _row_to_subscriber(
        cls,
        row: sqlite3.Row,
        *,
        strict_categories: bool = False,
    ) -> Subscriber | None:
        categories, is_valid = cls._parse_categories_json(
            row["categories_json"],
            subscriber_id=row["id"],
            email=row["email"],
        )
        if strict_categories and not is_valid:
            return None

        return Subscriber(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            categories=categories,
            status=row["status"],
            source=row["source"],
            engagement_score=row["engagement_score"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()

    # ── CRUD ──────────────────────────────────────────────────────────────

    def add_subscriber(
        self,
        email: str,
        *,
        name: str = "",
        categories: list[str] | None = None,
        source: str = "landing_page",
    ) -> Subscriber | None:
        """Add a new subscriber.  Returns None if email already exists."""
        import json

        subscriber_id = str(uuid.uuid4())
        now = self._now_iso()
        cats_json = json.dumps(categories or [])

        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO subscribers (id, email, name, categories_json, status, source, engagement_score, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'active', ?, 0.0, ?, ?)
                    """,
                    (subscriber_id, email.strip().lower(), name, cats_json, source, now, now),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                logger.debug("Subscriber %s already exists", email)
                return None

        logger.info("Added subscriber %s (%s) from %s", email, subscriber_id[:8], source)
        return Subscriber(
            id=subscriber_id,
            email=email.strip().lower(),
            name=name,
            categories=categories or [],
            source=source,
            created_at=now,
            updated_at=now,
        )

    def get_subscriber_by_email(self, email: str) -> Subscriber | None:
        """Lookup a subscriber by email."""
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM subscribers WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
        return self._row_to_subscriber(row) if row else None

    def get_active_subscribers(
        self,
        *,
        categories: list[str] | None = None,
        min_engagement: float = 0.0,
    ) -> list[Subscriber]:
        """Fetch active subscribers, optionally filtered."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM subscribers WHERE status = 'active' AND engagement_score >= ?",
            (min_engagement,),
        ).fetchall()

        subscribers = []
        for row in rows:
            subscriber = self._row_to_subscriber(row, strict_categories=True)
            if subscriber is not None:
                subscribers.append(subscriber)

        if categories:
            cat_set = set(categories)
            subscribers = [
                s for s in subscribers
                if not s.categories or cat_set.intersection(s.categories)
            ]

        return subscribers

    def update_categories(self, email: str, categories: list[str]) -> bool:
        """Update subscriber's preferred categories."""
        import json

        now = self._now_iso()
        with self._lock:
            conn = self._connect()
            cursor = conn.execute(
                "UPDATE subscribers SET categories_json = ?, updated_at = ? WHERE email = ?",
                (json.dumps(categories), now, email.strip().lower()),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_engagement_score(
        self,
        subscriber_id: str,
        *,
        opened: bool = False,
        clicked: bool = False,
    ) -> None:
        """Update rolling engagement score with Exponential Moving Average.

        Formula: new_score = 0.7 * old_score + 0.3 * event_weight
        - clicked: weight = 1.0
        - opened (not clicked): weight = 0.5
        - delivered only: weight = 0.0
        """
        event_weight = 1.0 if clicked else (0.5 if opened else 0.0)
        now = self._now_iso()

        with self._lock:
            conn = self._connect()
            row = conn.execute(
                "SELECT engagement_score FROM subscribers WHERE id = ?",
                (subscriber_id,),
            ).fetchone()
            if row is None:
                return

            old_score = float(row["engagement_score"])
            new_score = round(0.7 * old_score + 0.3 * event_weight, 4)

            conn.execute(
                "UPDATE subscribers SET engagement_score = ?, updated_at = ? WHERE id = ?",
                (new_score, now, subscriber_id),
            )
            conn.commit()

    def unsubscribe(self, email: str) -> bool:
        """Mark subscriber as unsubscribed."""
        now = self._now_iso()
        with self._lock:
            conn = self._connect()
            cursor = conn.execute(
                "UPDATE subscribers SET status = 'unsubscribed', updated_at = ? WHERE email = ?",
                (now, email.strip().lower()),
            )
            conn.commit()
            return cursor.rowcount > 0

    def pause(self, email: str) -> bool:
        """Temporarily pause a subscription."""
        now = self._now_iso()
        with self._lock:
            conn = self._connect()
            cursor = conn.execute(
                "UPDATE subscribers SET status = 'paused', updated_at = ? WHERE email = ?",
                (now, email.strip().lower()),
            )
            conn.commit()
            return cursor.rowcount > 0

    def reactivate(self, email: str) -> bool:
        """Reactivate a paused/unsubscribed subscriber."""
        now = self._now_iso()
        with self._lock:
            conn = self._connect()
            cursor = conn.execute(
                "UPDATE subscribers SET status = 'active', updated_at = ? WHERE email = ?",
                (now, email.strip().lower()),
            )
            conn.commit()
            return cursor.rowcount > 0

    # ── Events ────────────────────────────────────────────────────────────

    def record_event(
        self,
        subscriber_id: str,
        event_type: str,
        newsletter_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a newsletter delivery/engagement event."""
        import json

        now = self._now_iso()
        with self._lock:
            conn = self._connect()
            conn.execute(
                """
                INSERT INTO newsletter_events (subscriber_id, event_type, newsletter_id, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (subscriber_id, event_type, newsletter_id, json.dumps(metadata or {}), now),
            )
            conn.commit()

    # ── Stats ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Aggregate statistics for dashboard display."""
        conn = self._connect()

        total = conn.execute("SELECT COUNT(*) as c FROM subscribers").fetchone()["c"]
        active = conn.execute("SELECT COUNT(*) as c FROM subscribers WHERE status = 'active'").fetchone()["c"]
        avg_eng = conn.execute("SELECT AVG(engagement_score) as avg FROM subscribers WHERE status = 'active'").fetchone()["avg"] or 0.0

        # Category distribution
        rows = conn.execute(
            "SELECT id, email, categories_json FROM subscribers WHERE status = 'active'"
        ).fetchall()
        cat_dist: dict[str, int] = {}
        for row in rows:
            categories, is_valid = self._parse_categories_json(
                row["categories_json"],
                subscriber_id=row["id"],
                email=row["email"],
            )
            if not is_valid:
                continue
            for cat in categories:
                cat_dist[cat] = cat_dist.get(cat, 0) + 1

        # Recent growth (last 7 days)
        growth_rows = conn.execute(
            """
            SELECT DATE(created_at) as d, COUNT(*) as c
            FROM subscribers
            WHERE created_at >= DATE('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY d
            """
        ).fetchall()
        recent_growth = {r["d"]: r["c"] for r in growth_rows}

        return {
            "total": total,
            "active": active,
            "avg_engagement": round(avg_eng, 4),
            "category_distribution": cat_dist,
            "recent_growth": recent_growth,
        }

    def get_subscriber_count(self) -> int:
        """Quick count of active subscribers."""
        conn = self._connect()
        return conn.execute("SELECT COUNT(*) as c FROM subscribers WHERE status = 'active'").fetchone()["c"]
