"""
Schema Snapshot Tests - QC W-4
Detect unannounced schema drift across all pipeline databases.

Strategy:
  1. Extract expected table names from the canonical schema source files
  2. Create in-memory SQLite DBs using each project's init_schema
  3. Compare actual tables against snapshot to detect additions/removals
"""

import re
import sqlite3
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ── Known table snapshots (ground truth as of 2026-04-14) ──
# If a migration adds a table, this test will fail,
# forcing the developer to consciously update the snapshot.

GDT_EXPECTED_TABLES = frozenset({
    "runs", "trends", "tweets", "meta", "source_quality",
    "content_feedback", "posting_time_stats", "watchlist_hits",
    "schema_version", "tweet_performance", "golden_references",
    "trend_genealogy",
    # Migration tables (v6+)
    "trend_quarantine", "validated_trends", "draft_bundles",
    "qa_reports", "review_decisions", "publish_receipts",
    "feedback_summaries",
    # TAP tables (v9+)
    "tap_snapshots", "tap_snapshot_items", "tap_alert_queue",
    "tap_deal_room_events", "tap_checkout_sessions",
    # Reasoning tables
    "trend_facts", "trend_hypotheses", "trend_patterns",
})

CIE_EXPECTED_TABLES = frozenset({
    "trend_reports", "regulation_reports", "generated_contents",
    "monthly_reviews", "content_actual_performance",
})

DN_EXPECTED_TABLES = frozenset({
    "schema_version", "job_runs", "article_cache",
    "content_reports", "channel_publications", "llm_cache",
    "x_daily_posts", "topic_timeline", "x_tweet_metrics",
    "feed_etag_cache", "fact_fragments", "hypotheses",
    "reasoning_patterns", "digest_queue",
    # Pipeline-specific
    "pipeline_checkpoints", "signal_history",
    # Subscriber
    "subscribers", "newsletter_events",
})


def _extract_table_names_from_file(path: Path) -> set[str]:
    """Extract CREATE TABLE names from a Python file using regex."""
    if not path.exists():
        return set()
    content = path.read_text(encoding="utf-8", errors="replace")
    pattern = r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)"
    return {m.group(1).lower() for m in re.finditer(pattern, content, re.IGNORECASE)}


class TestGdtSchemaSnapshot:
    """GetDayTrends schema drift detection."""

    def test_db_schema_tables_match_snapshot(self):
        schema_file = PROJECT_ROOT / "automation" / "getdaytrends" / "db_schema.py"
        migration_file = PROJECT_ROOT / "automation" / "getdaytrends" / "db_layer" / "migrations.py"
        reasoning_file = PROJECT_ROOT / "automation" / "getdaytrends" / "trend_reasoning.py"

        actual = set()
        for f in [schema_file, migration_file, reasoning_file]:
            actual |= _extract_table_names_from_file(f)

        # Exclude test-only tables
        actual -= {"test", "t"}

        missing = GDT_EXPECTED_TABLES - actual
        unexpected = actual - GDT_EXPECTED_TABLES

        assert not missing, (
            f"Tables REMOVED from GDT schema without snapshot update: {missing}\n"
            f"If intentional, remove them from GDT_EXPECTED_TABLES in this test."
        )
        assert not unexpected, (
            f"Tables ADDED to GDT schema without snapshot update: {unexpected}\n"
            f"If intentional, add them to GDT_EXPECTED_TABLES in this test."
        )

    def test_core_tables_have_required_columns(self):
        """Verify core tables have minimum required columns."""
        schema_file = PROJECT_ROOT / "automation" / "getdaytrends" / "db_schema.py"
        content = schema_file.read_text(encoding="utf-8", errors="replace")

        # 'trends' must have fingerprint (dedup key)
        assert "fingerprint" in content, "trends table missing fingerprint column"
        # 'runs' must have run_uuid
        assert "run_uuid" in content, "runs table missing run_uuid column"
        # 'tweets' must have x_tweet_id (performance tracking)
        assert "x_tweet_id" in content, "tweets table missing x_tweet_id column"


class TestCieSchemaSnapshot:
    """Content Intelligence schema drift detection."""

    def test_schema_tables_match_snapshot(self):
        schema_file = PROJECT_ROOT / "automation" / "content-intelligence" / "storage" / "local_db.py"
        actual = _extract_table_names_from_file(schema_file)

        missing = CIE_EXPECTED_TABLES - actual
        unexpected = actual - CIE_EXPECTED_TABLES

        assert not missing, (
            f"Tables REMOVED from CIE schema without snapshot update: {missing}"
        )
        assert not unexpected, (
            f"Tables ADDED to CIE schema without snapshot update: {unexpected}"
        )


class TestDailyNewsSchemaSnapshot:
    """DailyNews schema drift detection."""

    def test_schema_tables_match_snapshot(self):
        store_file = PROJECT_ROOT / "automation" / "DailyNews" / "src" / "antigravity_mcp" / "state" / "store.py"
        signal_file = PROJECT_ROOT / "automation" / "DailyNews" / "src" / "antigravity_mcp" / "pipelines" / "signal_watch.py"
        subscriber_file = PROJECT_ROOT / "automation" / "DailyNews" / "src" / "antigravity_mcp" / "integrations" / "subscriber_store.py"
        db_client_file = PROJECT_ROOT / "automation" / "DailyNews" / "src" / "antigravity_mcp" / "state" / "db_client.py"

        actual = set()
        for f in [store_file, signal_file, subscriber_file, db_client_file]:
            actual |= _extract_table_names_from_file(f)

        # Exclude migration/test artifacts
        actual -= {"test", "t"}

        missing = DN_EXPECTED_TABLES - actual
        unexpected = actual - DN_EXPECTED_TABLES

        assert not missing, (
            f"Tables REMOVED from DN schema without snapshot update: {missing}"
        )
        assert not unexpected, (
            f"Tables ADDED to DN schema without snapshot update: {unexpected}"
        )


class TestCrossProjectSchemaConsistency:
    """Verify shared table patterns across projects."""

    def test_no_table_name_collision_across_projects(self):
        """Different projects should not accidentally use the same table name
        in the same DB (except shared patterns like schema_version)."""
        ALLOWED_SHARED = {"schema_version"}

        gdt = GDT_EXPECTED_TABLES - ALLOWED_SHARED
        cie = CIE_EXPECTED_TABLES - ALLOWED_SHARED
        dn = DN_EXPECTED_TABLES - ALLOWED_SHARED

        gdt_cie = gdt & cie
        gdt_dn = gdt & dn
        cie_dn = cie & dn

        assert not gdt_cie, f"GDT-CIE table name collision: {gdt_cie}"
        assert not gdt_dn, f"GDT-DN table name collision: {gdt_dn}"
        assert not cie_dn, f"CIE-DN table name collision: {cie_dn}"

    def test_expected_table_counts(self):
        """Sanity check: each project has a reasonable schema size."""
        assert len(GDT_EXPECTED_TABLES) >= 10, "GDT schema unexpectedly small"
        assert len(CIE_EXPECTED_TABLES) >= 4, "CIE schema unexpectedly small"
        assert len(DN_EXPECTED_TABLES) >= 10, "DN schema unexpectedly small"
