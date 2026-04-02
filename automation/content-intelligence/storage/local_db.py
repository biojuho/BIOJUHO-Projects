"""CIE 로컬 SQLite 저장소 v2.0 — 발행 메타데이터 지원."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger as log

if TYPE_CHECKING:
    from config import CIEConfig
    from storage.models import ContentBatch, MonthlyReview

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
    sentiment       TEXT DEFAULT 'neutral',
    confidence      INTEGER DEFAULT 0,
    hook_starter    TEXT DEFAULT '',
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
    content_hash    TEXT NOT NULL DEFAULT '',
    hashtags        TEXT DEFAULT '[]',
    trend_keywords  TEXT DEFAULT '[]',
    qa_total_score  REAL DEFAULT 0,
    qa_detail       TEXT DEFAULT '{}',
    regulation_ok   INTEGER DEFAULT 0,
    algorithm_ok    INTEGER DEFAULT 0,
    published       INTEGER DEFAULT 0,
    published_at    TEXT DEFAULT NULL,
    publish_target  TEXT DEFAULT '',
    notion_page_id  TEXT DEFAULT '',
    publish_error   TEXT DEFAULT '',
    created_at      TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_gc_content_hash ON generated_contents(content_hash) WHERE content_hash != '';

CREATE TABLE IF NOT EXISTS monthly_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    month           TEXT NOT NULL,
    performance     TEXT DEFAULT '{}',
    strategy        TEXT DEFAULT '{}',
    improvements    TEXT DEFAULT '[]',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS content_actual_performance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id      INTEGER NOT NULL,
    platform        TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    tweet_id        TEXT DEFAULT '',
    impressions     INTEGER DEFAULT 0,
    likes           INTEGER DEFAULT 0,
    retweets        INTEGER DEFAULT 0,
    quotes          INTEGER DEFAULT 0,
    replies         INTEGER DEFAULT 0,
    bookmarks       INTEGER DEFAULT 0,
    engagement_rate REAL DEFAULT 0.0,
    collected_at    TEXT NOT NULL,
    UNIQUE(content_id, platform)
);

CREATE INDEX IF NOT EXISTS idx_cap_er ON content_actual_performance(engagement_rate);
CREATE INDEX IF NOT EXISTS idx_tr_platform ON trend_reports(platform, collected_at);
CREATE INDEX IF NOT EXISTS idx_gc_platform ON generated_contents(platform, created_at);
CREATE INDEX IF NOT EXISTS idx_gc_qa ON generated_contents(qa_total_score);
CREATE INDEX IF NOT EXISTS idx_gc_published ON generated_contents(published, created_at);
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
    else:
        # v2.0 마이그레이션: 새 컬럼 추가
        _migrate_v2(conn)

    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """기존 DB에 스키마가 없는 경우 생성한다."""
    conn.executescript(_SCHEMA)
    conn.commit()
    _migrate_v2(conn)


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """v2.0 스키마 마이그레이션: 발행 메타데이터 + 트렌드 확장 컬럼.

    모든 ALTER TABLE을 하나의 트랜잭션으로 묶어 부분 마이그레이션을 방지한다.
    SQLite는 DDL을 트랜잭션 안에서 실행할 수 있다.
    """
    migrations: list[tuple[str, str, str]] = [
        # (table, column, definition)
        ("generated_contents", "published_at",  "TEXT DEFAULT NULL"),
        ("generated_contents", "publish_target", "TEXT DEFAULT ''"),
        ("generated_contents", "notion_page_id", "TEXT DEFAULT ''"),
        ("generated_contents", "publish_error",  "TEXT DEFAULT ''"),
        ("generated_contents", "content_hash",   "TEXT NOT NULL DEFAULT ''"),
        ("trend_reports",      "sentiment",      "TEXT DEFAULT 'neutral'"),
        ("trend_reports",      "confidence",     "INTEGER DEFAULT 0"),
        ("trend_reports",      "hook_starter",   "TEXT DEFAULT ''"),
    ]

    pending = []
    for table, col, defn in migrations:
        try:
            conn.execute(f"SELECT {col} FROM {table} LIMIT 1")
        except sqlite3.OperationalError:
            pending.append((table, col, defn))

    if not pending:
        return

    try:
        for table, col, defn in pending:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {defn}")
            log.debug(f"  마이그레이션: {table}.{col} 추가")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ───────────────────────────────────────────────────
#  트렌드 저장
# ───────────────────────────────────────────────────


def save_trends(conn: sqlite3.Connection, batch) -> int:
    """MergedTrendReport를 DB에 저장한다."""
    count = 0
    try:
        for report in batch.platform_reports:
            for trend in report.trends:
                conn.execute(
                    """INSERT INTO trend_reports
                       (platform, keyword, hashtags, volume, format_trend,
                        tone_trend, project_connection, sentiment, confidence,
                        hook_starter, collected_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        report.platform,
                        trend.keyword,
                        json.dumps(trend.hashtags, ensure_ascii=False),
                        trend.volume,
                        trend.format_trend,
                        trend.tone_trend,
                        trend.project_connection,
                        getattr(trend, "sentiment", "neutral"),
                        getattr(trend, "confidence", 0),
                        getattr(trend, "hook_starter", ""),
                        report.collected_at.isoformat(),
                    ),
                )
                count += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    log.info(f"🗄️ 트렌드 {count}건 저장 완료")
    return count


