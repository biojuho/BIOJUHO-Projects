"""네이버 블로그 트렌드 수집기 — DataLab API + LLM 분석."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import httpx
from collectors.base import llm_analyze
from loguru import logger as log
from prompts.trend_collection import TREND_COLLECTION_SYSTEM, build_trend_prompt
from storage.models import PlatformTrend, PlatformTrendReport

if TYPE_CHECKING:
    from config import CIEConfig


async def collect_naver_trends(config: CIEConfig) -> PlatformTrendReport:
    """네이버 트렌드를 수집한다.

    1순위: 네이버 DataLab API (API 키 설정 시)
    2순위: LLM 기반 분석
    """
    log.info("📡 [1단계] 네이버 블로그 트렌드 수집 시작...")

    # DataLab API 시도
    if config.naver_client_id and config.naver_client_secret:
        datalab_trends = await _fetch_naver_datalab(config)
        if datalab_trends:
            log.info(f"  ✅ 네이버 DataLab에서 {len(datalab_trends)} 트렌드 수집")
            return PlatformTrendReport(
                platform="naver",
                trends=datalab_trends,
                key_insights=["네이버 DataLab API에서 실시간 급상승 검색어 로드"],
                collected_at=datetime.now(),
            )

    # LLM 분석 폴백
    log.info("  네이버 API 미설정/실패 → LLM 분석 모드")
    prompt = build_trend_prompt("naver", config.project_fields, config.trend_top_n)
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
        platform="naver",
        trends=trends,
        key_insights=data.get("key_insights", []),
        collected_at=datetime.now(),
        raw_response=str(data),
    )

    log.info(f"  ✅ 네이버 트렌드 {len(trends)}개 수집 완료")
    return report


async def _fetch_naver_datalab(config: CIEConfig) -> list[PlatformTrend] | None:
    """네이버 DataLab API로 급상승 검색어를 가져온다."""
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {
        "X-Naver-Client-Id": config.naver_client_id,
        "X-Naver-Client-Secret": config.naver_client_secret,
        "Content-Type": "application/json",
    }

    # 프로젝트 분야 기반 키워드 그룹
    keyword_groups = []
    for field in config.project_fields[:5]:
        keyword_groups.append(
            {
                "groupName": field,
                "keywords": [field],
            }
        )

    if not keyword_groups:
        return None

    from datetime import timedelta

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": "date",
        "keywordGroups": keyword_groups,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        trends = []
        for result in data.get("results", []):
            ratios = result.get("data", [])
            latest_ratio = ratios[-1].get("ratio", 0) if ratios else 0
            trends.append(
                PlatformTrend(
                    keyword=result.get("title", ""),
                    volume=int(latest_ratio * 10),
                    format_trend="블로그 포스트",
                    tone_trend="정보형",
                )
            )
        return trends if trends else None

    except Exception as e:
        log.warning(f"  네이버 DataLab API 실패: {e}")
        return None
