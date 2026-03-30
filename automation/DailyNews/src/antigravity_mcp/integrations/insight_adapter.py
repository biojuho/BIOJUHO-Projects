"""Insight Adapter — in-package DailyNews insight generation wrapper."""

from __future__ import annotations

import logging
from typing import Any

from antigravity_mcp.insights.generator import InsightGenerator

logger = logging.getLogger(__name__)


class InsightAdapter:
    """Thin compatibility wrapper around the packaged insight generator."""

    def __init__(self, *, llm_adapter: Any | None = None, state_store: Any | None = None):
        self.llm_adapter = llm_adapter
        self.state_store = state_store
        self._generator = InsightGenerator(llm_adapter=llm_adapter, state_store=state_store)

    def is_available(self) -> bool:
        return self._generator is not None

    async def generate_insights(
        self,
        category: str,
        articles: list[dict[str, str]],
        window_name: str = "morning",
        max_insights: int = 4,
    ) -> dict[str, Any]:
        result = await self._generator.generate_insights(
            category=category,
            articles=articles,
            window_name=window_name,
            max_insights=max_insights,
        )
        if result.get("error"):
            logger.warning("Insight generation degraded for %s: %s", category, result["error"])
        return result

    async def generate_insight_report(
        self,
        category: str,
        articles: list[dict[str, str]],
        window_name: str = "morning",
    ) -> tuple[list[str], list[str], str]:
        result = await self.generate_insights(
            category=category,
            articles=articles,
            window_name=window_name,
            max_insights=4,
        )

        summary_lines: list[str] = []
        insights: list[str] = []
        full_items: list[dict[str, Any]] = []

        for idx, insight in enumerate(result.get("insights", []), 1):
            if not insight.get("validation_passed", False):
                continue
            title = insight.get("title", "Untitled")
            content = (insight.get("content", "") or "").strip()
            summary_lines.append(f"{idx}. {title}")
            insights.append(f"[인사이트 {idx}] {content}")
            full_items.append(insight)

        x_long_form = result.get("x_long_form", "")
        result.setdefault("full_items", full_items)
        return summary_lines, insights, x_long_form
