"""2단계 — 플랫폼별 규제 점검 + 통합 체크리스트 생성."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger as log

from collectors.base import llm_analyze
from prompts.regulation_check import (
    REGULATION_CHECK_SYSTEM,
    build_regulation_prompt,
)
from storage.models import RegulationReport, UnifiedChecklist

if TYPE_CHECKING:
    from config import CIEConfig


# ───────────────────────────────────────────────────
#  개별 플랫폼 규제 점검
# ───────────────────────────────────────────────────

async def check_platform_regulation(
    platform: str,
    config: CIEConfig,
) -> RegulationReport:
    """단일 플랫폼의 규제/알고리즘을 점검한다."""
    log.info(f"🔍 [2단계] {platform.upper()} 규제 점검 시작...")

    prompt = build_regulation_prompt(platform, config.regulation_lookback_days)
    data = await llm_analyze(
        REGULATION_CHECK_SYSTEM,
        prompt,
        tier=config.regulation_tier,
    )

    report = RegulationReport(
        platform=platform,
        policy_changes=data.get("policy_changes", []),
        penalty_triggers=data.get("penalty_triggers", []),
        algorithm_preferences=data.get("algorithm_preferences", []),
        do_list=data.get("do_list", []),
        dont_list=data.get("dont_list", []),
        checked_at=datetime.now(),
        raw_response=str(data),
    )

    log.info(
        f"  ✅ {platform.upper()} 규제 점검 완료 — "
        f"DO {len(report.do_list)}건 / DON'T {len(report.dont_list)}건"
    )
    return report


async def check_all_regulations(
    config: CIEConfig,
) -> list[RegulationReport]:
    """모든 대상 플랫폼의 규제를 병렬 점검한다."""
    tasks = [
        check_platform_regulation(p, config)
        for p in config.platforms
    ]
    return await asyncio.gather(*tasks, return_exceptions=False)


# ───────────────────────────────────────────────────
#  통합 Do & Don't 체크리스트
# ───────────────────────────────────────────────────

def generate_unified_checklist(
    reports: list[RegulationReport],
) -> UnifiedChecklist:
    """여러 플랫폼의 규제 리포트를 통합 체크리스트로 변환한다."""
    do_items: list[dict] = []
    dont_items: list[dict] = []

    for report in reports:
        for action in report.do_list:
            do_items.append({
                "platform": report.platform,
                "action": action,
                "priority": "높음",
            })
        for action in report.dont_list:
            dont_items.append({
                "platform": report.platform,
                "action": action,
                "severity": "높음",
            })

    # 공통 DO/DON'T 식별 (2개 이상 플랫폼에 공통이면 "공통"으로 표시)
    _merge_common(do_items, "priority")
    _merge_common(dont_items, "severity")

    platforms = ", ".join(r.platform.upper() for r in reports)
    summary = (
        f"{platforms} 통합 체크리스트 — "
        f"DO {len(do_items)}건 / DON'T {len(dont_items)}건"
    )

    checklist = UnifiedChecklist(
        do_items=do_items,
        dont_items=dont_items,
        summary=summary,
    )

    log.info(f"📋 통합 체크리스트 생성 완료: {summary}")
    return checklist


def _merge_common(items: list[dict], extra_key: str) -> None:
    """동일한 action이 여러 플랫폼에 존재하면 '공통'으로 통합."""
    seen: dict[str, list[int]] = {}
    for i, item in enumerate(items):
        key = item["action"].strip().lower()
        seen.setdefault(key, []).append(i)

    indices_to_remove = set()
    for key, indices in seen.items():
        if len(indices) >= 2:
            # 첫 번째를 "공통"으로 변경하고 나머지 제거
            items[indices[0]]["platform"] = "공통"
            for idx in indices[1:]:
                indices_to_remove.add(idx)

    for idx in sorted(indices_to_remove, reverse=True):
        items.pop(idx)
