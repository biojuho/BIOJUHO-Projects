"""Brain module adapter — cross-article LLM analysis with trend integration.

Consolidated from legacy ``scripts/brain_module.py`` to eliminate duplication.
Includes per-category prompt hints and structured X thread generation.
"""
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

# Per-category prompt hints (migrated from scripts/brain_module.py)
_CATEGORY_PROMPT_HINTS: dict[str, dict[str, str]] = {
    "Tech": {
        "role": "기술/AI/소프트웨어 뉴스를 전문적으로 다루는",
        "focus": "기술 트렌드, AI 혁신, 개발자 생태계, 빅테크 동향에 집중하세요.",
        "tone": "캐주얼하고 신뢰감 있는 전문가 톤",
    },
    "Economy_KR": {
        "role": "한국 경제/금융 뉴스를 전문적으로 분석하는",
        "focus": "국내 증시, 금리, 환율, 부동산, 수출입 동향, 기업 실적에 집중하세요.",
        "tone": "전문적이면서도 대중이 이해하기 쉬운 해설 톤",
    },
    "Economy_Global": {
        "role": "글로벌 경제/금융 시장을 전문적으로 분석하는",
        "focus": "미국 연준, 글로벌 증시, 원자재, 무역 정책, 거시경제 지표에 집중하세요.",
        "tone": "글로벌 시각으로 분석하는 전문가 톤",
    },
    "Crypto": {
        "role": "암호화폐/블록체인 시장을 전문적으로 다루는",
        "focus": "비트코인/이더리움 가격, DeFi, 규제 동향, 온체인 데이터, 거래소 뉴스에 집중하세요.",
        "tone": "크립토 커뮤니티에 맞는 캐주얼하면서도 날카로운 분석 톤",
    },
    "Global_Affairs": {
        "role": "국제 정치/외교 뉴스를 전문적으로 분석하는",
        "focus": "지정학적 갈등, 외교 협상, 선거/정권 변동, 국제기구 동향, 인도적 이슈에 집중하세요.",
        "tone": "객관적이면서도 통찰력 있는 국제뉴스 해설 톤",
    },
    "AI_Deep": {
        "role": "AI/ML 최신 기술과 연구 동향을 깊이 있게 분석하는",
        "focus": "신규 모델 릴리스, 벤치마크 결과, 오픈소스 생태계, AI 안전성/정렬, 에이전트 아키텍처, 멀티모달, 추론 능력, 산업 적용 사례에 집중하세요.",
        "tone": "기술적 깊이를 유지하면서도 실무 개발자가 바로 활용할 수 있는 인사이트를 제공하는 전문가 톤",
    },
}


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
            trends_text = "[X Radar 실시간 반응 분석]\n"
            for t in niche_trends[:3]:
                trends_text += f"- 키워드: {t.get('keyword')}\n"
                trends_text += f"  - 반응 인사이트: {t.get('top_insight')}\n"
                trends_text += f"  - 바이럴 포텐셜 점수: {t.get('viral_potential')}/100\n"
                trends_text += f"  - 추천 앵글: {', '.join(t.get('suggested_angles', []))}\n"

        hints = _CATEGORY_PROMPT_HINTS.get(category, _CATEGORY_PROMPT_HINTS["Tech"])

        prompt = (
            f"당신은 X(트위터)에서 {hints['role']} 콘텐츠 크리에이터 \"Raphael\"입니다.\n"
            f"Premium+ 사용자처럼 글자 제한 없이 자유롭게 긴 포스트를 작성할 수 있다고 가정하고, "
            f"하나의 긴 글(또는 자연스럽게 연결된 스레드) 형식으로 매우 가독성 높고 몰입감 있는 "
            f"{category} 뉴스 요약을 작성해주세요.\n\n"
            f"[카테고리 집중 포인트]: {hints['focus']}\n"
            f"[톤앤매너]: {hints['tone']}\n\n"
            f"[분석 대상 기간]: {time_window}\n\n"
            f"[뉴스 원문 데이터]:\n{news_text}\n"
            f"{trends_text}\n"
            "[작성 지침]\n"
            "1. **언어**: 반드시 모든 내용을 **한국어(Korean)**로 작성하세요.\n"
            "2. **길이**: **800~1200자 내외**로 정보를 압축하여 임팩트 있게 작성.\n"
            "3. **도입부**: 강렬한 한 줄 요약.\n"
            "4. **본문 구성**: 핵심 뉴스(3~4개)별로 명확한 소제목(이모지 1개 + 짧은 제목) 사용.\n"
            "   - 구조: **핵심 사실(1문장)** -> 배경/디테일(1-2문장 압축) -> 전망/의미(1문장).\n"
            "5. **트렌드 통합**: X Radar 데이터가 있다면 적극 활용.\n"
            "6. **금지**: 해시태그(#) 절대 사용 금지.\n"
            "7. **마무리**: 독자 참여 유도 1문장.\n\n"
            "[출력 형식]\n"
            "반드시 아래 JSON 형식으로만 응답하세요.\n"
            "**주의: JSON 값 내부의 줄바꿈은 반드시 \\n으로 이스케이프 처리해야 합니다.**\n"
            '{"summary": ["핵심1", "핵심2", "핵심3"], '
            '"insights": [{"date": "YYYY-MM-DD", "topic": "주제", "insight": "핵심 분석", "importance": "중요성"}], '
            '"x_thread": ["작성된 긴 포스트의 전체 내용 (줄바꿈은 \\n으로 표기)"]}'
        )

        try:
            resp = await self._client.acreate(
                tier=TaskTier.HEAVY,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = (resp.text or "").strip()
            if not text:
                return None
            return _robust_json_parse(text)
        except Exception as exc:
            logger.warning("Brain analysis failed: %s", exc)
            return None
