"""shared.llm.stats - Cost tracking with persistent SQLite storage and CSV export."""

from __future__ import annotations

import csv
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import MODEL_COSTS
from .models import CostRecord, TaskTier

log = logging.getLogger("shared.llm")

_DATA_DIR = Path(__file__).resolve().parents[2] / "shared" / "llm" / "data"
_DB_PATH = _DATA_DIR / "llm_costs.db"
_CSV_DIR = _DATA_DIR / "logs"


def _ensure_dirs() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _CSV_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class UsageStats:
    """Aggregated usage statistics."""

    total_calls: int = 0
    total_errors: int = 0
    total_cost_usd: float = 0.0
    calls_by_backend: dict[str, int] = field(default_factory=dict)
    calls_by_tier: dict[str, int] = field(default_factory=dict)
    cost_by_backend: dict[str, float] = field(default_factory=dict)
    cost_by_model: dict[str, float] = field(default_factory=dict)
    tokens_by_backend: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return round((self.total_calls - self.total_errors) / self.total_calls * 100, 1)


class CostTracker:
    """Thread-safe cost tracking with SQLite persistence and daily CSV export."""

    def __init__(self, persist: bool = True) -> None:
        self._records: list[CostRecord] = []
        self._lock = threading.Lock()
        self._persist = persist
        self._db: sqlite3.Connection | None = None
        if persist:
            self._init_db()

    def _init_db(self) -> None:
        try:
            _ensure_dirs()
            self._db = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
            self._db.execute("""
                CREATE TABLE IF NOT EXISTS llm_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    backend TEXT NOT NULL,
                    model TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0.0,
                    success INTEGER DEFAULT 1,
                    error TEXT DEFAULT '',
                    project TEXT DEFAULT ''
                )
            """)
            self._db.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_calls_timestamp
                ON llm_calls(timestamp)
            """)
            self._db.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_calls_backend
                ON llm_calls(backend)
            """)
            self._db.commit()
        except Exception as e:
            log.warning("Failed to init cost DB: %s (falling back to in-memory)", e)
            self._db = None

    def record(
        self,
        backend: str,
        model: str,
        tier: TaskTier,
        input_tokens: int = 0,
        output_tokens: int = 0,
        success: bool = True,
        error: str = "",
        project: str = "",
    ) -> CostRecord:
        """Record a single LLM call with persistence."""
        cost_per_m = MODEL_COSTS.get(model, (0.0, 0.0))
        cost = (input_tokens * cost_per_m[0] + output_tokens * cost_per_m[1]) / 1_000_000

        rec = CostRecord(
            timestamp=datetime.now(timezone.utc),
            backend=backend,
            model=model,
            tier=tier,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            success=success,
            error=error,
        )
        with self._lock:
            self._records.append(rec)

        if self._persist and self._db is not None:
            self._persist_record(rec, project)

        return rec

    def _persist_record(self, rec: CostRecord, project: str) -> None:
        try:
            self._db.execute(  # type: ignore[union-attr]
                """INSERT INTO llm_calls
                   (timestamp, backend, model, tier, input_tokens, output_tokens,
                    cost_usd, success, error, project)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rec.timestamp.isoformat(),
                    rec.backend,
                    rec.model,
                    rec.tier.value,
                    rec.input_tokens,
                    rec.output_tokens,
                    rec.cost_usd,
                    1 if rec.success else 0,
                    rec.error,
                    project,
                ),
            )
            self._db.commit()  # type: ignore[union-attr]
        except Exception as e:
            log.warning("Failed to persist cost record: %s", e)

    def get_stats(self) -> UsageStats:
        """Compute aggregated stats from all records."""
        with self._lock:
            records = list(self._records)

        stats = UsageStats()
        for r in records:
            stats.total_calls += 1
            if not r.success:
                stats.total_errors += 1
            stats.total_cost_usd += r.cost_usd
            stats.calls_by_backend[r.backend] = stats.calls_by_backend.get(r.backend, 0) + 1
            stats.calls_by_tier[r.tier.value] = stats.calls_by_tier.get(r.tier.value, 0) + 1
            stats.cost_by_backend[r.backend] = stats.cost_by_backend.get(r.backend, 0) + r.cost_usd
            stats.cost_by_model[r.model] = stats.cost_by_model.get(r.model, 0) + r.cost_usd
            if r.backend not in stats.tokens_by_backend:
                stats.tokens_by_backend[r.backend] = {"input": 0, "output": 0}
            stats.tokens_by_backend[r.backend]["input"] += r.input_tokens
            stats.tokens_by_backend[r.backend]["output"] += r.output_tokens

        stats.total_cost_usd = round(stats.total_cost_usd, 6)
        for k in stats.cost_by_backend:
            stats.cost_by_backend[k] = round(stats.cost_by_backend[k], 6)
        for k in stats.cost_by_model:
            stats.cost_by_model[k] = round(stats.cost_by_model[k], 6)
        return stats

    def get_daily_stats(self, days: int = 30) -> list[dict]:
        """Retrieve daily aggregated stats from SQLite."""
        if self._db is None:
            return []
        try:
            cursor = self._db.execute(
                """SELECT
                    DATE(timestamp) as day,
                    COUNT(*) as calls,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors,
                    SUM(cost_usd) as cost,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    backend
                FROM llm_calls
                WHERE timestamp >= datetime('now', ?)
                GROUP BY day, backend
                ORDER BY day DESC""",
                (f"-{days} days",),
            )
            return [
                {
                    "date": row[0],
                    "calls": row[1],
                    "errors": row[2],
                    "cost_usd": round(row[3], 6),
                    "input_tokens": row[4],
                    "output_tokens": row[5],
                    "backend": row[6],
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            log.warning("Failed to query daily stats: %s", e)
            return []

    def export_csv(self, days: int = 30) -> Path | None:
        """Export recent records to a daily CSV file."""
        if self._db is None:
            return None
        try:
            _ensure_dirs()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            csv_path = _CSV_DIR / f"llm_usage_{today}.csv"
            cursor = self._db.execute(
                """SELECT timestamp, backend, model, tier,
                          input_tokens, output_tokens, cost_usd,
                          success, error, project
                   FROM llm_calls
                   WHERE timestamp >= datetime('now', ?)
                   ORDER BY timestamp""",
                (f"-{days} days",),
            )
            rows = cursor.fetchall()
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "backend", "model", "tier",
                    "input_tokens", "output_tokens", "cost_usd",
                    "success", "error", "project",
                ])
                writer.writerows(rows)
            log.info("Exported %d records to %s", len(rows), csv_path)
            return csv_path
        except Exception as e:
            log.warning("Failed to export CSV: %s", e)
            return None

    def reset(self) -> None:
        """Clear in-memory records."""
        with self._lock:
            self._records.clear()

    def close(self) -> None:
        """Close the SQLite connection."""
        if self._db is not None:
            self._db.close()
            self._db = None
