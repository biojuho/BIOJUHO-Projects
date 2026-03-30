"""X(Twitter) 트렌드 수집기 — getdaytrends 딥 연동 (v2.0).

1순위: gdt_bridge를 통한 리치 데이터 로드
2순위: LLM 기반 실시간 분석
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from collectors.base import llm_analyze
from collectors.gdt_bridge import load_all as gdt_load_all
from loguru import logger as log
from prompts.trend_collection import TREND_COLLECTION_SYSTEM, build_trend_prompt
from storage.models import PlatformTrend, PlatformTrendReport

if TYPE_CHECKING:
    from config import CIEConfig


async def collect_x_trends(config: CIEConfig) -> PlatformTrendReport:
    """X 트렌드를 수집하고 CIE 포맷으로 변환한다.

    1순위: gdt_bridge → GetDayTrends DB 딥 연동 (v2.0)
    2순위: LLM 기반 실시간 분석
    """
    log.info("📡 [1단계] X 트렌드 수집 시작...")

    # GDT Bridge 딥 연동 시도
    gdt_result = gdt_load_all(config)
    if gdt_result and gdt_result.trends:
        trends = [
            PlatformTrend(
                keyword=t.keyword,
                volume=t.viral_potential * 100,
                format_trend="트윗/쓰레드",
                tone_trend=t.sentiment or "일반",
                project_connection=t.top_insight or "",
                sentiment=t.sentiment,
                confidence=t.confidence,
                hook_starter=t.best_hook_starter,
                optimal_post_hour=_best_hour_for(t.keyword, gdt_result.posting_slots),
            )
            for t in gdt_result.trends
        ]
        insights = [
            f"getdaytrends DB 딥 연동: {len(trends)} 트렌드 로드",
        ]
        if gdt_result.watchlist_alerts:
            insights.append(f"⚡ 감시 키워드 활성: {', '.join(gdt_result.watchlist_alerts)}")
        if gdt_result.top_keywords:
            insights.append(f"🏆 고성과 키워드: {', '.join(gdt_result.top_keywords[:5])}")

        log.info(f"  ✅ GDT Bridge: {len(trends)} 트렌드 로드 완료")
        return PlatformTrendReport(
            platform="x",
            trends=trends,
            key_insights=insights,
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


def _best_hour_for(keyword: str, slots: list) -> int:
    """키워드에 해당하는 최적 게시 시간을 반환한다."""
    if not slots:
        return -1
    # 가장 높은 평균 점수의 시간대 반환
    return slots[0].hour if slots else -1


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
