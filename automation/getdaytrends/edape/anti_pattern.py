"""
EDAPE — Anti-Pattern Suppressor

성과 데이터에서 하위 N% 패턴을 식별하여
프롬프트에서 명시적으로 금지할 패턴 목록을 반환한다.

원칙:
  - 데이터가 충분하지 않은 패턴(min_samples 미달)은 억제 대상에서 제외
  - 탐험(exploration) 예산을 보호하기 위해 전체 패턴의 최대 30%만 억제
"""

from __future__ import annotations

import inspect
import math
from typing import Any

from loguru import logger as log


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


class AntiPatternSuppressor:
    """하위 성과 패턴 식별 및 억제 목록 생성."""

    MAX_SUPPRESSION_RATIO: float = 0.30  # 전체 패턴 중 최대 30%만 억제

    def __init__(
        self,
        lookback_days: int = 7,
        suppression_percentile: float = 0.20,
        min_samples: int = 5,
    ) -> None:
        self.lookback_days = lookback_days
        self.percentile = suppression_percentile
        self.min_samples = min_samples

    async def analyze(self, tracker: Any) -> dict[str, list[str]]:
        """
        tracker에서 앵글/훅/킥 성과를 읽고 하위 percentile 패턴을 반환.

        Returns:
            {"angles": [...], "hooks": [...], "kicks": [...]}
        """
        result: dict[str, list[str]] = {
            "angles": [],
            "hooks": [],
            "kicks": [],
        }

        try:
            angle_stats = await _maybe_await(tracker.get_angle_performance(self.lookback_days))
            result["angles"] = self._find_bottom(angle_stats)
        except Exception as e:
            log.debug(f"[AntiPattern] 앵글 분석 실패: {e}")

        try:
            hook_stats = await _maybe_await(tracker.get_hook_performance(self.lookback_days))
            result["hooks"] = self._find_bottom(hook_stats)
        except Exception as e:
            log.debug(f"[AntiPattern] 훅 분석 실패: {e}")

        try:
            kick_stats = await _maybe_await(tracker.get_kick_performance(self.lookback_days))
            result["kicks"] = self._find_bottom(kick_stats)
        except Exception as e:
            log.debug(f"[AntiPattern] 킥 분석 실패: {e}")

        total = sum(len(v) for v in result.values())
        if total:
            log.debug(f"[AntiPattern] 억제 대상: {total}개 패턴")

        return result

    def _find_bottom(self, stats: dict) -> list[str]:
        """
        stats dict에서 하위 percentile에 해당하는 패턴 이름 반환.
        min_samples 미달 패턴은 제외.
        """
        # 충분한 데이터가 있는 패턴만 필터
        qualified = [
            (name, stat)
            for name, stat in stats.items()
            if stat.total_tweets >= self.min_samples
            and stat.avg_engagement_rate > 0
        ]

        if len(qualified) < 3:
            # 데이터 부족 시 억제 안 함 (탐험 보호)
            return []

        # engagement rate 오름차순 정렬
        qualified.sort(key=lambda x: x[1].avg_engagement_rate)

        # 하위 percentile 개수 계산 (최대 30% 제한)
        bottom_count = max(1, math.floor(len(qualified) * self.percentile))
        max_allowed = max(1, math.floor(len(qualified) * self.MAX_SUPPRESSION_RATIO))
        bottom_count = min(bottom_count, max_allowed)

        return [name for name, _ in qualified[:bottom_count]]
