"""Signal Watch Pipeline — standalone trend monitoring for DailyNews.

Runs independently of the main batch pipeline. Can be triggered:
  - CLI: `antigravity-mcp signal watch`
  - GitHub Actions cron (every 3 hours)
  - Manual invocation

Outputs signal reports to state DB and optionally triggers draft generation.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from antigravity_mcp.config import DATA_DIR, get_settings
from antigravity_mcp.domain.models import ContentItem
from antigravity_mcp.integrations.signal_collector import MultiSourceCollector
from antigravity_mcp.integrations.signal_scorer import ScoredSignal, SignalScorer
from antigravity_mcp.pipelines.analyze import generate_briefs
from antigravity_mcp.state.store import PipelineStateStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# psycopg2 optional import
# ---------------------------------------------------------------------------

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    _PG_AVAILABLE = True
except ImportError:
    _PG_AVAILABLE = False

# ---------------------------------------------------------------------------
# Signal State Store (Supabase PostgreSQL + SQLite dual-mode)
# ---------------------------------------------------------------------------

_SIGNAL_DB_PATH = DATA_DIR / "signal_watch.db"

_SQLITE_SCHEMA = """\
CREATE TABLE IF NOT EXISTS signal_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword       TEXT NOT NULL,
    composite_score REAL NOT NULL,
    sources       TEXT NOT NULL,
    source_count  INTEGER NOT NULL,
    arbitrage_type TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    velocity      REAL DEFAULT 0.0,
    category_hint TEXT DEFAULT '',
    detected_at   TEXT NOT NULL,
    raw_data      TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_sh_keyword_detected ON signal_history(keyword, detected_at);
