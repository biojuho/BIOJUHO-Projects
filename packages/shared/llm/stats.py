"""shared.llm.stats - Cost tracking with persistent SQLite storage and CSV export."""

from __future__ import annotations

import csv
import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import MetaData, Table, Column, Integer, String, Float, select, func, text, case

from .config import MODEL_COSTS
from .models import CostRecord, TaskTier
from shared.db.engine import get_sqlalchemy_engine

log = logging.getLogger("shared.llm")

_DATA_DIR = Path(__file__).resolve().parents[2] / "shared" / "llm" / "data"
_CSV_DIR = _DATA_DIR / "logs"

metadata = MetaData()
llm_calls_table = Table(
    "llm_calls",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("timestamp", String, nullable=False, index=True),
    Column("backend", String, nullable=False, index=True),
    Column("model", String, nullable=False),
    Column("tier", String, nullable=False),
    Column("input_tokens", Integer, default=0),
    Column("output_tokens", Integer, default=0),
    Column("cost_usd", Float, default=0.0),
    Column("success", Integer, default=1),
    Column("error", String, default=""),
    Column("project", String, default=""),
)


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
    """Thread-safe cost tracking with SQLAlchemy persistence and daily CSV export."""

    _MAX_RECORDS: int = 10_000

    def __init__(self, persist: bool = True) -> None:
        self._records: list[CostRecord] = []
        self._lock = threading.Lock()
        self._persist = persist
        self._engine = None
        if persist:
            self._init_db()

    def _init_db(self) -> None:
        try:
            _ensure_dirs()
            # Utilizes shared factory which dynamically pivots to PostgreSQL if DATABASE_URL is set
            self._engine = get_sqlalchemy_engine("llm_costs")
            metadata.create_all(self._engine)
        except Exception as e:
            log.warning("Failed to init cost DB: %s (falling back to in-memory)", e)
            self._engine = None

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
            timestamp=datetime.now(UTC),
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
            if len(self._records) >= self._MAX_RECORDS:
                self._records = self._records[-(self._MAX_RECORDS // 2):]
            self._records.append(rec)
            
            if self._persist and self._engine is not None:
                self._persist_record(rec, project)

        return rec

    def _persist_record(self, rec: CostRecord, project: str) -> None:
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    llm_calls_table.insert().values(
                        timestamp=rec.timestamp.isoformat(),
                        backend=rec.backend,
                        model=rec.model,
                        tier=rec.tier.value,
                        input_tokens=rec.input_tokens,
                        output_tokens=rec.output_tokens,
                        cost_usd=rec.cost_usd,
                        success=1 if rec.success else 0,
                        error=rec.error,
                        project=project,
                    )
                )
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
        """Retrieve daily aggregated stats from DB (Safe for Postgres and SQLite)."""
        if self._engine is None:
            return []
        try:
            cutoff_date = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            
            # Using substr(1, 10) to parse YYYY-MM-DD from ISO-8601 strings globally
            day_col = func.substr(llm_calls_table.c.timestamp, 1, 10).label("day")
            query = (
                select(
                    day_col,
                    func.count().label("calls"),
                    func.sum(case((llm_calls_table.c.success == 0, 1), else_=0)).label("errors"),
                    func.sum(llm_calls_table.c.cost_usd).label("cost_usd"),
                    func.sum(llm_calls_table.c.input_tokens).label("input_tokens"),
                    func.sum(llm_calls_table.c.output_tokens).label("output_tokens"),
                    llm_calls_table.c.backend
                )
                .where(llm_calls_table.c.timestamp >= cutoff_date)
                .group_by("day", llm_calls_table.c.backend)
                .order_by(text("day DESC"))
            )

            with self._engine.connect() as conn:
                rows = conn.execute(query).fetchall()
                
            return [
                {
                    "date": row[0],
                    "calls": row[1],
                    "errors": row[2] or 0,
                    "cost_usd": round(row[3] or 0.0, 6),
                    "input_tokens": row[4] or 0,
                    "output_tokens": row[5] or 0,
                    "backend": row[6],
                }
                for row in rows
            ]
        except Exception as e:
            log.warning("Failed to query daily stats: %s", e)
            return []

    def get_today_cost(self) -> float:
        """Return total USD cost spent today (UTC)."""
        if self._engine is None:
            return 0.0
        try:
            today_prefix = datetime.now(UTC).strftime("%Y-%m-%d")
            query = select(
                func.coalesce(func.sum(llm_calls_table.c.cost_usd), 0)
            ).where(func.substr(llm_calls_table.c.timestamp, 1, 10) == today_prefix)
            
            with self._engine.connect() as conn:
                return round(conn.execute(query).scalar() or 0.0, 6)
        except Exception:
            return 0.0

    def export_csv(self, days: int = 30) -> Path | None:
        """Export recent records to a daily CSV file."""
        if self._engine is None:
            return None
        try:
            _ensure_dirs()
            today = datetime.now(UTC).strftime("%Y-%m-%d")
            csv_path = _CSV_DIR / f"llm_usage_{today}.csv"
            
            cutoff_date = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            query = (
                select(
                    llm_calls_table.c.timestamp,
                    llm_calls_table.c.backend,
                    llm_calls_table.c.model,
                    llm_calls_table.c.tier,
                    llm_calls_table.c.input_tokens,
                    llm_calls_table.c.output_tokens,
                    llm_calls_table.c.cost_usd,
                    llm_calls_table.c.success,
                    llm_calls_table.c.error,
                    llm_calls_table.c.project
                )
                .where(llm_calls_table.c.timestamp >= cutoff_date)
                .order_by(llm_calls_table.c.timestamp)
            )

            with self._engine.connect() as conn:
                rows = conn.execute(query).fetchall()

            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "timestamp",
                        "backend",
                        "model",
                        "tier",
                        "input_tokens",
                        "output_tokens",
                        "cost_usd",
                        "success",
                        "error",
                        "project",
                    ]
                )
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
        """Close the Engine component if necessary."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
