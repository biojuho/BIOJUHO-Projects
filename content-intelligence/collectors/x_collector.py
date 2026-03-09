"""X(Twitter) 트렌드 수집기 — getdaytrends 연동."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger as log

from collectors.base import llm_analyze
from prompts.trend_collection import TREND_COLLECTION_SYSTEM, build_trend_prompt
from storage.models import PlatformTrend, PlatformTrendReport

if TYPE_CHECKING:
    from config import CIEConfig


async def collect_x_trends(config: CIEConfig) -> PlatformTrendReport:
    """X 트렌드를 수집하고 CIE 포맷으로 변환한다.

    1순위: getdaytrends의 최근 DB 데이터 활용 (이미 수집 중이므로)
    2순위: LLM 기반 실시간 분석
    """
    log.info("📡 [1단계] X 트렌드 수집 시작...")

    # getdaytrends DB에서 최근 트렌드 가져오기 시도
    trends_from_db = _try_getdaytrends_db(config)
    if trends_from_db:
        log.info(f"  ✅ getdaytrends DB에서 {len(trends_from_db)} 트렌드 로드")
        return PlatformTrendReport(
            platform="x",
            trends=trends_from_db,
            key_insights=["getdaytrends DB에서 실시간 트렌드 로드"],
            collected_at=datetime.now(),
        )

    # DB 미사용 시 LLM 분석
    log.info("  getdaytrends DB 미사용 → LLM 분석 모드")
    prompt = build_trend_prompt("x", config.project_fields, config.trend_top_n)
    data = await llm_analyze(
        TREND_COLLECTION_SYSTEM,
        prompt,
        tier=config.trend_analysis_tier,
    )

    return _parse_report("x", data)


def _try_getdaytrends_db(config: CIEConfig) -> list[PlatformTrend] | None:
    """getdaytrends의 SQLite DB에서 최근 트렌드를 로드한다."""
    import sqlite3
    from pathlib import Path

    db_path = config.project_root / "getdaytrends" / "data" / "trends.db"
    if not db_path.exists():
        return None

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT keyword, viral_potential, category, trend_acceleration,
                      top_insight
               FROM trends
               WHERE scored_at >= datetime('now', '-24 hours')
               ORDER BY viral_potential DESC
               LIMIT ?""",
            (10,),
        ).fetchall()
        conn.close()

        if not rows:
            return None

        return [
            PlatformTrend(
                keyword=row["keyword"],
                volume=row["viral_potential"] * 100,  # 추정치
                format_trend="트윗/쓰레드",
                tone_trend=row["category"] or "일반",
                project_connection=row["top_insight"] or "",
            )
            for row in rows
        ]
    except Exception as e:
        log.warning(f"  getdaytrends DB 접근 실패: {e}")
        return None


def _parse_report(platform: str, data: dict) -> PlatformTrendReport:
    """JSON 응답을 PlatformTrendReport로 변환."""
    trends = []
    for t in data.get("trends", []):
        trends.append(
            PlatformTrend(
                keyword=t.get("keyword", ""),
                hashtags=t.get("hashtags", []),
                volume=t.get("volume", 0),
                format_trend=t.get("format_trend", ""),
                tone_trend=t.get("tone_trend", ""),
                project_connection=t.get("project_connection", ""),
            )
        )

    return PlatformTrendReport(
        platform=platform,
        trends=trends,
        key_insights=data.get("key_insights", []),
        collected_at=datetime.now(),
        raw_response=str(data),
    )
