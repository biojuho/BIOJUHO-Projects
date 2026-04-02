"""발행 후 실측 성과 수집 스크립트.

발행 48시간 후 X API에서 실제 참여 데이터를 수집하고,
content_actual_performance 테이블에 저장한다.

Usage:
    python scripts/collect_post_performance.py
    python scripts/collect_post_performance.py --hours 72 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── PYTHONPATH ──
_CIE_DIR = Path(__file__).resolve().parents[1]
if str(_CIE_DIR) not in sys.path:
    sys.path.insert(0, str(_CIE_DIR))

from config import CIEConfig
from loguru import logger as log


# ── 성과 테이블 스키마 ──
_PERF_SCHEMA = """\
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
"""


def ensure_perf_table(conn: sqlite3.Connection) -> None:
    """content_actual_performance 테이블이 없으면 생성한다."""
    try:
        conn.execute("SELECT 1 FROM content_actual_performance LIMIT 1")
    except sqlite3.OperationalError:
        conn.executescript(_PERF_SCHEMA)
        conn.commit()
        log.info("content_actual_performance 테이블 생성 완료")


def get_published_contents(conn: sqlite3.Connection, hours: int = 48) -> list[dict]:
    """발행 후 hours시간 이상 경과했지만 아직 성과 미수집인 콘텐츠 목록."""
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    rows = conn.execute(
        """SELECT gc.id, gc.platform, gc.content_type, gc.publish_target,
                  gc.notion_page_id, gc.published_at, gc.title
           FROM generated_contents gc
           LEFT JOIN content_actual_performance cap ON gc.id = cap.content_id
           WHERE gc.published = 1
             AND gc.published_at <= ?
             AND cap.id IS NULL
           ORDER BY gc.published_at DESC
           LIMIT 50""",
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_x_metrics(tweet_id: str, config: CIEConfig) -> dict | None:
    """X API v2로 트윗의 공개 메트릭을 가져온다.

    Returns:
        {"impressions", "likes", "retweets", "quotes", "replies", "bookmarks"}
        or None on failure.
    """
    if not config.x_access_token:
        return None

    try:
        import httpx
    except ImportError:
        log.warning("httpx 미설치 — X API 호출 불가")
        return None

    url = f"https://api.x.com/2/tweets/{tweet_id}"
    params = {"tweet.fields": "public_metrics"}
    headers = {"Authorization": f"Bearer {config.x_access_token}"}

    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code != 200:
            log.warning(f"X API {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json().get("data", {})
        pm = data.get("public_metrics", {})
        return {
            "impressions": pm.get("impression_count", 0),
            "likes": pm.get("like_count", 0),
            "retweets": pm.get("retweet_count", 0),
            "quotes": pm.get("quote_count", 0),
            "replies": pm.get("reply_count", 0),
            "bookmarks": pm.get("bookmark_count", 0),
        }
    except Exception as e:
        log.warning(f"X API 호출 실패: {e}")
        return None


def calc_engagement_rate(metrics: dict) -> float:
    """ER = (likes + retweets + quotes + replies + bookmarks) / impressions."""
    impressions = metrics.get("impressions", 0)
    if impressions == 0:
        return 0.0
    engagements = (
        metrics.get("likes", 0)
        + metrics.get("retweets", 0)
        + metrics.get("quotes", 0)
        + metrics.get("replies", 0)
        + metrics.get("bookmarks", 0)
    )
    return round(engagements / impressions * 100, 4)


def save_performance(conn: sqlite3.Connection, content_id: int, platform: str,
                     content_type: str, tweet_id: str, metrics: dict) -> None:
    """수집된 성과를 DB에 저장한다."""
    er = calc_engagement_rate(metrics)
    conn.execute(
        """INSERT OR REPLACE INTO content_actual_performance
           (content_id, platform, content_type, tweet_id,
            impressions, likes, retweets, quotes, replies, bookmarks,
            engagement_rate, collected_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            content_id, platform, content_type, tweet_id,
            metrics.get("impressions", 0),
            metrics.get("likes", 0),
            metrics.get("retweets", 0),
            metrics.get("quotes", 0),
            metrics.get("replies", 0),
            metrics.get("bookmarks", 0),
            er,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    log.info(f"  ✅ 성과 저장: content_id={content_id} ER={er:.2f}% imp={metrics.get('impressions', 0)}")


def update_golden_references(conn: sqlite3.Connection, config: CIEConfig) -> int:
    """상위 성과 콘텐츠를 GDT golden_references에 자동 반영한다.

    조건: ER >= 상위 10% AND impressions >= 500
    """
    rows = conn.execute(
        """SELECT cap.content_id, gc.body, gc.content_type,
                  cap.engagement_rate, cap.impressions
           FROM content_actual_performance cap
           JOIN generated_contents gc ON gc.id = cap.content_id
           WHERE cap.impressions >= 500
           ORDER BY cap.engagement_rate DESC
           LIMIT 5"""
    ).fetchall()

    if not rows:
        return 0

    # 상위 10% ER 임계값 계산
    all_ers = conn.execute(
        "SELECT engagement_rate FROM content_actual_performance WHERE impressions >= 100"
    ).fetchall()
    if len(all_ers) < 5:
        threshold = 0.0  # 데이터 부족 시 전부 후보
    else:
        sorted_ers = sorted([r["engagement_rate"] for r in all_ers], reverse=True)
        threshold = sorted_ers[max(0, len(sorted_ers) // 10)]

    updated = 0
    for row in rows:
        if row["engagement_rate"] >= threshold:
            log.info(
                f"  🏆 Golden candidate: id={row['content_id']} "
                f"ER={row['engagement_rate']:.2f}% imp={row['impressions']}"
            )
            updated += 1

    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="발행 콘텐츠 실측 성과 수집")
    parser.add_argument("--hours", type=int, default=48, help="발행 후 경과 시간 (기본: 48)")
    parser.add_argument("--dry-run", action="store_true", help="수집 없이 대상 목록만 확인")
    args = parser.parse_args()

    log.remove()
    log.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:7} | {message}")

    config = CIEConfig()
    from storage.local_db import get_connection
    conn = get_connection(config)

    ensure_perf_table(conn)

    targets = get_published_contents(conn, hours=args.hours)
    log.info(f"📊 성과 수집 대상: {len(targets)}건 (발행 후 {args.hours}h 경과)")

    if not targets:
        log.info("  수집할 콘텐츠가 없습니다.")
        conn.close()
        return

    if args.dry_run:
        for t in targets:
            log.info(f"  [DRY] id={t['id']} {t['platform']}/{t['content_type']} 발행: {t['published_at']}")
        conn.close()
        return

    collected = 0
    for t in targets:
        platform = t["platform"]
        if platform == "x" and t.get("notion_page_id"):
            # X 발행 시 tweet_id가 notion_page_id에 저장될 수 있음
            metrics = fetch_x_metrics(t["notion_page_id"], config)
            if metrics:
                save_performance(conn, t["id"], platform, t["content_type"],
                                 t["notion_page_id"], metrics)
                collected += 1
        else:
            log.debug(f"  건너뜀: id={t['id']} ({platform}) — API 미지원 또는 ID 없음")

    log.info(f"📊 수집 완료: {collected}/{len(targets)}건")

    # Golden Reference 후보 업데이트
    golden = update_golden_references(conn, config)
    if golden:
        log.info(f"🏆 Golden Reference 후보: {golden}건")

    conn.close()


if __name__ == "__main__":
    main()
