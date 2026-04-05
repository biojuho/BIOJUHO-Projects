"""CIE local_db 저장소 단위 테스트."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

_CIE_DIR = Path(__file__).resolve().parents[1]
if str(_CIE_DIR) not in sys.path:
    sys.path.insert(0, str(_CIE_DIR))

from config import CIEConfig
from storage.local_db import (
    ensure_schema,
    get_connection,
    load_unpublished_contents,
    save_contents,
    save_regulations,
    save_review,
    save_trends,
)
from storage.models import (
    ContentBatch,
    GeneratedContent,
    MergedTrendReport,
    MonthlyReview,
    PlatformTrend,
    PlatformTrendReport,
    QAAxisDiagnostic,
    QAReport,
    RegulationReport,
    UnifiedChecklist,
)


@pytest.fixture
def db_config(tmp_path):
    db_path = tmp_path / "test_cie.db"
    return CIEConfig(sqlite_path=str(db_path))


@pytest.fixture
def conn(db_config):
    c = get_connection(db_config)
    yield c
    c.close()


class TestGetConnection:
    def test_creates_db(self, db_config):
        c = get_connection(db_config)
        assert Path(db_config.sqlite_path).exists()
        # Verify tables exist
        tables = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "trend_reports" in table_names
        assert "generated_contents" in table_names
        assert "regulation_reports" in table_names
        c.close()

    def test_ensure_schema_idempotent(self, conn):
        ensure_schema(conn)
        ensure_schema(conn)  # should not raise


class TestSaveTrends:
    def test_save_and_count(self, conn):
        trend = PlatformTrend(keyword="AI", volume=100, format_trend="thread")
        report = PlatformTrendReport(platform="x", trends=[trend])
        merged = MergedTrendReport(platform_reports=[report])
        count = save_trends(conn, merged)
        assert count == 1

        rows = conn.execute("SELECT * FROM trend_reports").fetchall()
        assert len(rows) == 1
        assert rows[0]["keyword"] == "AI"
        assert rows[0]["platform"] == "x"

    def test_save_multiple_platforms(self, conn):
        trends_x = [PlatformTrend(keyword="LLM")]
        trends_naver = [PlatformTrend(keyword="Claude"), PlatformTrend(keyword="GPT")]
        merged = MergedTrendReport(
            platform_reports=[
                PlatformTrendReport(platform="x", trends=trends_x),
                PlatformTrendReport(platform="naver", trends=trends_naver),
            ]
        )
        count = save_trends(conn, merged)
        assert count == 3


class TestSaveRegulations:
    def test_save(self, conn):
        reports = [
            RegulationReport(
                platform="x",
                do_list=["use threads"],
                dont_list=["spam"],
                policy_changes=[{"change": "new rule"}],
            ),
        ]
        count = save_regulations(conn, reports)
        assert count == 1

        rows = conn.execute("SELECT * FROM regulation_reports").fetchall()
        assert len(rows) == 1
        do_list = json.loads(rows[0]["do_list"])
        assert "use threads" in do_list


class TestSaveContents:
    def test_save_with_qa(self, conn):
        qa = QAReport(
            hook_score=15, fact_score=12, tone_score=10,
            kick_score=10, angle_score=10, regulation_score=8,
            algorithm_score=7, reader_value_score=6,
            originality_score=5, credibility_score=4,
            diagnostics=[
                QAAxisDiagnostic(axis="hook", score=15, max_score=20, reason="good"),
            ],
        )
        content = GeneratedContent(
            platform="x", content_type="post",
            body="Test content body",
            hashtags=["#AI"],
            qa_report=qa,
        )
        batch = ContentBatch(contents=[content])
        count = save_contents(conn, batch)
        assert count == 1

        rows = conn.execute("SELECT * FROM generated_contents").fetchall()
        assert len(rows) == 1
        assert rows[0]["qa_total_score"] == 72.0
        qa_detail = json.loads(rows[0]["qa_detail"])
        assert qa_detail["hook"] == 15
        assert "diagnostics" in qa_detail

    def test_duplicate_content_skipped(self, conn):
        content = GeneratedContent(
            platform="x", content_type="post", body="Same body",
        )
        batch = ContentBatch(contents=[content])
        save_contents(conn, batch)
        count2 = save_contents(conn, batch)
        assert count2 == 0  # duplicate skipped

    def test_save_without_qa(self, conn):
        content = GeneratedContent(
            platform="naver", content_type="blog",
            body="Blog post content",
            title="Test Blog",
        )
        batch = ContentBatch(contents=[content])
        count = save_contents(conn, batch)
        assert count == 1


class TestLoadUnpublished:
    def test_load(self, conn):
        # Insert a content row manually
        conn.execute(
            """INSERT INTO generated_contents
               (platform, content_type, title, body, content_hash, hashtags,
                trend_keywords, qa_total_score, qa_detail, regulation_ok,
                algorithm_ok, published, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("x", "post", "", "Good content", "hash1", "[]", "[]",
             80.0, json.dumps({"hook": 15, "fact": 12, "tone": 10,
                               "kick": 10, "angle": 10, "regulation": 8,
                               "algorithm": 7, "warnings": []}),
             1, 1, 0, datetime.now().isoformat()),
        )
        conn.commit()

        contents = load_unpublished_contents(conn, min_qa_score=70)
        assert len(contents) == 1
        assert contents[0].platform == "x"
        assert contents[0].qa_report is not None
        assert contents[0].qa_report.hook_score == 15

    def test_load_filters_low_qa(self, conn):
        conn.execute(
            """INSERT INTO generated_contents
               (platform, content_type, title, body, content_hash, hashtags,
                trend_keywords, qa_total_score, qa_detail, regulation_ok,
                algorithm_ok, published, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("x", "post", "", "Low quality", "hash2", "[]", "[]",
             30.0, "{}", 0, 0, 0, datetime.now().isoformat()),
        )
        conn.commit()

        contents = load_unpublished_contents(conn, min_qa_score=70)
        assert len(contents) == 0

    def test_load_filters_published(self, conn):
        conn.execute(
            """INSERT INTO generated_contents
               (platform, content_type, title, body, content_hash, hashtags,
                trend_keywords, qa_total_score, qa_detail, regulation_ok,
                algorithm_ok, published, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("x", "post", "", "Published content", "hash3", "[]", "[]",
             85.0, "{}", 1, 1, 1, datetime.now().isoformat()),
        )
        conn.commit()

        contents = load_unpublished_contents(conn, min_qa_score=70)
        assert len(contents) == 0


class TestSaveReview:
    def test_save(self, conn):
        review = MonthlyReview(
            month="2026-03",
            top_performers=[{"keyword": "AI", "score": 95}],
            next_month_strategy=["Focus on LLM content"],
            system_improvements=["Add caching"],
        )
        save_review(conn, review)

        rows = conn.execute("SELECT * FROM monthly_reviews").fetchall()
        assert len(rows) == 1
        assert rows[0]["month"] == "2026-03"