# ───────────────────────────────────────────────────
#  규제 리포트 저장
# ───────────────────────────────────────────────────


def save_regulations(conn: sqlite3.Connection, reports: list) -> int:
    """RegulationReport 목록을 DB에 저장한다."""
    count = 0
    try:
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
    except Exception:
        conn.rollback()
        raise
    log.info(f"🗄️ 규제 리포트 {count}건 저장 완료")
    return count


# ───────────────────────────────────────────────────
#  콘텐츠 저장
# ───────────────────────────────────────────────────


def save_contents(conn: sqlite3.Connection, batch: ContentBatch) -> int:
    """ContentBatch의 모든 콘텐츠를 DB에 저장한다."""
    count = 0
    try:
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
                    "reader_value": c.qa_report.reader_value_score,
                    "originality": c.qa_report.originality_score,
                    "credibility": c.qa_report.credibility_score,
                    "applied_min_score": c.qa_report.applied_min_score,
                    "diagnostics": [
                        {"axis": d.axis, "score": d.score, "max": d.max_score,
                         "reason": d.reason, "suggestion": d.suggestion}
                        for d in c.qa_report.diagnostics
                    ],
                    "persona_fits": [
                        {"id": p.persona_id, "name": p.persona_name,
                         "fit": p.fit_score, "reason": p.reason}
                        for p in c.qa_report.persona_fits
                    ],
                    "rewrite_suggestion": c.qa_report.rewrite_suggestion,
                }
                qa_total = c.qa_report.total_score

            content_hash = hashlib.sha256(
                f"{c.platform}:{c.content_type}:{c.body}".encode()
            ).hexdigest()

            try:
                conn.execute(
                    """INSERT INTO generated_contents
                       (platform, content_type, title, body, content_hash, hashtags,
                        trend_keywords, qa_total_score, qa_detail,
                        regulation_ok, algorithm_ok, published,
                        published_at, publish_target, notion_page_id,
                        publish_error, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        c.platform,
                        c.content_type,
                        c.title,
                        c.body,
                        content_hash,
                        json.dumps(c.hashtags, ensure_ascii=False),
                        json.dumps(c.trend_keywords_used, ensure_ascii=False),
                        qa_total,
                        json.dumps(qa_detail, ensure_ascii=False),
                        1 if c.regulation_compliant else 0,
                        1 if c.algorithm_optimized else 0,
                        1 if c.is_published else 0,
                        c.published_at.isoformat() if c.published_at else None,
                        c.publish_target,
                        c.notion_page_id,
                        c.publish_error,
                        c.created_at.isoformat(),
                    ),
                )
                count += 1
            except sqlite3.IntegrityError:
                log.warning(f"  ⚠️ 중복 콘텐츠 건너뜀 [{c.platform}/{c.content_type}] hash={content_hash[:8]}…")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    log.info(f"🗄️ 콘텐츠 {count}건 저장 완료")
    return count


# ───────────────────────────────────────────────────
#  미발행 콘텐츠 로드 (publish-only 모드)
# ───────────────────────────────────────────────────


def load_unpublished_contents(conn: sqlite3.Connection, min_qa_score: int = 70) -> list:
    """DB에서 QA 통과했지만 미발행인 콘텐츠를 로드한다."""
    from storage.models import GeneratedContent, PersonaFitScore, QAAxisDiagnostic, QAReport

    rows = conn.execute(
        """SELECT * FROM generated_contents
           WHERE published = 0
             AND qa_total_score >= ?
           ORDER BY created_at DESC
           LIMIT 20""",
        (min_qa_score,),
    ).fetchall()

    contents = []
    for row in rows:
        qa_detail = json.loads(row["qa_detail"]) if row["qa_detail"] else {}
        qa_report = None
        if qa_detail:
            diag_list = [
                QAAxisDiagnostic(
                    axis=d.get("axis", ""),
                    score=d.get("score", 0),
                    max_score=d.get("max", 0),
                    reason=d.get("reason", ""),
                    suggestion=d.get("suggestion", ""),
                )
                for d in qa_detail.get("diagnostics", [])
                if isinstance(d, dict)
            ]
            fit_list = [
                PersonaFitScore(
                    persona_id=p.get("id", ""),
                    persona_name=p.get("name", ""),
                    fit_score=p.get("fit", 0),
                    reason=p.get("reason", ""),
                )
                for p in qa_detail.get("persona_fits", [])
                if isinstance(p, dict)
            ]
            qa_report = QAReport(
                hook_score=qa_detail.get("hook", 0),
                fact_score=qa_detail.get("fact", 0),
                tone_score=qa_detail.get("tone", 0),
                kick_score=qa_detail.get("kick", 0),
                angle_score=qa_detail.get("angle", 0),
                regulation_score=qa_detail.get("regulation", 0),
                algorithm_score=qa_detail.get("algorithm", 0),
                warnings=qa_detail.get("warnings", []),
                reader_value_score=qa_detail.get("reader_value", 0),
                originality_score=qa_detail.get("originality", 0),
                credibility_score=qa_detail.get("credibility", 0),
                applied_min_score=qa_detail.get("applied_min_score", 70),
                diagnostics=diag_list,
                persona_fits=fit_list,
                rewrite_suggestion=qa_detail.get("rewrite_suggestion", ""),
            )

        contents.append(
            GeneratedContent(
                platform=row["platform"],
                content_type=row["content_type"],
                title=row["title"] or "",
                body=row["body"],
                hashtags=json.loads(row["hashtags"]) if row["hashtags"] else [],
                trend_keywords_used=json.loads(row["trend_keywords"]) if row["trend_keywords"] else [],
                qa_report=qa_report,
                regulation_compliant=bool(row["regulation_ok"]),
                algorithm_optimized=bool(row["algorithm_ok"]),
            )
        )

    return contents


# ───────────────────────────────────────────────────
#  월간 회고 저장
# ───────────────────────────────────────────────────


def save_review(conn: sqlite3.Connection, review: MonthlyReview) -> None:
    """월간 회고를 DB에 저장한다."""
    try:
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
    except Exception:
        conn.rollback()
        raise
    log.info(f"🗄️ 월간 회고 ({review.month}) 저장 완료")
