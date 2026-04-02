"""GetDayTrends DB 딥 연동 브리지.

getdaytrends의 SQLite/PostgreSQL DB에서 풍부한 트렌드 데이터를 읽어
CIE 파이프라인에 주입한다.

활용 테이블:
  - trends:  키워드, viral_potential, sentiment, 교차검증 신뢰도
  - tweets:  기존 생성 콘텐츠 성과 (impressions, engagements)
  - content_feedback: QA 점수 이력 → 고성과 패턴 학습
  - posting_time_stats: 카테고리별 최적 게시 시간
  - watchlist_hits: 감시 키워드 알림
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger as log

if TYPE_CHECKING:
    from config import CIEConfig


# ── 데이터 모델 ──────────────────────────────────────


@dataclass
class RichTrend:
    """GetDayTrends에서 가져온 풍부한 트렌드 데이터."""

    keyword: str
    rank: int = 0
    viral_potential: int = 0
    category: str = ""
    sentiment: str = "neutral"
    confidence: int = 0  # cross_source_confidence
    best_hook_starter: str = ""
    suggested_angles: list[str] = field(default_factory=list)
    top_insight: str = ""
    trend_acceleration: str = "+0%"
    # 성과 데이터 (tweets JOIN)
    avg_engagement_rate: float = 0.0
    total_impressions: int = 0
    # 메타
    scored_at: str = ""


@dataclass
class PostingTimeSlot:
    """카테고리별 최적 게시 시간."""

    category: str
    hour: int
    avg_score: float = 0.0
    sample_count: int = 0


@dataclass
class GdtBridgeResult:
    """GDT Bridge 통합 결과."""

    trends: list[RichTrend] = field(default_factory=list)
    posting_slots: list[PostingTimeSlot] = field(default_factory=list)
    top_keywords: list[str] = field(default_factory=list)
    watchlist_alerts: list[str] = field(default_factory=list)
    db_path: str = ""
    loaded_at: datetime = field(default_factory=datetime.now)


# ── DB 경로 탐지 ──────────────────────────────────────


def _find_gdt_db(config: CIEConfig) -> Path | None:
    """GetDayTrends DB 파일을 자동 탐지한다."""
    # 1. 환경변수 오버라이드
    if hasattr(config, "gdt_db_path") and config.gdt_db_path:
        p = Path(config.gdt_db_path)
        if p.exists():
            return p

    # 2. 기본 위치
    candidates = [
        config.project_root / "getdaytrends" / "data" / "trends.db",
        config.project_root / "getdaytrends" / "data" / "getdaytrends.db",
    ]
    for p in candidates:
        if p.exists():
            return p

    return None


# ── 쿼리 함수들 ──────────────────────────────────────


def load_rich_trends(
    conn: sqlite3.Connection,
    hours: int = 24,
    limit: int = 15,
) -> list[RichTrend]:
    """최근 N시간 이내의 트렌드를 tweets 성과 데이터와 함께 로드한다."""
    query = """
        SELECT
            t.keyword,
            t.rank,
            t.viral_potential,
            COALESCE(t.top_insight, '') AS top_insight,
            COALESCE(t.suggested_angles, '[]') AS suggested_angles,
            COALESCE(t.best_hook_starter, '') AS best_hook_starter,
            COALESCE(t.sentiment, 'neutral') AS sentiment,
            COALESCE(t.cross_source_confidence, 0) AS confidence,
            COALESCE(t.trend_acceleration, '+0%') AS trend_acceleration,
            t.scored_at,
            COALESCE(AVG(tw.engagement_rate), 0) AS avg_eng,
            COALESCE(SUM(tw.impressions), 0) AS total_imp
        FROM trends t
        LEFT JOIN tweets tw ON tw.trend_id = t.id AND tw.status != '대기중'
        WHERE t.scored_at >= datetime('now', ? || ' hours')
        GROUP BY t.id
        ORDER BY t.viral_potential DESC
        LIMIT ?
    """
    try:
        rows = conn.execute(query, (f"-{hours}", limit)).fetchall()
    except Exception as e:
        log.warning(f"리치 트렌드 로드 실패 (fallback): {e}")
        # 테이블 구조가 다를 경우 단순 쿼리
        return _load_simple_trends(conn, hours, limit)

    import json

    results = []
    for row in rows:
        angles_raw = row["suggested_angles"]
        try:
            angles = json.loads(angles_raw) if angles_raw else []
        except (json.JSONDecodeError, TypeError):
            angles = []

        results.append(
            RichTrend(
                keyword=row["keyword"],
                rank=row["rank"] or 0,
                viral_potential=row["viral_potential"] or 0,
                top_insight=row["top_insight"],
                suggested_angles=angles,
                best_hook_starter=row["best_hook_starter"],
                sentiment=row["sentiment"],
                confidence=row["confidence"],
                trend_acceleration=row["trend_acceleration"],
                scored_at=row["scored_at"] or "",
                avg_engagement_rate=row["avg_eng"],
                total_impressions=int(row["total_imp"]),
            )
        )
    return results


def _load_simple_trends(
    conn: sqlite3.Connection,
    hours: int = 24,
    limit: int = 15,
) -> list[RichTrend]:
    """테이블 구조가 다를 경우의 폴백 단순 쿼리."""
    rows = conn.execute(
        """SELECT keyword, viral_potential, scored_at
           FROM trends
           WHERE scored_at >= datetime('now', ? || ' hours')
           ORDER BY viral_potential DESC
           LIMIT ?""",
        (f"-{hours}", limit),
    ).fetchall()
    return [
        RichTrend(
            keyword=row["keyword"],
            viral_potential=row["viral_potential"] or 0,
            scored_at=row["scored_at"] or "",
        )
        for row in rows
    ]


def load_posting_stats(conn: sqlite3.Connection) -> list[PostingTimeSlot]:
    """카테고리별 최적 게시 시간을 로드한다."""
    try:
        rows = conn.execute(
            """SELECT category, hour,
                      total_score / MAX(sample_count, 1) AS avg_score,
                      sample_count
               FROM posting_time_stats
               WHERE sample_count >= 3
               ORDER BY avg_score DESC
               LIMIT 20"""
        ).fetchall()
        return [
            PostingTimeSlot(
                category=row["category"],
                hour=row["hour"],
                avg_score=row["avg_score"],
                sample_count=row["sample_count"],
            )
            for row in rows
        ]
    except Exception as e:
        log.debug(f"게시 시간 통계 없음: {e}")
        return []


def load_top_performing_keywords(
    conn: sqlite3.Connection,
    days: int = 30,
    limit: int = 10,
) -> list[str]:
    """과거 N일간 고성과(QA 점수 + 참여율) 키워드를 로드한다."""
    try:
        rows = conn.execute(
            """SELECT keyword, AVG(qa_score) AS avg_qa
               FROM content_feedback
               WHERE created_at >= datetime('now', ? || ' days')
                 AND qa_score > 70
               GROUP BY keyword
               ORDER BY avg_qa DESC
               LIMIT ?""",
            (f"-{days}", limit),
        ).fetchall()
        return [row["keyword"] for row in rows]
    except Exception as e:
        log.debug(f"고성과 키워드 없음: {e}")
        return []


def load_watchlist_alerts(
    conn: sqlite3.Connection,
    hours: int = 48,
) -> list[str]:
    """최근 감시 목록 히트 키워드."""
    try:
        rows = conn.execute(
            """SELECT DISTINCT keyword
               FROM watchlist_hits
               WHERE detected_at >= datetime('now', ? || ' hours')
               ORDER BY viral_potential DESC
               LIMIT 5""",
            (f"-{hours}",),
        ).fetchall()
        return [row["keyword"] for row in rows]
    except Exception as e:
        log.debug(f"watchlist 없음: {e}")
        return []


# ── 역피드백 쓰기 ──────────────────────────────────────


def write_content_feedback(
    config: CIEConfig,
    keyword: str,
    category: str,
    qa_score: float,
    regenerated: bool = False,
    reason: str = "",
) -> bool:
    """CIE QA 결과를 GetDayTrends content_feedback 테이블에 역주입한다.

    GetDayTrends의 PerformanceTracker.get_optimal_pattern_weights()가
    이 데이터를 활용하여 프롬프트 패턴 가중치를 개선한다.

    Returns:
        True if written successfully, False on error or DB not found.
    """
    db_path = _find_gdt_db(config)
    if db_path is None:
        return False

    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """INSERT INTO content_feedback
               (keyword, category, qa_score, regenerated, reason, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (keyword, category, qa_score, int(regenerated), reason),
        )
        conn.commit()
        log.debug(f"  ↩️ GDT 역피드백: {keyword} / QA={qa_score:.0f} / regen={regenerated}")
        return True
    except Exception as e:
        log.warning(f"  ⚠️ GDT content_feedback 쓰기 실패 (피드백 루프 단절): {e}")
        return False
    finally:
        if conn is not None:
            conn.close()


