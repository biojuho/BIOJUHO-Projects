"""CIE 로컬 SQLite 저장소."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger as log

if TYPE_CHECKING:
    from config import CIEConfig
    from storage.models import ContentBatch, GeneratedContent, MonthlyReview

# ───────────────────────────────────────────────────
#  DB 초기화
# ───────────────────────────────────────────────────

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS trend_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL,
    keyword         TEXT NOT NULL,
    hashtags        TEXT DEFAULT '[]',
    volume          INTEGER DEFAULT 0,
    format_trend    TEXT DEFAULT '',
    tone_trend      TEXT DEFAULT '',
    project_connection TEXT DEFAULT '',
    collected_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS regulation_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL,
    policy_changes  TEXT DEFAULT '[]',
    penalty_triggers TEXT DEFAULT '[]',
    algorithm_prefs TEXT DEFAULT '[]',
    do_list         TEXT DEFAULT '[]',
    dont_list       TEXT DEFAULT '[]',
    checked_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generated_contents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    title           TEXT DEFAULT '',
    body            TEXT NOT NULL,
    hashtags        TEXT DEFAULT '[]',
    trend_keywords  TEXT DEFAULT '[]',
    qa_total_score  REAL DEFAULT 0,
    qa_detail       TEXT DEFAULT '{}',
    regulation_ok   INTEGER DEFAULT 0,
    algorithm_ok    INTEGER DEFAULT 0,
    published       INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monthly_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    month           TEXT NOT NULL,
    performance     TEXT DEFAULT '{}',
    strategy        TEXT DEFAULT '{}',
    improvements    TEXT DEFAULT '[]',
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tr_platform ON trend_reports(platform, collected_at);
CREATE INDEX IF NOT EXISTS idx_gc_platform ON generated_contents(platform, created_at);
CREATE INDEX IF NOT EXISTS idx_gc_qa ON generated_contents(qa_total_score);
"""


def get_connection(config: CIEConfig) -> sqlite3.Connection:
    """SQLite 연결을 반환한다. DB가 없으면 스키마를 초기화한다."""
    db_path = Path(config.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    is_new = not db_path.exists()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    if is_new:
        conn.executescript(_SCHEMA)
        conn.commit()
        log.info(f"🗄️ DB 초기화 완료: {db_path}")

    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """기존 DB에 스키마가 없는 경우 생성한다."""
    conn.executescript(_SCHEMA)
    conn.commit()


# ───────────────────────────────────────────────────
#  트렌드 저장
# ───────────────────────────────────────────────────

def save_trends(conn: sqlite3.Connection, batch) -> int:
    """MergedTrendReport를 DB에 저장한다."""
    count = 0
    for report in batch.platform_reports:
        for trend in report.trends:
            conn.execute(
                """INSERT INTO trend_reports
                   (platform, keyword, hashtags, volume, format_trend,
                    tone_trend, project_connection, collected_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    report.platform,
                    trend.keyword,
                    json.dumps(trend.hashtags, ensure_ascii=False),
                    trend.volume,
                    trend.format_trend,
                    trend.tone_trend,
                    trend.project_connection,
                    report.collected_at.isoformat(),
                ),
            )
            count += 1
    conn.commit()
    log.info(f"🗄️ 트렌드 {count}건 저장 완료")
    return count


# ───────────────────────────────────────────────────
#  규제 리포트 저장
# ───────────────────────────────────────────────────

def save_regulations(conn: sqlite3.Connection, reports: list) -> int:
    """RegulationReport 목록을 DB에 저장한다."""
    count = 0
    for r in reports:
        conn.execute(
            """INSERT INTO regulation_reports
               (platform, policy_changes, penalty_triggers,
                algorithm_prefs, do_list, dont_list, checked_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                r.platform,
                json.dumps(r.policy_changes, ensure_ascii=False),
                json.dumps(r.penalty_triggers, ensure_ascii=False),
                json.dumps(r.algorithm_preferences, ensure_ascii=False),
                json.dumps(r.do_list, ensure_ascii=False),
                json.dumps(r.dont_list, ensure_ascii=False),
                r.checked_at.isoformat(),
            ),
        )
        count += 1
    conn.commit()
    log.info(f"🗄️ 규제 리포트 {count}건 저장 완료")
    return count


# ───────────────────────────────────────────────────
#  콘텐츠 저장
# ───────────────────────────────────────────────────

def save_contents(conn: sqlite3.Connection, batch: ContentBatch) -> int:
    """ContentBatch의 모든 콘텐츠를 DB에 저장한다."""
    count = 0
    for c in batch.contents:
        qa_detail = {}
        qa_total = 0.0
        if c.qa_report:
            qa_detail = {
                "hook": c.qa_report.hook_score,
                "fact": c.qa_report.fact_score,
                "tone": c.qa_report.tone_score,
                "kick": c.qa_report.kick_score,
                "angle": c.qa_report.angle_score,
                "regulation": c.qa_report.regulation_score,
                "algorithm": c.qa_report.algorithm_score,
                "warnings": c.qa_report.warnings,
            }
            qa_total = c.qa_report.total_score

        conn.execute(
            """INSERT INTO generated_contents
               (platform, content_type, title, body, hashtags,
                trend_keywords, qa_total_score, qa_detail,
                regulation_ok, algorithm_ok, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                c.platform,
                c.content_type,
                c.title,
                c.body,
                json.dumps(c.hashtags, ensure_ascii=False),
                json.dumps(c.trend_keywords_used, ensure_ascii=False),
                qa_total,
                json.dumps(qa_detail, ensure_ascii=False),
                1 if c.regulation_compliant else 0,
                1 if c.algorithm_optimized else 0,
                c.created_at.isoformat(),
            ),
        )
        count += 1
    conn.commit()
    log.info(f"🗄️ 콘텐츠 {count}건 저장 완료")
    return count


# ───────────────────────────────────────────────────
#  월간 회고 저장
# ───────────────────────────────────────────────────

def save_review(conn: sqlite3.Connection, review: MonthlyReview) -> None:
    """월간 회고를 DB에 저장한다."""
    conn.execute(
        """INSERT INTO monthly_reviews
           (month, performance, strategy, improvements, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (
            review.month,
            json.dumps(
                {
                    "top": review.top_performers,
                    "bottom": review.bottom_performers,
                    "issues": review.regulation_issues,
                },
                ensure_ascii=False,
            ),
            json.dumps(review.next_month_strategy, ensure_ascii=False),
            json.dumps(review.system_improvements, ensure_ascii=False),
            review.created_at.isoformat(),
        ),
    )
    conn.commit()
    log.info(f"🗄️ 월간 회고 ({review.month}) 저장 완료")
