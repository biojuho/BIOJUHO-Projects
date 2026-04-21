from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from antigravity_mcp.insights.validator import InsightValidator

logger = logging.getLogger(__name__)

_EVIDENCE_TAG_PATTERN = re.compile(
    r"\s*\[(?:A\d+|Inference:[^\]]+|Background|Insufficient evidence)\]\s*$"
)
_WHITESPACE_PATTERN = re.compile(r"\s+")

_DEFAULT_LONGFORM_PROFILE: dict[str, str] = {
    "header": "🗞️ Daily Brief",
    "focus": "핵심 변화",
    "reader_promise": "독자가 오늘 봐야 할 변화와 함의를 빠르게 파악하게 한다.",
    "frame_question": "이 변화가 누가 이기고 누가 밀리는지를 어떻게 바꾸는가?",
    "default_today": "오늘은 표면 뉴스보다 구조 변화가 더 중요하다.",
    "default_closing": "헤드라인보다 구조 변화의 방향을 먼저 읽어야 한다.",
}

_CATEGORY_LONGFORM_PROFILES: dict[str, dict[str, str]] = {
    "Global_Affairs": {
        "header": "🏛 정치",
        "focus": "권력 지형의 이동",
        "reader_promise": "누가 권한을 얻고 누가 제약받는지 보이게 한다.",
        "frame_question": "누가 권한을 얻고, 누가 제약받는가?",
        "default_today": "오늘 정치 섹션의 핵심은 권한과 통제의 축이 다시 움직인다는 점이다.",
        "default_closing": "정치 뉴스의 핵심은 발언보다 권한 배분의 변화다.",
    },
    "Economy_KR": {
        "header": "🇰🇷 국내 경제",
        "focus": "독자 지갑에 닿는 변화",
        "reader_promise": "정책과 시장 변화가 통장과 자금 흐름에 어떻게 닿는지 설명한다.",
        "frame_question": "이 정책의 비용은 누가 내고, 수혜는 누가 받는가?",
        "default_today": "오늘 국내 경제는 정부와 시장이 개인의 리스크를 어떻게 나눌지가 핵심이다.",
        "default_closing": "국내 경제 뉴스는 결국 누가 비용을 떠안고 누가 완충을 받는지로 정리된다.",
    },
    "Economy_Global": {
        "header": "🌍 글로벌 경제",
        "focus": "매크로 흐름과 한국 파급",
        "reader_promise": "글로벌 거시 변화가 한국 자산, 환율, 물가로 어떻게 번역되는지 보여준다.",
        "frame_question": "한국 자산·환율·물가에 어떤 파급이 오는가?",
        "default_today": "오늘 글로벌 경제는 해외 변수의 변화가 한국 가격 변수로 번역되는 과정이 핵심이다.",
        "default_closing": "글로벌 경제 뉴스는 한국 자산 가격으로 번역되는 순간 진짜 의미가 드러난다.",
    },
    "AI_Deep": {
        "header": "🤖 AI",
        "focus": "업계 내부자 시각",
        "reader_promise": "새 기술이 실제 업무 구조를 얼마나 바꾸는지 읽게 한다.",
        "frame_question": "이 기술이 실제 업무를 얼마나 대체하거나 보조하는가?",
        "default_today": "오늘 AI 섹션은 모델 성능보다 업무 구조 변화가 더 중요한 날이다.",
        "default_closing": "AI 뉴스의 본질은 데모가 아니라 업무 대체 구조다.",
    },
    "Tech": {
        "header": "🔧 Tech",
        "focus": "실무자 관점의 도구 변화",
        "reader_promise": "플랫폼 힘의 균형이 어디로 이동하는지, 그래서 무엇을 배워야 하는지 보여준다.",
        "frame_question": "플랫폼 힘의 균형이 어디로 이동하고, 지금 무엇을 배워야 하나?",
        "default_today": "오늘 Tech는 제품 기능보다 도구와 플랫폼의 주도권 이동이 핵심이다.",
        "default_closing": "Tech 뉴스는 기능 추가보다 누가 락인을 가져가는지에서 갈린다.",
    },
    "Crypto": {
        "header": "₿ Crypto",
        "focus": "감정과 데이터의 괴리",
        "reader_promise": "가격보다 심리와 제도권 접점의 변화를 먼저 읽게 한다.",
        "frame_question": "시장이 착각하는 건 무엇이고, 제도권 편입은 빨라지는가?",
        "default_today": "오늘 Crypto는 가격보다 심리와 규제의 간극이 더 중요한 날이다.",
        "default_closing": "크립토 뉴스는 가격보다 제도권과의 접점에서 방향이 갈린다.",
    },
}


def _get_longform_profile(category: str) -> dict[str, str]:
    profile = dict(_DEFAULT_LONGFORM_PROFILE)
    profile.update(_CATEGORY_LONGFORM_PROFILES.get(category, {}))
    return profile


def _strip_evidence_tags(text: str) -> str:
    return _EVIDENCE_TAG_PATTERN.sub("", text or "").strip()


