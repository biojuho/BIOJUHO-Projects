"""
getdaytrends v2.0 - SQLite Database
트렌드 히스토리 저장, CRUD 헬퍼 함수.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta

from models import GeneratedThread, GeneratedTweet, RunResult, ScoredTrend


def get_connection(db_path: str = "data/getdaytrends.db") -> sqlite3.Connection:
    """SQLite DB 연결. data/ 디렉토리 자동 생성."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """테이블 생성 (없으면)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            run_uuid      TEXT NOT NULL UNIQUE,
            started_at    TEXT NOT NULL,
            finished_at   TEXT,
            country       TEXT NOT NULL DEFAULT 'korea',
            trends_collected  INTEGER DEFAULT 0,
            trends_scored     INTEGER DEFAULT 0,
            tweets_generated  INTEGER DEFAULT 0,
            tweets_saved      INTEGER DEFAULT 0,
            alerts_sent       INTEGER DEFAULT 0,
            errors        TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS trends (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id             INTEGER NOT NULL REFERENCES runs(id),
            keyword            TEXT NOT NULL,
            rank               INTEGER,
            volume_raw         TEXT DEFAULT 'N/A',
            volume_numeric     INTEGER DEFAULT 0,
            viral_potential    INTEGER DEFAULT 0,
            trend_acceleration TEXT DEFAULT '+0%',
            top_insight        TEXT DEFAULT '',
            suggested_angles   TEXT DEFAULT '[]',
            best_hook_starter  TEXT DEFAULT '',
            country            TEXT DEFAULT 'korea',
            sources            TEXT DEFAULT '[]',
            twitter_context    TEXT DEFAULT '',
            reddit_context     TEXT DEFAULT '',
            news_context       TEXT DEFAULT '',
            scored_at          TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_trends_keyword ON trends(keyword);
        CREATE INDEX IF NOT EXISTS idx_trends_scored_at ON trends(scored_at);
        CREATE INDEX IF NOT EXISTS idx_trends_viral ON trends(viral_potential);

        CREATE TABLE IF NOT EXISTS tweets (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            trend_id      INTEGER NOT NULL REFERENCES trends(id),
            run_id        INTEGER NOT NULL REFERENCES runs(id),
            tweet_type    TEXT NOT NULL,
            content       TEXT NOT NULL,
            char_count    INTEGER DEFAULT 0,
            is_thread     INTEGER DEFAULT 0,
            thread_order  INTEGER DEFAULT 0,
            status        TEXT DEFAULT '대기중',
            saved_to      TEXT DEFAULT '[]',
            generated_at  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tweets_trend ON tweets(trend_id);
        CREATE INDEX IF NOT EXISTS idx_tweets_status ON tweets(status);
    """)
    conn.commit()

    # v2.1 마이그레이션: content_type 컬럼 추가 (기존 DB 호환)
    try:
        conn.execute("SELECT content_type FROM tweets LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE tweets ADD COLUMN content_type TEXT DEFAULT 'short'")
        conn.commit()
        log.info("DB 마이그레이션: tweets.content_type 컬럼 추가")


log = logging.getLogger(__name__)


def save_run(conn: sqlite3.Connection, run: RunResult) -> int:
    """실행 기록 저장. run row id 반환."""
    cursor = conn.execute(
        """INSERT INTO runs (run_uuid, started_at, country, trends_collected,
           trends_scored, tweets_generated, tweets_saved, alerts_sent, errors)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run.run_id,
            run.started_at.isoformat(),
            run.country,
            run.trends_collected,
            run.trends_scored,
            run.tweets_generated,
            run.tweets_saved,
            run.alerts_sent,
            json.dumps(run.errors, ensure_ascii=False),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def update_run(conn: sqlite3.Connection, run: RunResult, row_id: int) -> None:
    """실행 기록 업데이트 (완료 시)."""
    conn.execute(
        """UPDATE runs SET finished_at=?, trends_collected=?, trends_scored=?,
           tweets_generated=?, tweets_saved=?, alerts_sent=?, errors=?
           WHERE id=?""",
        (
            run.finished_at.isoformat() if run.finished_at else None,
            run.trends_collected,
            run.trends_scored,
            run.tweets_generated,
            run.tweets_saved,
            run.alerts_sent,
            json.dumps(run.errors, ensure_ascii=False),
            row_id,
        ),
    )
    conn.commit()


def save_trend(conn: sqlite3.Connection, trend: ScoredTrend, run_id: int) -> int:
    """스코어링된 트렌드 저장. trend row id 반환."""
    cursor = conn.execute(
        """INSERT INTO trends (run_id, keyword, rank, volume_raw, volume_numeric,
           viral_potential, trend_acceleration, top_insight, suggested_angles,
           best_hook_starter, country, sources, twitter_context, reddit_context,
           news_context, scored_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            trend.keyword,
            trend.rank,
            str(trend.volume_last_24h),
            trend.volume_last_24h,
            trend.viral_potential,
            trend.trend_acceleration,
            trend.top_insight,
            json.dumps(trend.suggested_angles, ensure_ascii=False),
            trend.best_hook_starter,
            trend.country,
            json.dumps([s.value for s in trend.sources], ensure_ascii=False),
            trend.context.twitter_insight if trend.context else "",
            trend.context.reddit_insight if trend.context else "",
            trend.context.news_insight if trend.context else "",
            trend.scored_at.isoformat(),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def save_tweet(
    conn: sqlite3.Connection,
    tweet: GeneratedTweet,
    trend_id: int,
    run_id: int,
    saved_to: list[str] | None = None,
) -> int:
    """생성된 트윗 저장."""
    cursor = conn.execute(
        """INSERT INTO tweets (trend_id, run_id, tweet_type, content, char_count,
           is_thread, thread_order, status, saved_to, generated_at, content_type)
           VALUES (?, ?, ?, ?, ?, 0, 0, '대기중', ?, ?, ?)""",
        (
            trend_id,
            run_id,
            tweet.tweet_type,
            tweet.content,
            tweet.char_count,
            json.dumps(saved_to or ["sqlite"], ensure_ascii=False),
            datetime.now().isoformat(),
            tweet.content_type,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def save_thread(
    conn: sqlite3.Connection,
    thread: GeneratedThread,
    trend_id: int,
    run_id: int,
) -> list[int]:
    """쓰레드의 각 트윗을 저장. tweet row id 리스트 반환."""
    ids = []
    for i, text in enumerate(thread.tweets):
        cursor = conn.execute(
            """INSERT INTO tweets (trend_id, run_id, tweet_type, content, char_count,
               is_thread, thread_order, status, saved_to, generated_at)
               VALUES (?, ?, '쓰레드', ?, ?, 1, ?, '대기중', '["sqlite"]', ?)""",
            (trend_id, run_id, text, len(text), i, datetime.now().isoformat()),
        )
        ids.append(cursor.lastrowid)
    conn.commit()
    return ids


def get_trend_history(
    conn: sqlite3.Connection, keyword: str, days: int = 7
) -> list[dict]:
    """특정 키워드의 과거 등장 기록 조회."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT keyword, rank, viral_potential, trend_acceleration,
           top_insight, scored_at
           FROM trends WHERE keyword = ? AND scored_at >= ?
           ORDER BY scored_at DESC""",
        (keyword, cutoff),
    ).fetchall()
    return [dict(r) for r in rows]


def get_recent_trends(
    conn: sqlite3.Connection, days: int = 7, min_score: int = 0
) -> list[dict]:
    """최근 N일 트렌드 조회 (최소 점수 필터)."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT keyword, rank, viral_potential, trend_acceleration,
           top_insight, country, scored_at
           FROM trends WHERE scored_at >= ? AND viral_potential >= ?
           ORDER BY viral_potential DESC""",
        (cutoff, min_score),
    ).fetchall()
    return [dict(r) for r in rows]


def get_recently_processed_keywords(
    conn: sqlite3.Connection, hours: int = 3
) -> set[str]:
    """최근 N시간 이내 처리된 키워드 목록 반환 (중복 필터용)."""
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    rows = conn.execute(
        "SELECT DISTINCT keyword FROM trends WHERE scored_at >= ?",
        (cutoff,),
    ).fetchall()
    return {row["keyword"] for row in rows}


def get_trend_stats(conn: sqlite3.Connection) -> dict:
    """전체 통계: 총 실행 수, 총 트렌드 수, 평균 점수 등."""
    stats = {}
    row = conn.execute("SELECT COUNT(*) as cnt FROM runs").fetchone()
    stats["total_runs"] = row["cnt"]
    row = conn.execute(
        "SELECT COUNT(*) as cnt, AVG(viral_potential) as avg_score FROM trends"
    ).fetchone()
    stats["total_trends"] = row["cnt"]
    stats["avg_viral_score"] = round(row["avg_score"] or 0, 1)
    row = conn.execute("SELECT COUNT(*) as cnt FROM tweets").fetchone()
    stats["total_tweets"] = row["cnt"]
    return stats
