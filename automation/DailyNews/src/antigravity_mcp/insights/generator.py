from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from antigravity_mcp.insights.validator import InsightValidator

logger = logging.getLogger(__name__)


class InsightGenerator:
    def __init__(self, llm_adapter: Any | None = None, state_store: Any | None = None):
        self.llm_adapter = llm_adapter
        self.state_store = state_store
        self.validator = InsightValidator()

    async def generate_insights(
        self,
        category: str,
        articles: list[dict[str, str]],
        window_name: str = "morning",
        max_insights: int = 4,
    ) -> dict[str, Any]:
        if not articles:
            return {
                "insights": [],
                "x_long_form": "",
                "validation_summary": {"total_insights": 0, "passed": 0, "failed": 0},
                "error": "No articles provided",
            }
        if self.llm_adapter is None:
            return {
                "insights": [],
                "x_long_form": "",
                "validation_summary": {"total_insights": 0, "passed": 0, "failed": 0},
                "error": "LLM adapter unavailable",
            }

        historical_context = await self._get_historical_context(category)
        prompt = self._build_insight_prompt(category, articles, historical_context, max_insights, window_name)
        raw_insights = await self._call_llm(prompt)

        validated_insights = []
        source_text = "\n".join(f"{article.get('title', '')}\n{article.get('summary', '')}" for article in articles)
        for insight in raw_insights[:max_insights]:
            validated = self.validator.validate(insight, source_text=source_text)
            insight.update(validated)
            validated_insights.append(insight)

        x_long_form = self._format_x_long_form(category, validated_insights)
        return {
            "insights": validated_insights,
            "x_long_form": x_long_form,
            "validation_summary": {
                "total_insights": len(validated_insights),
                "passed": sum(1 for item in validated_insights if item.get("validation_passed", False)),
                "failed": sum(1 for item in validated_insights if not item.get("validation_passed", False)),
                "evidence_tagged": sum(1 for item in validated_insights if item.get("evidence_tag")),
            },
        }

    async def _get_historical_context(self, category: str) -> str:
        if not self.state_store or not hasattr(self.state_store, "get_recent_topics"):
            return ""
        try:
            past_topics = self.state_store.get_recent_topics(category, days=30, limit=10)
        except Exception as exc:
            logger.warning("Failed to load historical insight context: %s", exc)
            return ""
        if not past_topics:
            return ""
        lines = [f"## 최근 30일 주요 트렌드 ({category})"]
        for topic in past_topics[:5]:
            lines.append(
                f"- {topic.get('topic_label', 'Unknown')} "
                f"(등장 {topic.get('occurrence_count', 1)}회, {topic.get('first_seen_at', '')[:10]} ~ {topic.get('last_seen_at', '')[:10]})"
            )
        return "\n".join(lines)

    def _build_insight_prompt(
        self,
        category: str,
        articles: list[dict[str, str]],
        historical_context: str,
        max_insights: int,
        window_name: str,
    ) -> str:
        article_lines = "\n\n".join(
            f"[A{idx}] 제목: {article.get('title', '')}\n요약: {article.get('summary', '')}\n링크: {article.get('link', '')}"
            for idx, article in enumerate(articles[:10], 1)
        )
        return f"""당신은 분석형 뉴스 인사이트 전문가입니다.
아래 기사들로부터 독자가 바로 행동할 수 있는 고품질 인사이트를 {max_insights}개 생성하세요.

원칙:
1. 점(Fact) → 선(Trend) 연결
2. 파급 효과(Ripple Effect) 예측
3. 실행 가능한 결론(Actionable Item)

하드 규칙:
- CTA는 일반론적 조언으로 끝나면 안 됩니다.
- 타겟 독자는 최대 3개 이하여야 합니다.
- 입력 기사에 없는 새로운 숫자는 조심스럽게 다뤄야 합니다.
- 각 인사이트에는 근거 태그를 하나 포함해야 합니다.

허용 근거 태그:
- [A1], [A2], [A3]
- [Inference:A1+A2]
- [Background]
- [Insufficient evidence]

카테고리: {category}
시간대: {window_name}

과거 트렌드:
{historical_context if historical_context else "(없음)"}

오늘의 기사:
{article_lines}

출력은 반드시 JSON 배열만 반환하세요:
[
  {{
    "title": "인사이트 제목",
    "content": "150-300단어이며 마지막에 근거 태그를 붙입니다. 예: ... [A1]",
    "principle_1_connection": "점→선 연결 설명 [A1]",
    "principle_2_ripple": "1차→2차→3차 파급 효과 [Inference:A1+A2]",
    "principle_3_action": "구체적 행동",
    "target_audience": "투자자, 개발자",
    "evidence_tag": "[A1]"
  }}
]
"""

    async def _call_llm(self, prompt: str) -> list[dict[str, Any]]:
        try:
            response = await self.llm_adapter.generate_text(
                prompt,
                max_tokens=2000,
                cache_scope="insight-generator",
            )
        except Exception as exc:
            logger.error("Insight generation failed: %s", exc)
            return []

        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if not json_match:
            logger.warning("Insight generator returned non-JSON output")
            return []
        try:
            parsed = json.loads(json_match.group(0))
        except json.JSONDecodeError as exc:
            logger.warning("Insight generator JSON parse failed: %s", exc)
            return []
        return parsed if isinstance(parsed, list) else []

    def _format_x_long_form(self, category: str, insights: list[dict[str, Any]]) -> str:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        lines = [f"# {category} 주요 인사이트 ({today})", ""]
        for idx, insight in enumerate(insights, 1):
            if not insight.get("validation_passed", False):
                continue
            lines.append(f"## {idx}. {insight.get('title', 'Untitled')}")
            lines.append("")
            clean_content = re.sub(
                r"\s*\[(?:A\d+|Inference:[^\]]+|Background|Insufficient evidence)\]\s*$",
                "",
                insight.get("content", ""),
            ).strip()
            lines.append(clean_content)
            lines.append("")
            action = insight.get("principle_3_action", "")
            if action:
                lines.append(f"실행 항목: {action}")
                lines.append("")
        return "\n".join(lines).strip()