def _compact_text(text: str, *, max_len: int = 0) -> str:
    compact = _WHITESPACE_PATTERN.sub(" ", _strip_evidence_tags(text)).strip(" -:\n")
    if max_len and len(compact) > max_len:
        compact = compact[: max_len - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "…"
    return compact


def _pick_text(*values: str, max_len: int = 0) -> str:
    for value in values:
        compact = _compact_text(value or "", max_len=max_len)
        if compact:
            return compact
    return ""


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
        profile = _get_longform_profile(category)
        article_lines = "\n\n".join(
            f"[A{idx}] 제목: {article.get('title', '')}\n요약: {article.get('summary', '')}\n링크: {article.get('link', '')}"
            for idx, article in enumerate(articles[:10], 1)
        )
        return f"""당신은 분석형 뉴스 인사이트 전문가입니다.
아래 기사들로부터 독자가 바로 행동할 수 있는 고품질 인사이트를 {max_insights}개 생성하세요.

이 결과물은 X에서 발행되는 "{profile['header']}" 카테고리 롱폼 포스트의 재료입니다.
포맷 전제:
- 각 카테고리는 하나의 자기완결적 브리핑 카드처럼 읽혀야 합니다.
- 카툰 이미지는 비유와 인상을 담당합니다.
- 텍스트는 팩트, 인과, 함의, 독자 체크포인트를 담당합니다.
- 텍스트에서 "마치 ~ 같다" 식 비유는 남발하지 말고, 꼭 필요할 때만 1문장 이하로 제한하세요.
- 첫 번째 인사이트는 반드시 메인 아이템, 나머지는 서브 아이템으로 구성하세요.
- 한 인사이트에는 한 개의 핵심 메시지만 남기세요.

카테고리 프레임:
- 포커스: {profile['focus']}
- 독자 약속: {profile['reader_promise']}
- 마무리에서 답해야 할 질문: {profile['frame_question']}

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
    "section_role": "main",
    "hook": "첫 문장으로 바로 써도 되는 한 줄 훅",
    "summary_fact": "핵심 사실 1문장",
    "why_now": "왜 지금 중요한지 1문장",
    "content": "4~6문장 본문이며 마지막에 근거 태그를 붙입니다. 예: ... [A1]",
    "principle_1_connection": "점→선 연결 설명 [A1]",
    "principle_2_ripple": "1차→2차→3차 파급 효과 [Inference:A1+A2]",
    "principle_3_action": "구체적 행동과 시한",
    "target_audience": "투자자, 개발자",
    "evidence_tag": "[A1]",
    "one_line_takeaway": "독자가 가져가야 할 핵심 관점 1문장",
    "closing_line": "공유 가능한 결론 1문장",
    "visual_brief": "카툰 한 컷용 이미지 디렉션 1문장"
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
        profile = _get_longform_profile(category)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        valid_insights = [insight for insight in insights if insight.get("validation_passed", False)]
        if not valid_insights:
            return ""

        selected = valid_insights[:4]
        opener = _pick_text(
            selected[0].get("hook", ""),
            selected[0].get("one_line_takeaway", ""),
            selected[0].get("why_now", ""),
            selected[0].get("summary_fact", ""),
            profile["default_today"],
            max_len=110,
        )

        lines = [f"## {profile['header']} | {today}", "", f"오늘 한 줄: {opener}", ""]

        for idx, insight in enumerate(selected, 1):
            role = str(insight.get("section_role", "") or "").strip().lower()
            if idx == 1 or role == "main":
                role_label = "메인"
            else:
                role_label = f"서브 {idx - 1}"

            title = _pick_text(insight.get("title", ""), f"이슈 {idx}", max_len=56)
            fact = _pick_text(
                insight.get("summary_fact", ""),
                insight.get("hook", ""),
                insight.get("content", ""),
                max_len=110,
            )
            why_now = _pick_text(
                insight.get("why_now", ""),
                insight.get("principle_1_connection", ""),
                max_len=120,
            )
            viewpoint = _pick_text(
                insight.get("one_line_takeaway", ""),
                insight.get("closing_line", ""),
                insight.get("principle_2_ripple", ""),
                max_len=130,
            )
            checkpoint = _pick_text(
                insight.get("principle_3_action", ""),
                insight.get("target_audience", ""),
                max_len=120,
            )

            lines.append(f"### {role_label} | {title}")
            if fact:
                lines.append(f"핵심 사실: {fact}")
            if why_now:
                lines.append(f"왜 중요하냐면: {why_now}")
            if viewpoint:
                lines.append(f"내 시각: {viewpoint}")
            if checkpoint:
                lines.append(f"체크포인트: {checkpoint}")
            lines.append("")
            if idx != len(selected):
                lines.append("──────")
                lines.append("")

        closing = _pick_text(
            selected[0].get("closing_line", ""),
            selected[0].get("one_line_takeaway", ""),
            profile["default_closing"],
            max_len=130,
        )
        lines.append(f"오늘의 결론: {closing}")
        lines.append(f"답해야 할 질문: {profile['frame_question']}")
        return "\n".join(lines).strip()
