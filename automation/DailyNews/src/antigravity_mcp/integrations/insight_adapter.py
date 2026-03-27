"""
Insight Adapter — DailyNews Insight Generator Skill 통합 어댑터

.agent/skills/daily-insight-generator를 antigravity_mcp 파이프라인에 통합합니다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class InsightAdapter:
    """DailyNews Insight Generator Skill 통합 어댑터"""

    def __init__(self, *, llm_adapter: Any | None = None, state_store: Any | None = None):
        self.llm_adapter = llm_adapter
        self.state_store = state_store
        self._generator = None
        self._skill_available = self._check_skill_available()

    def _check_skill_available(self) -> bool:
        """Skill 파일 존재 여부 확인"""
        project_root = Path(__file__).resolve().parents[4]
        skill_path = project_root / ".agent" / "skills" / "daily-insight-generator" / "generator.py"
        return skill_path.exists()

    def is_available(self) -> bool:
        """Skill 사용 가능 여부"""
        return self._skill_available

    async def generate_insights(
        self,
        category: str,
        articles: list[dict[str, str]],
        window_name: str = "morning",
        max_insights: int = 4,
    ) -> dict[str, Any]:
        """
        뉴스 기사로부터 인사이트 생성

        Args:
            category: 카테고리 (예: Tech, Economy_KR)
            articles: [{"title": "...", "summary": "...", "link": "..."}]
            window_name: 시간대 (morning/evening)
            max_insights: 최대 인사이트 수

        Returns:
            {
                "insights": [...],
                "x_long_form": "...",
                "validation_summary": {...}
            }
        """
        if not self.is_available():
            logger.warning("Insight generator skill not available")
            return {
                "insights": [],
                "x_long_form": "",
                "validation_summary": {"total_insights": 0, "passed": 0, "failed": 0},
                "error": "Skill not available",
            }

        if not articles:
            logger.warning("No articles provided for insight generation")
            return {
                "insights": [],
                "x_long_form": "",
                "validation_summary": {"total_insights": 0, "passed": 0, "failed": 0},
            }

        try:
            # generator.py 동적 임포트
            if self._generator is None:
                project_root = Path(__file__).resolve().parents[4]
                skill_dir = project_root / ".agent" / "skills" / "daily-insight-generator"
                if str(skill_dir) not in sys.path:
                    sys.path.insert(0, str(skill_dir))

                from generator import InsightGenerator

                self._generator = InsightGenerator(llm_adapter=self.llm_adapter, state_store=self.state_store)

            # 인사이트 생성
            result = await self._generator.generate_insights(
                category=category,
                articles=articles,
                window_name=window_name,
                max_insights=max_insights,
            )

            logger.info(
                "Generated %d insights for %s (%d passed validation)",
                len(result["insights"]),
                category,
                result["validation_summary"]["passed"],
            )

            return result

        except Exception as exc:
            logger.error("Insight generation failed: %s", exc, exc_info=True)
            return {
                "insights": [],
                "x_long_form": "",
                "validation_summary": {"total_insights": 0, "passed": 0, "failed": 0},
                "error": str(exc),
            }

    async def generate_insight_report(
        self,
        category: str,
        articles: list[dict[str, str]],
        window_name: str = "morning",
    ) -> tuple[list[str], list[str], str]:
        """
        파이프라인 통합용 간소화 인터페이스

        Returns:
            (summary_lines, insights, x_long_form)
        """
        result = await self.generate_insights(
            category=category,
            articles=articles,
            window_name=window_name,
            max_insights=4,
        )

        # 검증 통과한 인사이트만 추출
        summary_lines = []
        insights = []

        for idx, insight in enumerate(result.get("insights", []), 1):
            if not insight.get("validation_passed", False):
                continue

            title = insight.get("title", "Untitled")
            content = insight.get("content", "")

            summary_lines.append(f"{idx}. {title}")
            insights.append(f"[인사이트 {idx}] {content[:200]}...")

        x_long_form = result.get("x_long_form", "")

        return summary_lines, insights, x_long_form


def main():
    """테스트용 메인 함수"""
    import asyncio

    logging.basicConfig(level=logging.INFO)

    # 샘플 데이터
    sample_articles = [
        {
            "title": "엔비디아, H100 GPU 공급 부족으로 납품 지연",
            "summary": "엔비디아의 AI 칩 H100에 대한 수요가 공급을 크게 초과하며 평균 6개월 이상 대기 발생",
            "link": "https://example.com/nvidia-h100",
        },
        {
            "title": "AMD, AI 칩 MI300X 정식 출시 발표",
            "summary": "AMD가 엔비디아에 대항하는 AI 가속기 MI300X를 2월 공식 출시",
            "link": "https://example.com/amd-mi300x",
        },
        {
            "title": "구글, TPU v5 대량 생산 시작",
            "summary": "구글이 자체 AI 칩 TPU v5를 1월부터 대량 생산하며 클라우드 고객에게 제공 시작",
            "link": "https://example.com/google-tpu-v5",
        },
    ]

    async def test():
        adapter = InsightAdapter()
        if not adapter.is_available():
            print("Insight generator skill is not available. Install the skill first.")
            return

        result = await adapter.generate_insights(
            category="Tech",
            articles=sample_articles,
            window_name="morning",
            max_insights=3,
        )

        print("\n=== Insight Generation Result ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    asyncio.run(test())


if __name__ == "__main__":
    main()
