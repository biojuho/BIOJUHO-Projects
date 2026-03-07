"""Brain module adapter — cross-article LLM analysis with trend integration."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Import LLM primitives with graceful fallback
try:
    from shared.llm import TaskTier, get_client as _get_llm_client
except ImportError:
    try:
        import sys
        from pathlib import Path
        _ROOT = Path(__file__).resolve().parents[4]
        if str(_ROOT) not in sys.path:
            sys.path.insert(0, str(_ROOT))
        from shared.llm import TaskTier, get_client as _get_llm_client
    except ImportError:
        TaskTier = None
        _get_llm_client = None


def _robust_json_parse(text: str) -> dict | None:
    """Parse JSON from LLM output, tolerant of markdown fences and trailing commas."""
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        text = text.strip()
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse brain module JSON: %s...", text[:100])
        return None


class BrainAdapter:
    """Cross-article analysis that generates summary, insights, and X thread drafts."""

    def __init__(self) -> None:
        try:
            self._client = _get_llm_client() if _get_llm_client else None
        except Exception:
            self._client = None

    def is_available(self) -> bool:
        return self._client is not None

    async def analyze_news(
        self,
        category: str,
        articles: list[dict[str, str]],
        time_window: str = "",
        niche_trends: list[dict] | None = None,
    ) -> dict[str, Any] | None:
        """Generate summary/insights/X thread from a batch of articles.

        Returns None on failure so pipelines can gracefully degrade.
        """
        if not self.is_available() or not articles:
            return None

        news_text = ""
        for idx, art in enumerate(articles, 1):
            desc = (art.get("description") or "")[:200]
            news_text += f"{idx}. {art['title']}\n   - {desc}...\n\n"

        trends_text = ""
        if niche_trends:
            trends_text = "🎯 [X Radar 실시간 반응 분석]\n"
            for t in niche_trends[:3]:
                trends_text += f"- 키워드: {t.get('keyword')}\n"
                trends_text += f"  - 인사이트: {t.get('top_insight')}\n"
                trends_text += f"  - 바이럴 점수: {t.get('viral_potential')}/100\n"

        prompt = (
            f"당신은 기술/경제 뉴스 콘텐츠 크리에이터입니다.\n"
            f"[분석 대상 기간]: {time_window}\n"
            f"[뉴스 원문]:\n{news_text}\n{trends_text}\n"
            "반드시 JSON 형식으로만 응답하세요 (한국어):\n"
            '{"summary": ["핵심1", "핵심2"], '
            '"insights": [{"topic": "주제", "insight": "분석", "importance": "중요도"}], '
            '"x_thread": ["X 포스트 전체 내용"]}'
        )

        try:
            resp = await self._client.acreate(
                tier=TaskTier.MEDIUM,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            text = (resp.text or "").strip()
            if not text:
                return None
            return _robust_json_parse(text)
        except Exception as exc:
            logger.warning("Brain analysis failed: %s", exc)
            return None