CREATE INDEX IF NOT EXISTS idx_sh_detected ON signal_history(detected_at);
CREATE INDEX IF NOT EXISTS idx_sh_score ON signal_history(composite_score);
"""

_PG_SCHEMA = """\
CREATE TABLE IF NOT EXISTS signal_history (
    id            SERIAL PRIMARY KEY,
    keyword       TEXT NOT NULL,
    composite_score DOUBLE PRECISION NOT NULL,
    sources       TEXT NOT NULL,
    source_count  INTEGER NOT NULL,
    arbitrage_type TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    velocity      DOUBLE PRECISION DEFAULT 0.0,
    category_hint TEXT DEFAULT '',
    detected_at   TEXT NOT NULL,
    raw_data      TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_sh_keyword_detected ON signal_history(keyword, detected_at);
CREATE INDEX IF NOT EXISTS idx_sh_detected ON signal_history(detected_at);
CREATE INDEX IF NOT EXISTS idx_sh_score ON signal_history(composite_score);
"""


class SignalStateStore:
    """Dual-mode signal history store: Supabase PostgreSQL when available, SQLite fallback.

    Priority: SUPABASE_DATABASE_URL (env) → explicit db_path → default SQLite path.
    """

    def __init__(self, *, db_path: Path | str | None = None) -> None:
        self._explicit_db_path = str(db_path) if db_path else None
        self._initialised = False

        # Determine mode
        try:
            settings = get_settings()
            self._pg_url: str = settings.supabase_database_url or ""
        except Exception:
            self._pg_url = os.getenv("SUPABASE_DATABASE_URL", "") or os.getenv("DATABASE_URL", "")

        self._use_pg = bool(self._pg_url and _PG_AVAILABLE and not self._explicit_db_path)
        if self._use_pg:
            logger.info("SignalStateStore: using PostgreSQL (Supabase)")
        else:
            if self._pg_url and not _PG_AVAILABLE:
                logger.warning("SignalStateStore: SUPABASE_DATABASE_URL set but psycopg2 unavailable — falling back to SQLite")
            self._sqlite_path = self._explicit_db_path or str(_SIGNAL_DB_PATH)
            logger.info("SignalStateStore: using SQLite (%s)", self._sqlite_path)

    # -- Connection helpers -------------------------------------------------

    @contextmanager
    def _get_connection(self) -> Iterator[Any]:
        """Yield a DB connection (PG or SQLite) with auto-commit semantics."""
        if self._use_pg:
            conn = psycopg2.connect(self._pg_url, cursor_factory=RealDictCursor)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        else:
            os.makedirs(os.path.dirname(self._sqlite_path) or ".", exist_ok=True)
            conn = sqlite3.connect(self._sqlite_path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    def _ensure_init(self) -> None:
        if self._initialised:
            return
        with self._get_connection() as conn:
            if self._use_pg:
                with conn.cursor() as cur:
                    for stmt in _PG_SCHEMA.strip().split(";"):
                        stmt = stmt.strip()
                        if stmt:
                            cur.execute(stmt)
            else:
                conn.executescript(_SQLITE_SCHEMA)
        self._initialised = True

    # -- placeholder helper (? for SQLite, %s for PG) ----------------------

    @property
    def _ph(self) -> str:
        return "%s" if self._use_pg else "?"

    def _execute(self, conn: Any, sql: str, params: tuple = ()) -> Any:
        """Execute a query with the correct placeholder style."""
        if self._use_pg:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur
        else:
            return conn.execute(sql, params)

    def _fetchall(self, conn: Any, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute and fetchall, returning list of dicts."""
        if self._use_pg:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [dict(row) for row in cur.fetchall()]
        else:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def _fetchone(self, conn: Any, sql: str, params: tuple = ()) -> Any:
        """Execute and fetchone."""
        if self._use_pg:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()
        else:
            cursor = conn.execute(sql, params)
            return cursor.fetchone()

    # -- Public API ---------------------------------------------------------

    def save_signals(self, signals: list[ScoredSignal]) -> int:
        """Persist scored signals. Returns count saved."""
        self._ensure_init()
        now = datetime.now(UTC).isoformat()
        ph = self._ph

        insert_sql = f"""
            INSERT INTO signal_history
                (keyword, composite_score, sources, source_count,
                 arbitrage_type, recommended_action, velocity,
                 category_hint, detected_at, raw_data)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        """

        rows = []
        for s in signals:
            rows.append((
                s.keyword,
                s.composite_score,
                json.dumps(s.sources),
                s.source_count,
                s.arbitrage_type,
                s.recommended_action,
                s.velocity,
                s.category_hint,
                now,
                json.dumps({"raw_count": len(s.raw_signals)}),
            ))

        with self._get_connection() as conn:
            if self._use_pg:
                with conn.cursor() as cur:
                    for row in rows:
                        cur.execute(insert_sql, row)
            else:
                conn.executemany(insert_sql, rows)
        return len(rows)

    def get_signal_history(self, *, hours: int = 24, min_score: float = 0.0, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent signal history."""
        self._ensure_init()
        cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
        ph = self._ph
        sql = f"""
            SELECT keyword, composite_score, sources, source_count,
                   arbitrage_type, recommended_action, velocity,
                   category_hint, detected_at
            FROM signal_history
            WHERE detected_at >= {ph} AND composite_score >= {ph}
            ORDER BY composite_score DESC
            LIMIT {ph}
        """
        with self._get_connection() as conn:
            return self._fetchall(conn, sql, (cutoff, min_score, limit))

    def is_duplicate(self, keyword: str, *, within_hours: int = 3) -> bool:
        """Check if we already recorded this keyword recently."""
        self._ensure_init()
        cutoff = (datetime.now(UTC) - timedelta(hours=within_hours)).isoformat()
        ph = self._ph
        sql = f"SELECT COUNT(*) FROM signal_history WHERE keyword = {ph} AND detected_at >= {ph}"
        with self._get_connection() as conn:
            row = self._fetchone(conn, sql, (keyword, cutoff))
            if row is None:
                return False
            # PG returns dict, SQLite returns Row
            if isinstance(row, dict):
                return (row.get("count", 0) or 0) > 0
            return (row[0] or 0) > 0


# ---------------------------------------------------------------------------
# Pipeline Entry Point
# ---------------------------------------------------------------------------


async def run_signal_watch(
    *,
    threshold: float = 0.6,
    auto_draft: bool = False,
    categories: list[str] | None = None,
    country: str = "KR",
    limit_per_source: int = 20,
    dedup_hours: int = 3,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Run one cycle of signal watch.

    1. Collect signals from all sources (parallel)
    2. Cross-verify and score
    3. De-duplicate against recent history
    4. Save to state DB
    5. Return actionable signals

    Args:
        threshold: Minimum composite score to report.
        auto_draft: If True, trigger draft generation for top signals.
        categories: Target categories for affinity scoring.
        country: Country for Google Trends.
        limit_per_source: Max signals per source.
        dedup_hours: Skip keywords seen within this window.
        db_path: Override signal DB path (for testing).

    Returns:
        {
            "status": "ok",
            "total_collected": int,
            "total_scored": int,
            "actionable": int,
            "signals": [...],
            "sources": [...],
        }
    """
    started_at = datetime.now(UTC)
    store = SignalStateStore(db_path=db_path)

    # Step 1: Collect
    collector = MultiSourceCollector(country=country)
    raw_signals = await collector.collect_all(limit_per_source=limit_per_source)

    if not raw_signals:
        return {
            "status": "ok",
            "total_collected": 0,
            "total_scored": 0,
            "actionable": 0,
            "signals": [],
            "sources": collector.source_names,
            "elapsed_sec": (datetime.now(UTC) - started_at).total_seconds(),
        }

    # Step 2: Score
    scorer = SignalScorer(target_categories=categories)
    scored = scorer.score_signals(raw_signals, min_score=threshold)

    # Step 3: De-duplicate
    actionable: list[ScoredSignal] = []
    for signal in scored:
        if not store.is_duplicate(signal.keyword, within_hours=dedup_hours):
            actionable.append(signal)

    # Step 4: Save
    if actionable:
        store.save_signals(actionable)

    # Step 5: Format output
    signal_dicts = []
    for s in actionable:
        signal_dicts.append({
            "keyword": s.keyword,
            "score": s.composite_score,
            "sources": s.sources,
            "source_count": s.source_count,
            "type": s.arbitrage_type,
            "action": s.recommended_action,
            "velocity": s.velocity,
            "category": s.category_hint,
        })

    # Step 6: Auto-draft Trigger
    if auto_draft and actionable:
        draft_candidates = [s for s in actionable if s.recommended_action in ("draft_now", "series")]
        if draft_candidates:
            await _trigger_auto_draft(draft_candidates, run_id=f"signal_{started_at.strftime('%Y%m%d%H%M')}")

    elapsed = (datetime.now(UTC) - started_at).total_seconds()

    logger.info(
        "Signal Watch complete: %d collected → %d scored → %d actionable (%.1fs)",
        len(raw_signals),
        len(scored),
        len(actionable),
        elapsed,
    )

    return {
        "status": "ok",
        "total_collected": len(raw_signals),
        "total_scored": len(scored),
        "actionable": len(actionable),
        "signals": signal_dicts,
        "sources": collector.source_names,
        "elapsed_sec": round(elapsed, 2),
    }


async def _trigger_auto_draft(signals: list[ScoredSignal], run_id: str) -> None:
    """Generate synthetic ContentItems for signals and push to analyze pipeline."""
    from antigravity_mcp.integrations.jina_adapter import JinaAdapter

    jina = JinaAdapter(timeout=15.0)
    items = []
    now_iso = datetime.now(UTC).isoformat()

    for s in signals:
        query = f'"{s.keyword}" news 2026'
        logger.info("Fetching deep search context for signal: %s", s.keyword)
        deep_context = await jina.search_topic(query, max_length=4000)

        summary = (
            f"Trend detected via {', '.join(s.sources)} with score {s.composite_score:.2f}. "
            f"Velocity: {s.velocity:.2f}. Suggested action: {s.recommended_action}.\n\n"
        )
        if deep_context:
            summary += f"[Deep Context (Jina.ai Search)]\n{deep_context}"
        else:
            summary += "[Deep Context (Jina.ai Search)]\n(No deep context could be retrieved via search)"

        # Create synthetic ContentItem mapped from signal
        items.append(
            ContentItem(
                source_name="SignalArbitrage",
                category="TrendAlert",
                title=f"🚀 Trending Alert: {s.keyword} ({s.arbitrage_type})",
                link=f"https://www.google.com/search?q={s.keyword}&tbm=nws",  # Fallback query
                published_at=now_iso,
                summary=summary,
            )
        )

    logger.info("Auto-drafting %d trending signals...", len(items))
    state_store = PipelineStateStore()

    try:
        # We can bypass collect.py and directly trigger analyze
        run_id_out, reports, warnings, status = await generate_briefs(
            items=items,
            window_name="Trending_Alert",
            window_start=now_iso,
            window_end=now_iso,
            state_store=state_store,
            run_id=run_id,
        )
        logger.info(
            "Auto-draft finished: status=%s, %d reports generated. Warnings: %s",
            status, len(reports), warnings
        )
    except Exception as exc:
        logger.error("Auto-draft pipeline failed: %s", exc)
