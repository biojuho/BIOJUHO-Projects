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
    from shared.llm import TaskTier
    from shared.llm import get_client as _get_llm_client
except ImportError:
    try:
        import sys
        from pathlib import Path

        _ROOT = Path(__file__).resolve().parents[4]
        if str(_ROOT) not in sys.path:
            sys.path.insert(0, str(_ROOT))
        from shared.llm import TaskTier
        from shared.llm import get_client as _get_llm_client
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
        text = re.sub(r",(\s*[}\]])", r"\1", text)
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse brain module JSON: %s...", text[:100])
        return None


class BrainAdapter:
    """Cross-article analysis: editorial selection + deep insight generation."""

    def __init__(self) -> None:
        try:
            self._client = _get_llm_client() if _get_llm_client else None
        except Exception:
            self._client = None

    def is_available(self) -> bool:
        return self._client is not None

    async def select_top_articles(
        self,
        category: str,
        articles: list[dict[str, str]],
    ) -> list[int]:
        """Stage 2: Pick 3-4 highest-value articles for deep analysis.

        Returns indices of selected articles.
        """
        if not self.is_available() or len(articles) <= 4:
            return list(range(len(articles)))

        hints = _CATEGORY_PROMPT_HINTS.get(category, _CATEGORY_PROMPT_HINTS["Tech"])

        listing = ""
        for idx, art in enumerate(articles):
            title = art.get("title", "")
            summary = (art.get("summary") or art.get("description") or "")[:200]
            listing += f"{idx}. {title}\n   {summary}\n\n"

        prompt = (
            f"당신은 {hints['role']} 시니어 편집자입니다.\n"
            f"오늘 날짜는 {__import__('datetime').date.today().isoformat()}입니다.\n\n"
            "아래 기사 목록에서 **발행 가치가 가장 높은 3~4개**만 선택하세요.\n\n"
            "[선별 기준]\n"
            "1. **시의성**: 오늘 또는 어제 발생한 사건인가? 과거 뉴스의 재탕이면 제외.\n"
            "2. 시장/사회 영향도: 독자의 의사결정에 영향을 주는가?\n"
            "3. 수치 포함: 구체적 데이터가 있어 분석이 가능한가?\n"
            "4. 연결 가능성: 다른 뉴스와 엮어 더 큰 그림을 그릴 수 있는가?\n"
            "5. 참신성: 독자가 이미 아는 내용의 반복이 아닌가?\n\n"
            "[버리는 기사]\n"
            "- 며칠 전 사건의 후속 보도이면서 새로운 정보가 없는 기사\n"
            "- 단순 이벤트 고지, 기업 PR, 중복 기사\n"
            "- 카테고리와 맞지 않는 기사 (예: 경제 카테고리에 북한 외교 기사)\n\n"
            f"[기사 목록]\n{listing}\n"
            "선택한 기사의 번호만 JSON 배열로 반환하세요. 예: [0, 2, 5]\n"
            "번호 외에 아무 텍스트도 출력하지 마세요."
        )

        try:
            resp = await self._client.acreate(
                tier=TaskTier.LIGHTWEIGHT,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            text = (resp.text or "").strip()
            # Extract JSON array
            if "[" in text:
                arr_text = text[text.index("[") : text.index("]") + 1]
                indices = json.loads(arr_text)
                valid = [i for i in indices if isinstance(i, int) and 0 <= i < len(articles)]
                if valid:
                    logger.info("[%s] Editorial filter: selected %d/%d articles", category, len(valid), len(articles))
                    return valid
        except Exception as exc:
            logger.warning("Editorial filter failed for %s: %s", category, exc)

        return list(range(min(4, len(articles))))

    async def analyze_news(
        self,
        category: str,
        articles: list[dict[str, str]],
        time_window: str = "",
        niche_trends: list[dict] | None = None,
    ) -> dict[str, Any] | None:
        """Generate deep analysis with editorial selection.

        Returns None on failure so pipelines can gracefully degrade.
        """
        if not self.is_available() or not articles:
            return None

        # Stage 2: Editorial selection
        selected_indices = await self.select_top_articles(category, articles)
        selected_articles = [articles[i] for i in selected_indices]

        # Build article text — use full_text if available, fallback to summary
        news_text = ""
        for idx, art in enumerate(selected_articles, 1):
            full = art.get("full_text") or ""
            summary = (art.get("description") or art.get("summary") or "")[:200]
            content = full if full else summary
            news_text += f"[기사 {idx}] {art['title']}\n출처: {art.get('source_name', '알 수 없음')}\n{content}\n\n"

        trends_text = ""
        if niche_trends:
            trends_text = "[X Radar 실시간 반응 분석]\n"
            for t in niche_trends[:3]:
                trends_text += f"- 키워드: {t.get('keyword')}\n"
                trends_text += f"  - 반응 인사이트: {t.get('top_insight')}\n"
                trends_text += f"  - 바이럴 포텐셜 점수: {t.get('viral_potential')}/100\n"
                trends_text += f"  - 추천 앵글: {', '.join(t.get('suggested_angles', []))}\n"

        hints = _CATEGORY_PROMPT_HINTS.get(category, _CATEGORY_PROMPT_HINTS["Tech"])

        # Load X longform prompt template
        x_prompt_rules = ""
        try:
            from antigravity_mcp.config import CONFIG_DIR

            prompt_file = CONFIG_DIR / "x_longform_prompt.json"
            if prompt_file.exists():
                prompt_config = json.loads(prompt_file.read_text(encoding="utf-8"))
                x_prompt_rules = prompt_config.get("x_longform", {}).get("template", "")
        except Exception:
            pass

        # Stage 3: Deep analysis prompt — newsletter multi-section format
        prompt = (
            f"당신은 {hints['role']} 한국어 뉴스레터 편집자입니다.\n"
            f"[톤]: {hints['tone']}\n"
            f"[집중 포인트]: {hints['focus']}\n"
            f"[분석 기간]: {time_window}\n\n"
            f"[기사 원문]\n{news_text}\n"
            f"{trends_text}\n"
            "============================\n"
            "[독자]\n"
            "30~50대 한국 직장인·자영업자. 헤드라인은 봤지만 맥락을 모른다.\n"
            "자기 삶·자산에 영향을 주는 변화를 미리 감지하고 싶다. 당장 행동할 사람이 아니라 잠재적 당사자.\n\n"
            "[작성 규칙]\n"
            "- 기사마다 별도 섹션으로 분리. 각 섹션은 독립적으로 읽힐 수 있어야 한다.\n"
            "- 섹션 제목: ## {이모지} {핵심 수치 또는 키워드가 들어간 제목} (예: ## 📉 비트코인 $69,355 — 옵션 시장이 보내는 경고)\n"
            "- 첫 문장: 무슨 일인지 즉시 전달 (요약 아닌 훅)\n"
            "- **볼드**로 핵심 수치·용어 강조\n"
            "- 비유/아날로지 필수: 일반인이 크기감을 잡을 수 있는 일상적 비유 (삼성전자, 아파트값, 월급 등)\n"
            "- 인과 추론 2단계 이상: '이렇게 되면 → 저렇게 되고 → 결국 이게 바뀐다'\n"
            "- 마지막 문장: 독자가 기억할 한 줄 관점 (긴급 지시 아님)\n"
            "- 각 섹션 길이: 3~4 문단\n\n"
            "[금지]\n"
            "- '시사합니다', '중요합니다', '필요합니다' 결론 없는 마무리\n"
            "- '~할 수 있습니다', '~로 보입니다' 모호한 문장\n"
            "- 수치 없는 주장\n"
            "- 해시태그(#)\n"
            "- '지금 당장 ~하세요' 긴급 지시\n\n"
            "[출력 형식]\n"
            "반드시 아래 JSON만 반환. JSON 내 줄바꿈은 \\n으로.\n"
            '{"tagline": "오늘을 관통하는 핵심 한 줄 (예: 겉은 잔잔하고, 속은 갈라지고 있다)", '
            '"summary": ["핵심 발견 1", "핵심 발견 2", "핵심 발견 3"], '
            '"insights": [{"date": "YYYY-MM-DD", "topic": "주제", "insight": "핵심 분석 (수치 포함)", "importance": "독자에게 의미하는 바"}], '
            '"x_thread": ["## {이모지} {제목1}\\n\\n[섹션1 본문]\\n\\n## {이모지} {제목2}\\n\\n[섹션2 본문]\\n\\n..."]}'
        )
        if x_prompt_rules:
            prompt += f"\n\n[추가 롱폼 규칙]\n{x_prompt_rules}"

        try:
            resp = await self._client.acreate(
                tier=TaskTier.HEAVY,
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = (resp.text or "").strip()
            if not text:
                return None
            return _robust_json_parse(text)
        except Exception as exc:
            logger.warning("Brain analysis failed: %s", exc)
            return None
