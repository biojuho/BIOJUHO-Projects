"""
TAP Analyzer — 차익거래 기회를 프롬프트 힌트 및 로그 리포트로 변환.

역할:
  1. ArbitrageOpportunity 리스트 → 파이프라인 로그 출력
  2. 프롬프트 주입 블록 생성 (EDAPE와 병합 가능)
  3. 특정 국가 대상 기회 필터링

Graceful Degradation:
  - 빈 리스트/None 입력 → 빈 문자열/빈 리스트 반환
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger as log

if TYPE_CHECKING:
    from .detector import ArbitrageOpportunity


class ArbitrageAnalyzer:
    """차익거래 기회를 가공하여 다운스트림에 제공."""

    # 프롬프트 블록에 포함할 최대 기회 수
    MAX_PROMPT_HINTS = 3

    def __init__(self, opportunities: list[ArbitrageOpportunity] | None = None):
        self._opps = opportunities or []

    @property
    def count(self) -> int:
        return len(self._opps)

    @property
    def top_opportunities(self) -> list[ArbitrageOpportunity]:
        return self._opps[:self.MAX_PROMPT_HINTS]

    def filter_for_country(self, country: str) -> list[ArbitrageOpportunity]:
        """특정 타겟 국가에 대한 기회만 필터링."""
        c = country.lower()
        return [o for o in self._opps if c in [tc.lower() for tc in o.target_countries]]

    def to_prompt_block(self, *, target_country: str = "") -> str:
        """프롬프트 주입 블록 생성.

        Args:
            target_country: 특정 국가 대상으로 필터링 (빈 문자열이면 전체)

        Returns:
            프롬프트 블록 문자열 (기회 없으면 빈 문자열)
        """
        opps = self.filter_for_country(target_country) if target_country else self._opps
        if not opps:
            return ""

        hints = opps[:self.MAX_PROMPT_HINTS]
        lines = [
            "\n═══ [TAP — 교차국가 선점 기회] ═══",
            f"감지된 차익거래 기회: {len(self._opps)}건 (상위 {len(hints)}건 표시)\n",
        ]
        for i, opp in enumerate(hints, 1):
            lines.append(f"  {i}. {opp.to_prompt_hint()}")

        lines.append(
            "\n▶ 위 선점 기회를 활용하여 해당 키워드에 대해 "
            "앞서가는 관점의 콘텐츠를 생성할 것."
        )
        lines.append("═══════════════════════════════════════════════")
        return "\n".join(lines)

    def log_summary(self) -> None:
        """파이프라인 로그에 차익거래 요약 출력."""
        if not self._opps:
            log.debug("[TAP] 교차국가 차익거래 기회 없음")
            return

        log.info(f"[TAP] 교차국가 차익거래 기회 {len(self._opps)}건 감지:")
        for opp in self._opps[:5]:
            targets = ", ".join(c.upper() for c in opp.target_countries)
            log.info(
                f"  '{opp.keyword}' — "
                f"{opp.source_country.upper()} → {targets} "
                f"(viral={opp.viral_score}, gap={opp.time_gap_hours:.1f}h, "
                f"priority={opp.priority:.1f})"
            )