def write_content_feedback_batch(
    config: CIEConfig,
    items: list[dict],
) -> int:
    """콘텐츠 피드백을 배치로 역주입한다.

    Args:
        items: [{"keyword", "category", "qa_score", "regenerated", "reason"}, ...]

    Returns:
        Number of rows written.
    """
    if not items:
        return 0

    db_path = _find_gdt_db(config)
    if db_path is None:
        return 0

    written = 0
    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        for item in items:
            try:
                conn.execute(
                    """INSERT INTO content_feedback
                       (keyword, category, qa_score, regenerated, reason, created_at)
                       VALUES (?, ?, ?, ?, ?, datetime('now'))""",
                    (
                        item.get("keyword", ""),
                        item.get("category", ""),
                        float(item.get("qa_score", 0.0)),
                        int(item.get("regenerated", False)),
                        item.get("reason", ""),
                    ),
                )
                written += 1
            except Exception as e:
                log.warning(f"  ⚠️ content_feedback 행 쓰기 실패: {e}")
        conn.commit()
        if written:
            log.info(f"  ↩️ GDT 역피드백 배치: {written}건 주입 완료")
    except Exception as e:
        log.warning(f"  ⚠️ GDT content_feedback 배치 실패: {e}")
    finally:
        if conn is not None:
            conn.close()

    return written


# ── 통합 로드 함수 ──────────────────────────────────────


def load_all(config: CIEConfig) -> GdtBridgeResult | None:
    """GetDayTrends DB에서 모든 데이터를 통합 로드한다.

    DB가 없거나 접근 실패 시 None 반환 (graceful fallback).
    """
    db_path = _find_gdt_db(config)
    if db_path is None:
        log.info("  ℹ️ GetDayTrends DB 미발견 → LLM 모드로 전환")
        return None

    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        trends = load_rich_trends(conn)
        posting_slots = load_posting_stats(conn)
        top_kw = load_top_performing_keywords(conn)
        watchlist = load_watchlist_alerts(conn)

        result = GdtBridgeResult(
            trends=trends,
            posting_slots=posting_slots,
            top_keywords=top_kw,
            watchlist_alerts=watchlist,
            db_path=str(db_path),
        )

        log.info(
            f"  ✅ GDT Bridge: {len(trends)} trends, "
            f"{len(posting_slots)} slots, "
            f"{len(top_kw)} top kw, "
            f"{len(watchlist)} watchlist"
        )
        return result

    except Exception as e:
        log.warning(f"  ⚠️ GDT Bridge 로드 실패: {e}")
        return None
    finally:
        if conn is not None:
            conn.close()
