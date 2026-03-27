"""Threads(Meta) 트렌드 수집기."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger as log

from collectors.base import llm_analyze
from prompts.trend_collection import TREND_COLLECTION_SYSTEM, build_trend_prompt
from storage.models import PlatformTrend, PlatformTrendReport

if TYPE_CHECKING:
    from config import CIEConfig


async def collect_threads_trends(config: CIEConfig) -> PlatformTrendReport:
    """Threads 트렌드를 LLM 분석으로 수집한다.

    Threads API가 제한적이므로 LLM 기반 분석을 기본으로 사용.
    향후 Meta Graph API 연동 시 확장 가능.
    """
    log.info("📡 [1단계] Threads 트렌드 수집 시작...")

    prompt = build_trend_prompt("threads", config.project_fields, config.trend_top_n)
    data = await llm_analyze(
        TREND_COLLECTION_SYSTEM,
        prompt,
        tier=config.trend_analysis_tier,
    )

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

    report = PlatformTrendReport(
        platform="threads",
        trends=trends,
        key_insights=data.get("key_insights", []),
        collected_at=datetime.now(),
        raw_response=str(data),
    )

    log.info(f"  ✅ Threads 트렌드 {len(trends)}개 수집 완료")
    return report
