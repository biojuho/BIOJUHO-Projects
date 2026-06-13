"""
getdaytrends — Prompt Builder
프롬프트 빌드 + 시스템 프롬프트 + 페르소나 규칙.
generator.py에서 분리됨.
"""

import asyncio
import contextlib
import json
import re
from collections.abc import Callable, Coroutine
from typing import Any

from loguru import logger as log

from shared.llm import TaskTier

try:
    from .config import AppConfig
    from .models import ScoredTrend
except ImportError:
    from config import AppConfig
    from models import ScoredTrend

# ── 언어 코드 매핑 ────────────────────────────────────
_LANG_NAME_MAP: dict[str, str] = {
    "ko": "한국어",
    "en": "영어",
    "ja": "일본어",
    "es": "스페인어",
    "fr": "프랑스어",
    "zh": "중국어",
}


# ══════════════════════════════════════════════════════
#  Retry Helper (Phase 1)
# ══════════════════════════════════════════════════════


async def _retry_generate(
    coro_factory: Callable[[], Coroutine[Any, Any, Any]],
    keyword: str,
    max_retries: int = 2,
    base_delay: float = 1.0,
) -> Any:
    """
    생성 코루틴을 지수 백오프로 재시도.
    coro_factory: 호출할 때마다 새 코루틴을 반환하는 람다.
    예: _retry_generate(lambda: generate_tweets_async(trend, cfg, client), trend.keyword)
    """
    for attempt in range(max_retries + 1):
        try:
            result = await coro_factory()
            if result is not None:
                return result
        except Exception as e:
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                log.warning(
                    f"생성 재시도 ({attempt + 1}/{max_retries}) '{keyword}': {type(e).__name__} → {delay:.0f}s 후"
                )
                await asyncio.sleep(delay)
            else:
                log.error(f"생성 최종 실패 '{keyword}': {e}")
    return None


# ══════════════════════════════════════════════════════
#  Category-based Tier Routing (Phase 4)
# ══════════════════════════════════════════════════════


def _select_generation_tier(trend: ScoredTrend, config: AppConfig) -> "TaskTier":
    """카테고리 기반 LLM 티어 결정.

    heavy_categories(정치/경제/테크 등)는 Sonnet(HEAVY) 유지.
    연예/스포츠/날씨 등 경량 카테고리는 Haiku(LIGHTWEIGHT)로 다운그레이드.
    카테고리 미분류(category="")는 안전하게 HEAVY 유지.
    """
    category = getattr(trend, "category", "") or ""
    if not category:
        return TaskTier.HEAVY  # 카테고리 불명 → 기존 동작 유지

    heavy_cats = config.heavy_categories
    for heavy_cat in heavy_cats:
        if heavy_cat in category:
            return TaskTier.HEAVY

    return TaskTier.LIGHTWEIGHT


# ══════════════════════════════════════════════════════
#  Language Helper
# ══════════════════════════════════════════════════════

_LANGUAGE_MAP = {
    "korea": "한국어(Korean)",
    "us": "영어(English)",
    "japan": "일본어(Japanese)",
    "global": "영어(English)",
}


def _resolve_language(config: AppConfig) -> str:
    """
    다국어 자율 트랜스크리에이션 기초 설정:
    TARGET_LANGUAGES 환경변수가 단일 언어면 그대로 반환.
    여러 언어일 경우 (예: ko, en, ja) 콤마로 결합하여 LLM에 전달.
    추후 (v2.6) _step_generate에서 언어별로 루프를 도는 구조로 확장 가능.
    """
    if config.target_languages and config.target_languages != ["ko"]:
        # "ko", "en" 등 다국어 식별자가 들어있을 때
        # 향후에는 이 리스트를 순회하며 개별 TweetBatch를 생성하는 구조적 확장이 필요함 (기반 마련)
        mapping = {"ko": "한국어", "en": "영어", "ja": "일본어", "es": "스페인어", "fr": "프랑스어"}
        langs = [mapping.get(l.lower(), l) for l in config.target_languages]
        return ", ".join(langs)

    return _LANGUAGE_MAP.get((config.country or "").lower(), "한국어(Korean)")


def _build_account_identity_section(config: AppConfig, *, include_tone: bool = True) -> str:
    """[v8.0] 프롬프트 ②: 계정 정체성 섹션 생성."""
    niche = getattr(config, "account_niche", "")
    audience = getattr(config, "target_audience", "")
    if not niche and not audience:
        return ""
    parts = []
    if niche:
        parts.append(f"- 분야: {niche}")
    if include_tone:
        parts.append(f"- 톤앤매너: {config.tone}")
    else:
        parts.append(f"- 편집 프로필: {getattr(config, 'editorial_profile', 'report')}")
    if audience:
        parts.append(f"- 타겟 오디언스: {audience}")
    return "\n[계정 정체성]\n" + "\n".join(parts) + "\n"


def _build_diversity_section(recent_tweets: list[str]) -> str:
    """[v9.0] 이전 생성 트윗 목록을 프롬프트에 주입해 표현 중복 방지."""
    if not recent_tweets:
        return ""
    previews = "\n".join(f"  - {t[:80]}..." if len(t) > 80 else f"  - {t}" for t in recent_tweets[:4])
    return f"\n[이미 생성된 표현 — 반드시 다른 각도/어휘로 작성할 것]\n{previews}\n"


def _build_approved_post_bank_section(approved_posts: list[dict[str, Any]] | None) -> str:
    """Inject a few approved house-style references without inviting direct copying."""
    if not approved_posts:
        return ""

    lines = ["", "[Approved Post Bank — 리듬만 참고하고 문장은 복제하지 말 것]"]
    for post in approved_posts[:3]:
        body = re.sub(r"\s+", " ", str(post.get("body", "")).strip())
        if not body:
            continue
        if len(body) > 140:
            body = body[:137] + "..."
        lines.append(f"  - {body}")

    if len(lines) == 2:
        return ""

    lines.extend(
        [
            "- 압축감, 건조한 위트, 문장 밀도만 학습할 것.",
            "- 밈 말투, 과한 이모지, AI 프레임 반복은 금지.",
        ]
    )
    return "\n".join(lines) + "\n"


def _revision_feedback_base_lines() -> list[str]:
    return [
        "",
        "[재생성 보정 지시]",
        "- 이번 출력은 자동 QA 또는 FactCheck 실패 뒤 다시 쓰는 버전이다.",
        "- 핵심 인사이트는 유지하되, 문장만 조금 고치는 수준이 아니라 처음부터 다시 작성할 것.",
    ]


def _revision_axis_guidance() -> dict[str, str]:
    return {
        "hook": "泥?臾몄옣? ?レ옄, ?鍮? 吏덈Ц, 媛뺥븳 愿李?以??섎굹濡?諛붾줈 二쇰ぉ?꾨? 留뚮뱾?대씪.",
        "fact": "而⑦뀓?ㅽ듃??吏곸젒 ?덈뒗 怨좎쑀紐낆궗, ?섏튂, ?몄슜留??ъ슜?섍퀬 異붿젙 ?ъ떎? ?덈줈 留뚮뱾吏 留덈씪.",
        "tone": "?곹닾援? AI 留먰닾, 湲곗궗泥??쒗쁽??以꾩씠怨??щ엺??諛붾줈 留먰븯????븳 臾몄옣?쇰줈 諛붽퓭??",
        "kick": "留덈Т由щ뒗 諛뗫컠???뺣━ ????낆옄媛 媛?멸컝 ?댁꽍?대굹 ??以?愿李곕줈 ?앸궡??",
        "angle": "?댁뒪 ?붿빟 諛섎났???쇳븯怨? ??以묒슂?쒖??????紐낇솗??愿?먯씠???댁꽍??異붽??섎씪.",
        "regulation": "?뚮옯??洹쒖튃???꾩닔?섍퀬 湲몄씠, ?뺤떇, ?댁떆?쒓렇 ?쒗븳???ㅼ떆 ?먭??섎씪.",
        "algorithm": "?ㅽ겕濡ㅼ쓣 硫덉텛寃??섎뒗 援ъ“? 李몄뿬瑜?遺瑜대뒗 ?먮쫫????遺꾨챸???ㅺ퀎?섎씪.",
    }


def _qa_score_text(qa: dict) -> str:
    qa_total = qa.get("total")
    qa_threshold = qa.get("threshold")
    total_text = qa_total if qa_total not in (None, "") else "?"
    threshold_text = qa_threshold if qa_threshold not in (None, "") else "?"
    return f"- QA score/threshold: {total_text}/{threshold_text}"


def _qa_issue_lines(qa: dict) -> list[str]:
    return [f"- QA issue: {issue}" for issue in list(qa.get("issues", []) or [])[:3]]


def _qa_flag_lines(qa: dict) -> list[str]:
    lines: list[str] = []
    if qa.get("fact_violation"):
        lines.append("- Fact violation detected: preserve verified claims and remove unsupported numbers or entities.")
    if (qa.get("regulation") or 10) <= 3:
        lines.append("- Regulation score is low: avoid policy overclaims and name only verified institutions.")
    return lines


def _qa_axis_guidance_line(weakest_axis: str) -> str:
    guidance = _revision_axis_guidance().get(weakest_axis)
    return f"- Axis-specific rewrite guidance: {guidance}" if guidance else ""


def _append_revision_qa_lines(lines: list[str], qa: dict) -> None:
    if not qa:
        return
    weakest_axis = qa.get("worst_axis") or ""
    lines.append(_qa_score_text(qa))
    if weakest_axis:
        lines.append(f"- Weakest QA axis: {weakest_axis}")
    if qa.get("reason"):
        lines.append(f"- Main QA reason: {qa['reason']}")
    lines.extend(_qa_issue_lines(qa))
    lines.extend(_qa_flag_lines(qa))
    guidance_line = _qa_axis_guidance_line(weakest_axis)
    if guidance_line:
        lines.append(guidance_line)

def _append_revision_fact_check_lines(lines: list[str], fact_check: dict) -> None:
    if not fact_check:
        return
    accuracy_score = fact_check.get("accuracy_score")
    if fact_check.get("summary"):
        lines.append(f"- FactCheck 요약: {fact_check['summary']}")
    if accuracy_score is not None:
        with contextlib.suppress(TypeError, ValueError):
            lines.append(f"- 寃利??뺥솗?? {float(accuracy_score):.0%}")
    if fact_check.get("hallucinated_claims", 0):
        lines.append(f"- 환각 의심 주장 수: {fact_check.get('hallucinated_claims', 0)}")
    for issue in list(fact_check.get("issues", []) or [])[:3]:
        lines.append(f"- ?쒓굅 ?먮뒗 ?꾪솕??二쇱옣: {issue}")
    lines.append("- ?뚯뒪?먯꽌 吏곸젒 ?뺤씤???ъ떎留??⑥젙?뺤쑝濡??곌퀬, 遺덊솗?ㅽ븳 ?댁슜? 異붿젙 ?쒗쁽?쇰줈 ??떠??")


def _build_revision_feedback_section(revision_feedback: dict | None) -> str:
    """Inject retry-specific QA / fact-check guidance into regeneration prompts."""
    if not revision_feedback:
        return ""

    lines = _revision_feedback_base_lines()
    _append_revision_qa_lines(lines, revision_feedback.get("qa") or {})
    _append_revision_fact_check_lines(lines, revision_feedback.get("fact_check") or {})
    return "\n".join(lines) + "\n"


def _build_deep_why_section(trend: ScoredTrend) -> str:
    """[v10.0] 구조화된 트렌드 배경을 생성 프롬프트에 주입."""
    tc = getattr(trend, "trend_context", None)
    if not tc:
        # fallback: 기존 why_trending 필드 활용
        if trend.why_trending:
            return f"\n[왜 지금 이게 트렌드인가]\n{trend.why_trending}\n"
        return ""
    return f"\n[왜 지금 이게 트렌드인가 — 반드시 이 맥락을 글에 녹일 것]\n{tc.to_prompt_text()}\n"


def _build_context_section(trend: ScoredTrend) -> str:
    if not trend.context:
        return ""
    combined = trend.context.to_combined_text()
    return f"\n[수집된 실시간 컨텍스트]\n{combined}\n" if combined else ""


def _build_scoring_section(trend: ScoredTrend) -> str:
    if trend.viral_potential <= 0:
        return ""
    angles = ", ".join(trend.suggested_angles) if trend.suggested_angles else "없음"
    return f"""
[바이럴 분석 결과]
- 바이럴 점수: {trend.viral_potential}/100
- 가속도: {trend.trend_acceleration}
- 핵심 인사이트: {trend.top_insight}
- 추천 앵글: {angles}
- 추천 훅: {trend.best_hook_starter}
"""


def _use_report_profile(config: AppConfig) -> bool:
    return getattr(config, "editorial_profile", "").lower() == "report"


def _clean_fact_line(line: str) -> str:
    line = re.sub(r"^\[[^\]]+\]\s*", "", line.strip())
    line = re.sub(r"^[\-\*\u2022]+\s*", "", line)
    return re.sub(r"\s+", " ", line).strip()


def _build_available_facts_section(trend: ScoredTrend, limit: int = 10) -> str:
    facts = _available_fact_lines(_available_fact_blocks(trend), limit)
    if not facts:
        return ""
    bullets = "\n".join(f"- {fact}" for fact in facts)
    return f"\n[사용 가능한 사실]\n{bullets}\n"


def _available_source_labels(trend: ScoredTrend) -> list[str]:
    context = getattr(trend, "context", None)
    labels: list[str] = []
    if context and getattr(context, "twitter_insight", ""):
        labels.append("X reactions")
    if context and getattr(context, "reddit_insight", ""):
        labels.append("Reddit discussion")
    if context and getattr(context, "news_insight", ""):
        labels.append("news headlines")
    if getattr(trend, "trend_context", None):
        labels.append("structured trend context")
    return labels


def _build_source_attribution_section(trend: ScoredTrend) -> str:
    labels = _available_source_labels(trend)
    if not labels:
        return ""
    source_list = ", ".join(labels)
    return (
        "\n[Source attribution requirement]\n"
        f"- Available source types: {source_list}.\n"
        "- When making a concrete claim, name the source type it came from "
        "using one of the available source types above.\n"
        "- Do not invent direct quotes, institutions, or numbers that are not present in the available facts.\n"
    )


def _available_fact_blocks(trend: ScoredTrend) -> list[str]:
    raw_blocks: list[str] = []
    if getattr(trend, "trend_context", None):
        raw_blocks.append(trend.trend_context.to_prompt_text())
    if getattr(trend, "context", None):
        raw_blocks.append(trend.context.to_combined_text())
    if getattr(trend, "top_insight", ""):
        raw_blocks.append(trend.top_insight)
    if getattr(trend, "why_trending", ""):
        raw_blocks.append(trend.why_trending)
    return raw_blocks


def _available_fact_lines(raw_blocks: list[str], limit: int) -> list[str]:
    facts: list[str] = []
    seen: set[str] = set()
    for block in raw_blocks:
        for raw_line in block.splitlines():
            fact = _normalized_fact_line(raw_line, seen)
            if not fact:
                continue
            facts.append(fact)
            if len(facts) >= limit:
                break
        if len(facts) >= limit:
            break
    return facts


def _normalized_fact_line(raw_line: str, seen: set[str]) -> str:
    line = _clean_fact_line(raw_line)
    if not line:
        return ""
    key = line.casefold()
    if key in seen:
        return ""
    seen.add(key)
    return line[:217].rstrip() + "..." if len(line) > 220 else line

def _build_fact_guardrail_section(trend: ScoredTrend) -> str:
    facts_section = _build_available_facts_section(trend)

    # 소스 신뢰도 정보 포함
    credibility_note = ""
    cred = getattr(trend, "source_credibility", 0.0)
    if cred > 0:
        if cred >= 0.8:
            credibility_note = "- [출처 신뢰도: 높음] 수집된 팩트를 적극 활용할 것.\n"
        elif cred >= 0.5:
            credibility_note = "- [출처 신뢰도: 보통] 수치와 인용은 한정어('약', '추정')를 부착할 것.\n"
        else:
            credibility_note = "- [출처 신뢰도: 낮음] 구체적 수치 사용을 최소화하고 일반적 서술에 집중할 것.\n"

    # 소스 간 불일치 경고
    consistency_note = ""
    if not getattr(trend, "cross_source_consistent", True):
        flags = getattr(trend, "hallucination_flags", [])
        if flags:
            conflict_info = "; ".join(flags[:2])
            consistency_note = (
                f"- [소스 간 불일치 감지: {conflict_info}] "
                "수치가 소스마다 다를 수 있음. 확정적 표현 대신 '~로 알려졌다', '~라는 분석이 있다'를 사용할 것.\n"
            )

    rules = (
        "\n[사실 고정 규칙 — 위반 시 0점]\n"
        "- 아래 [사용 가능한 사실]과 입력 컨텍스트에 없는 기관명, 브랜드명, 통계, 도입 사례, 직접 인용은 새로 만들지 말 것.\n"
        "- 숫자나 기관명이 확인되지 않으면 일반화해서 서술할 것.\n"
        "- 고유명사는 입력에 실제로 등장한 경우에만 사용할 것.\n"
        "- '전문가들은', '관계자에 따르면' 등 출처 불명 인용은 절대 금지.\n"
        "- 날짜, 금액, 비율 등 수치는 컨텍스트 원문과 정확히 일치해야 함. 기억에 의존한 수치 사용 금지.\n"
        "- 비교 주장('A보다 B가 크다')은 컨텍스트에 양쪽 데이터가 있을 때만 가능.\n"
        f"{credibility_note}"
        f"{consistency_note}"
    )
    return rules + _build_source_attribution_section(trend) + facts_section


def _build_audience_format_section(trend: ScoredTrend) -> str:
    """[v18.0] Audience-First 프레임워크 기반: 크리에이터 친화적 시각적 포맷팅 및 지표 노출 규칙."""
    viral_score = trend.viral_potential
    if viral_score < 70:
        return ""

    return (
        f"\n[Audience-First 포맷팅 규칙]\n"
        f"- 대상 독자: 트렌드를 빠르게 파악하고 큐레이션하려는 '콘텐츠 크리에이터/마케터'.\n"
        f"- 시각적 가독성: 줄바꿈과 여백을 적극 활용하여 텍스트 덩어리(Text Block)가 되지 않도록 할 것.\n"
        f"- 바이럴 텐션: 포스트 리드(첫 문단) 혹은 마무리 부근에 현재 획득한 바이럴 점수({viral_score}점)를 "
        f"'💡 바이럴 텐션: {viral_score}점' 이나 유사한 재치있는 표현으로 명시하여 크리에이터들이 이 정보를 가치있게 느끼도록 할 것.\n"
    )


def _build_golden_reference_section(golden_refs: list | None) -> str:
    """[E] 골든 레퍼런스 벤치마크 섹션 — QA 기준으로 실제 고성과 트윗 주입."""
    if not golden_refs:
        return ""
    examples = []
    for i, ref in enumerate(golden_refs[:3], 1):
        content = getattr(ref, "content", "") or ""
        if len(content) > 150:
            content = content[:147] + "..."
        er = getattr(ref, "engagement_rate", 0.0) or 0.0
        angle = getattr(ref, "angle_type", "") or ""
        hook = getattr(ref, "hook_pattern", "") or ""
        examples.append(f"  {i}. [{angle}|{hook}] (ER={er:.4f}): {content}")
    refs_text = "\n".join(examples)
    return (
        f"\n[벤치마크 레퍼런스 — 이 수준 이상의 품질을 목표로 할 것]\n"
        f"아래는 실제로 높은 참여율을 기록한 트윗들이다. 이보다 낮은 퀄리티의 글은 0점이다.\n"
        f"{refs_text}\n"
    )



def _top_weight_line(title: str, weights: dict, labels: dict[str, str], limit: int) -> str:
    if not weights:
        return ""
    top_items = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:limit]
    formatted = ", ".join(f"{labels.get(k, k)}({v:.0%})" for k, v in top_items)
    return f"- {title}: {formatted}"


def _pattern_weight_labels() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    hook_labels = {
        "number_shock": "number shock",
        "relatable_math": "relatable math",
        "reversal": "reversal",
        "insider": "insider",
        "contrast": "contrast",
        "question": "question",
    }
    kick_labels = {
        "mic_drop": "mic drop",
        "self_deprecation": "self-deprecation",
        "uncertainty": "uncertainty",
        "manifesto": "manifesto",
        "twist": "twist",
    }
    angle_labels = {
        "reversal": "reversal angle",
        "data_punch": "data punch",
        "empathy": "empathy",
        "tips": "practical tips",
        "debate": "debate",
    }
    return hook_labels, kick_labels, angle_labels


def _build_pattern_weights_section(pattern_weights: dict | None) -> str:
    """Inject high-performing pattern weights into generation prompts."""
    if not pattern_weights:
        return ""
    hook_w = pattern_weights.get("hook_weights", {})
    kick_w = pattern_weights.get("kick_weights", {})
    angle_w = pattern_weights.get("angle_weights", {})

    if not hook_w and not kick_w and not angle_w:
        return ""

    hook_labels, kick_labels, angle_labels = _pattern_weight_labels()
    lines = ["\n[Performance-based pattern weights: prioritize higher-weight patterns]"]
    for line in (
        _top_weight_line("Opening hooks", hook_w, hook_labels, 3),
        _top_weight_line("Closing kicks", kick_w, kick_labels, 3),
        _top_weight_line("Delivery angles", angle_w, angle_labels, 2),
    ):
        if line:
            lines.append(line)

    return "\n".join(lines) + "\n"


def _build_category_tone_hint(trend: ScoredTrend) -> str:
    """[v17] 카테고리별 글쓰기 기법 우선순위 힌트."""
    category = getattr(trend, "category", "") or ""
    hints = {
        "정치": "기법 우선: 대조법 + 반전. 팩트 기반으로만 때릴 것. 양비론 금지, 구체적 수치/발언 인용",
        "경제": "기법 우선: 숫자 펀치 + 체감 환산. '1조'를 '직장인 월급 N만명분'으로 번역. 내 지갑에 미치는 영향 중심",
        "테크": "기법 우선: 비유법 + 질문 전환. 비전공자도 '오' 하게 일상 비유. 기술 자체보다 '그래서 뭐가 바뀌는데?'에 답할 것",
        "사회": "기법 우선: 공감 자조 + 반전. '나도 그런데...' 1인칭 시작. 개인 일상과 연결해서 공감 극대화",
        "스포츠": "기법 우선: 숫자 펀치 + 대조법. 기록/통계를 역대 비교로 임팩트. 선수의 인간적 면모 포착",
        "과학": "기법 우선: 체감 환산 + 질문 도발. 논문 숫자를 일상 스케일로 번역 ('이 거리는 서울-부산 N배'). '근데 이게 우리 삶에 뭔 영향?'",
        "의학": "기법 우선: 숫자 펀치 + 공감. 통계를 '100명 중 N명' 식 체감 단위로. 내 몸/건강에 직결되는 관점. 과장/공포 조장 금지",
        "국제": "기법 우선: 대조 병치 + 타임라인 대비. '그 나라에서는 A인데 우리는 B' 프레임. 한국 독자 관점에서 왜 중요한지",
        "게임": "기법 우선: 공감 자조 + 비유법. 게이머 문화 코드 활용. 과금/밸런스/메타 변화를 직장생활에 빗대기",
        "음식": "기법 우선: 숫자 펀치 + 공감. 가격 변화를 체감 단위로 ('작년에 8000원이었는데...'). 일상 경험 연결",
        "날씨": "기법 우선: 숫자 충격 + 체감 환산. 역대 기록 대비로 임팩트. 출퇴근/일상에 미치는 영향 중심",
    }
    hint = hints.get(category, "")
    return f"\n[카테고리 톤 힌트: {category}]\n{hint}\n" if hint else ""


# ══════════════════════════════════════════════════════
#  JSON Parser
# ══════════════════════════════════════════════════════


def _json_parse_candidates(raw: str) -> list[str]:
    stripped = raw.strip()
    candidates = [stripped]
    fence_match = re.match(r"^\s*```(?:json)?\s*([\s\S]*?)\s*```\s*$", stripped, re.IGNORECASE)
    if fence_match:
        candidates.append(fence_match.group(1).strip())

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and start < end:
        candidates.append(stripped[start : end + 1])

    repaired_candidates: list[str] = []
    for candidate in candidates:
        repaired_candidates.append(candidate)
        repaired = _strip_json_trailing_commas(candidate)
        if repaired != candidate:
            repaired_candidates.append(repaired)
    return repaired_candidates


def _strip_json_trailing_commas(candidate: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    i = 0

    while i < len(candidate):
        ch = candidate[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == ",":
            j = i + 1
            while j < len(candidate) and candidate[j] in " \t\r\n":
                j += 1
            if j < len(candidate) and candidate[j] in "}]":
                i += 1
                continue

        out.append(ch)
        i += 1

    return "".join(out)


def _parse_json(raw: str | None) -> dict | None:
    if not raw:
        return None

    candidates = _json_parse_candidates(raw)
    last_error: json.JSONDecodeError | None = None
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict):
            return parsed

    preview = raw[:200].replace("\n", "\\n")
    log.warning(f"[_parse_json] JSON 파싱 실패: {last_error} | 원본 미리보기: {preview}")
    return None


# ══════════════════════════════════════════════════════
#  System Prompt Builders  (tone 주입 — P1-2)
# ══════════════════════════════════════════════════════

# ── 시스템 프롬프트 (system_prompts.py에서 분리됨) ──────────────

try:
    from .system_prompts import (  # noqa: F401
        _JOONGYEON_RULES,
        _REPORT_BLOG_SYSTEM,
        _REPORT_LONG_FORM_SYSTEM,
        _REPORT_THREADS_SYSTEM,
        _system_long_form,
        _system_long_form_joongyeon,
        _system_thread,
        _system_threads,
        _system_threads_joongyeon,
        _system_tweets,
        _system_tweets_and_threads,
        _system_tweets_joongyeon,
    )
except ImportError:
    from system_prompts import (  # noqa: F401
        _JOONGYEON_RULES,
        _REPORT_BLOG_SYSTEM,
        _REPORT_LONG_FORM_SYSTEM,
        _REPORT_THREADS_SYSTEM,
        _system_long_form,
        _system_long_form_joongyeon,
        _system_thread,
        _system_threads,
        _system_threads_joongyeon,
        _system_tweets,
        _system_tweets_and_threads,
        _system_tweets_joongyeon,
    )


def _build_audience_format_section(trend: ScoredTrend) -> str:
    """Audience-first formatting rules without leaking internal dashboard metrics."""
    if trend.viral_potential < 70:
        return ""
    return (
        "\n[Audience-First Format Rules]\n"
        "- The reader should understand the point within three seconds.\n"
        "- Use line breaks so the post does not collapse into one text block.\n"
        "- Do not expose viral score, expected engagement, or any internal scoring language in public copy.\n"
        "- Create urgency through concrete observation, not through dashboard-style wording.\n"
    )


def _use_report_profile(config: AppConfig) -> bool:
    profile = getattr(config, "editorial_profile", "").lower()
    tone = getattr(config, "tone", "").lower()
    return profile == "report" and tone != "biojuho"


_AI_NATIVE_TOPIC_PATTERNS: tuple[str, ...] = (
    r"\bai\b",
    r"\bgpt\b",
    r"\bllm\b",
    r"\bagent(?:s)?\b",
    r"\bmodel(?:s)?\b",
    r"\bclaude\b",
    r"\bopenai\b",
    r"\bgemini\b",
    r"\banthropic\b",
    "인공지능",
    "생성형",
    "에이전트",
    "대규모 언어",
    "파운데이션 모델",
)


def _trend_is_ai_native(trend: ScoredTrend) -> bool:
    parts = [
        getattr(trend, "keyword", ""),
        getattr(trend, "category", ""),
        getattr(trend, "top_insight", ""),
        getattr(trend, "why_trending", ""),
        getattr(trend, "best_hook_starter", ""),
    ]
    parts.extend(getattr(trend, "suggested_angles", []) or [])
    context = getattr(trend, "context", None)
    if context is not None:
        combiner = getattr(context, "to_combined_text", None)
        if callable(combiner):
            parts.append(combiner())
    text = "\n".join(part for part in parts if part).lower()
    if not text:
        return False
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _AI_NATIVE_TOPIC_PATTERNS)


def _build_ai_frame_guard_section(trend: ScoredTrend) -> str:
    """Generation-stage AI Convergence Guard v2.

    When the trend is not AI-native, instruct the LLM to keep AI framing to at
    most one of the five drafts and to force at least one fully non-AI lens.
    """
    if _trend_is_ai_native(trend):
        return ""
    return (
        "\n[AI Frame Guard]\n"
        "- This topic is not AI-native.\n"
        "- At most 1 of the 5 drafts may use an AI/LLM/agent/generative-model lens.\n"
        "- At least 1 draft must avoid any AI/LLM/agent/model framing entirely.\n"
        "- Do not retrofit the topic into an AI/company/workshop narrative when a non-AI lens fits.\n"
    )


_BLOG_STRUCTURE_POOL: tuple[tuple[str, str], ...] = (
    (
        "pattern_a",
        "phenomenon -> historical parallel -> prediction. Use three H2 sections and a brief closing note.",
    ),
    (
        "pattern_b",
        "personal scene -> data/evidence -> structure read. Use three H2 sections and a brief closing note.",
    ),
    (
        "pattern_c",
        "counter-thesis -> evidence -> conditional conclusion. Use three H2 sections and a brief closing note.",
    ),
    (
        "pattern_d",
        "signal -> misread -> correction. Open with the visible signal, show how the default reading is wrong, then land the sharper correction. Three H2 sections and a brief closing note.",
    ),
    (
        "pattern_e",
        "anecdote -> contradiction -> broader pattern. Open with a small concrete anecdote, surface the contradiction it exposes, then pull back to the broader pattern. Three H2 sections and a brief closing note.",
    ),
    (
        "pattern_f",
        "timeline -> inflection point -> forecast. Lay out the short timeline, mark the precise inflection, then project the next move. Three H2 sections and a brief closing note.",
    ),
)


def _build_blog_structure_section(trend: ScoredTrend) -> str:
    """Rotate long-form structures to avoid a fixed repeated blog skeleton."""
    keyword = getattr(trend, "keyword", "")
    index = sum(ord(ch) for ch in keyword) % len(_BLOG_STRUCTURE_POOL)
    label, description = _BLOG_STRUCTURE_POOL[index]
    return f"\n[Blog Structure]\n- Selected layout: {label}\n- {description}\n"


_BIOJUHO_RULES = """You write for @biojuho.

Voice:
- dry wit, compressed sentences, aphoristic finish
- low emoji usage: 0 or 1
- no hashtags unless explicitly requested
- no meme slang or disposable filler
- write Korean that survives auto-translation: simple syntax, concrete nouns, low-local-joke dependency

Do:
- keep one consistent voice across X, Threads, long form, and blog
- prefer one lens per draft: observation, historical parallel, structural reading, counter-thesis, sharp question
- use evidence from the provided context, then add a tighter interpretation
- if the topic is not inherently about AI, do not force it into AI/company/workshop framing

Do not:
- use phrases like "주목받고 있다", "화제가 되고 있다", "정리하면", "살펴보면"
- use slang such as "쩌리", "똥챔프", "깝치다", "현타"
- overuse endings like "~임", "~음"
- mention viral score, engagement forecast, or any internal system metric in public copy
"""


def _system_tweets_biojuho() -> str:
    _biojuho_rules = """You write for @biojuho.

Voice:
- dry wit, compressed sentences, aphoristic finish
- low emoji usage: 0 or 1
- no hashtags unless explicitly requested
- no meme slang or disposable filler
- write Korean that survives auto-translation: simple syntax, concrete nouns, low-local-joke dependency

Do:
- keep one consistent voice across X, Threads, long form, and blog
- prefer one lens per draft: observation, historical parallel, structural reading, counter-thesis, sharp question
- use evidence from the provided context, then add a tighter interpretation
- if the topic is not inherently about AI, do not force it into AI/company/workshop framing

Do not:
- use newsroom filler such as "is getting attention", "is becoming a topic", "to summarize", or "if you look at it this way"
- use slang such as "쩌리", "똥챔프", "깝치다", or "현타"
- overuse blunt sentence endings like repeated "~임" or "~음"
- mention viral score, engagement forecast, or any internal system metric in public copy
"""
    return (
        _biojuho_rules
        + """

Write 5 X drafts in the same voice, but with clearly different lenses:
1. observation
2. historical_parallel
3. structural_read
4. counter_thesis
5. sharp_question

Rules:
- each draft must feel like a different angle, not just a different ending
- each draft must open differently
- keep each draft under 200 characters
- at least one draft must avoid AI framing entirely unless the keyword itself is about AI
- no "our company / our team" placeholder framing

Return JSON only:
{"topic":"topic","tweets":[
{"type":"observation","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"historical_parallel","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"structural_read","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"counter_thesis","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"sharp_question","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."}]}
"""
    )


def _system_threads_biojuho() -> str:
    return (
        _system_tweets_biojuho.__defaults__[0]
        if False
        else """You write for @biojuho.

Voice:
- dry wit, compressed sentences, aphoristic finish
- low emoji usage: 0 or 1
- no hashtags unless explicitly requested
- no meme slang or disposable filler
- write Korean that survives auto-translation: simple syntax, concrete nouns, low-local-joke dependency

Do:
- keep one consistent voice across X, Threads, long form, and blog
- prefer one lens per draft: observation, historical parallel, structural reading, counter-thesis, sharp question
- use evidence from the provided context, then add a tighter interpretation
- if the topic is not inherently about AI, do not force it into AI/company/workshop framing

Do not:
- use newsroom filler such as "is getting attention", "is becoming a topic", "to summarize", or "if you look at it this way"
- use slang such as "쩌리", "똥챔프", "깝치다", or "현타"
- overuse blunt sentence endings like repeated "~임" or "~음"
- mention viral score, engagement forecast, or any internal system metric in public copy
"""
        + """

Write two Threads posts in the same voice:
1. note
2. question

Rules:
- not a news brief and not a lifestyle influencer tone
- more breathing room than X, but still compressed
- 500 chars max each
- no hashtags
- no poll-bait or numbered engagement bait

Return JSON only:
{"posts":[
{"type":"note","content":"..."},
{"type":"question","content":"..."}]}
"""
    )


def _system_long_form_biojuho() -> str:
    return (
        _BIOJUHO_RULES
        + """

Write two long-form outputs:
1. deep_analysis
2. field_note

Rules:
- not a report template
- first 3 lines must state the real tension quickly
- use full paragraphs, not bullet-heavy filler
- avoid "정리하면", "결론적으로", or generic summary endings

Return JSON only:
{"posts":[
{"type":"deep_analysis","content":"..."},
{"type":"field_note","content":"..."}]}
"""
    )


def _system_thread_biojuho() -> str:
    return (
        _BIOJUHO_RULES
        + """

Write a 2-part X thread.
- part 1: hook + analysis
- part 2: pressure point / implication
- no hashtags
- no dashboard language

Return JSON only:
{"hook":"...","tweets":["...","..."]}
"""
    )


def _system_tweets_and_threads_biojuho() -> str:
    return (
        _BIOJUHO_RULES
        + """

Write 5 X drafts and 2 Threads posts in one consistent voice.
The X drafts must use these lenses:
observation, historical_parallel, structural_read, counter_thesis, sharp_question.
The Threads posts must be:
note, question.

Return JSON only:
{"topic":"topic","tweets":[
{"type":"observation","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"historical_parallel","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"structural_read","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"counter_thesis","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"sharp_question","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."}],
"threads_posts":[
{"type":"note","content":"..."},
{"type":"question","content":"..."}]}
"""
    )


def _load_system_prompts_module() -> object:
    try:
        from . import system_prompts as _system_prompts
    except ImportError:
        import system_prompts as _system_prompts
    return _system_prompts


def _system_tweets(tone: str) -> str:
    if tone == "biojuho":
        return _system_tweets_biojuho()
    if tone == "joongyeon":
        return _system_tweets_joongyeon()
    return _load_system_prompts_module()._system_tweets(tone)


def _system_long_form(tone: str, editorial_profile: str = "classic") -> str:
    if tone == "biojuho":
        return _system_long_form_biojuho()
    if editorial_profile == "report":
        return _REPORT_LONG_FORM_SYSTEM
    if tone == "joongyeon":
        return _system_long_form_joongyeon()
    return _load_system_prompts_module()._system_long_form(tone, editorial_profile)


def _system_threads(tone: str, editorial_profile: str = "classic") -> str:
    if tone == "biojuho":
        return _system_threads_biojuho()
    if editorial_profile == "report":
        return _REPORT_THREADS_SYSTEM
    if tone == "joongyeon":
        return _system_threads_joongyeon()
    return _load_system_prompts_module()._system_threads(tone, editorial_profile)


def _system_thread(tone: str) -> str:
    if tone == "biojuho":
        return _system_thread_biojuho()
    return _load_system_prompts_module()._system_thread(tone)


def _system_tweets_and_threads(tone: str) -> str:
    if tone == "biojuho":
        return _system_tweets_and_threads_biojuho()
    return _load_system_prompts_module()._system_tweets_and_threads(tone)


_BIOJUHO_RULES_FINAL = """You write for @biojuho.

Voice:
- dry wit, compressed sentences, aphoristic finish
- low emoji usage: 0 or 1
- no hashtags unless explicitly requested
- no meme slang or disposable filler
- write Korean that survives auto-translation: simple syntax, concrete nouns, low-local-joke dependency

Do:
- keep one consistent voice across X, Threads, long form, and blog
- prefer one lens per draft: observation, historical parallel, structural reading, counter-thesis, sharp question
- use evidence from the provided context, then add a tighter interpretation
- if the topic is not inherently about AI, do not force it into AI/company/workshop framing

Do not:
- use newsroom filler such as "is getting attention", "is becoming a topic", "to summarize", or "if you look at it this way"
- use throwaway meme slang, game-insult slang, or therapy-meme slang
- overuse clipped sentence endings
- mention viral score, engagement forecast, or any internal system metric in public copy
"""


def _system_tweets_biojuho() -> str:
    return (
        _BIOJUHO_RULES_FINAL
        + """

Write 5 X drafts in one voice, but with clearly different lenses:
1. observation
2. historical_parallel
3. structural_read
4. counter_thesis
5. sharp_question

Rules:
- each draft must feel like a different angle, not just a different ending
- each draft must open differently
- keep each draft under 200 characters
- at least one draft must avoid AI framing entirely unless the keyword itself is about AI
- no "our company / our team" placeholder framing

Return JSON only:
{"topic":"topic","tweets":[
{"type":"observation","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"historical_parallel","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"structural_read","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"counter_thesis","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"sharp_question","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."}]}
"""
    )


def _system_threads_biojuho() -> str:
    return (
        _BIOJUHO_RULES_FINAL
        + """

Write two Threads posts in the same voice:
1. note
2. question

Rules:
- not a news brief and not a lifestyle influencer tone
- more breathing room than X, but still compressed
- 500 chars max each
- no hashtags
- no poll-bait or numbered engagement bait

Return JSON only:
{"posts":[
{"type":"note","content":"..."},
{"type":"question","content":"..."}]}
"""
    )


def _system_long_form_biojuho() -> str:
    return (
        _BIOJUHO_RULES_FINAL
        + """

Write two long-form outputs:
1. deep_analysis
2. field_note

Rules:
- not a report template
- first 3 lines must state the real tension quickly
- use full paragraphs, not bullet-heavy filler
- avoid generic summary endings

Return JSON only:
{"posts":[
{"type":"deep_analysis","content":"..."},
{"type":"field_note","content":"..."}]}
"""
    )


def _system_thread_biojuho() -> str:
    return (
        _BIOJUHO_RULES_FINAL
        + """

Write a 2-part X thread.
- part 1: hook + analysis
- part 2: pressure point / implication
- no hashtags
- no dashboard language

Return JSON only:
{"hook":"...","tweets":["...","..."]}
"""
    )


def _system_tweets_and_threads_biojuho() -> str:
    return (
        _BIOJUHO_RULES_FINAL
        + """

Write 5 X drafts and 2 Threads posts in one consistent voice.
The X drafts must use these lenses:
observation, historical_parallel, structural_read, counter_thesis, sharp_question.
The Threads posts must be:
note, question.

Return JSON only:
{"topic":"topic","tweets":[
{"type":"observation","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"historical_parallel","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"structural_read","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"counter_thesis","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},
{"type":"sharp_question","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."}],
"threads_posts":[
{"type":"note","content":"..."},
{"type":"question","content":"..."}]}
"""
    )


def _system_tweets(tone: str) -> str:
    if tone == "biojuho":
        return _system_tweets_biojuho()
    if tone == "joongyeon":
        return _system_tweets_joongyeon()
    try:
        from . import system_prompts as _system_prompts
    except ImportError:
        import system_prompts as _system_prompts
    return _system_prompts._system_tweets(tone)


def _system_long_form(tone: str, editorial_profile: str = "classic") -> str:
    if tone == "biojuho":
        return _system_long_form_biojuho()
    if editorial_profile == "report":
        return _REPORT_LONG_FORM_SYSTEM
    if tone == "joongyeon":
        return _system_long_form_joongyeon()
    try:
        from . import system_prompts as _system_prompts
    except ImportError:
        import system_prompts as _system_prompts
    return _system_prompts._system_long_form(tone, editorial_profile)


def _system_threads(tone: str, editorial_profile: str = "classic") -> str:
    if tone == "biojuho":
        return _system_threads_biojuho()
    if editorial_profile == "report":
        return _REPORT_THREADS_SYSTEM
    if tone == "joongyeon":
        return _system_threads_joongyeon()
    try:
        from . import system_prompts as _system_prompts
    except ImportError:
        import system_prompts as _system_prompts
    return _system_prompts._system_threads(tone, editorial_profile)


def _system_thread(tone: str) -> str:
    if tone == "biojuho":
        return _system_thread_biojuho()
    try:
        from . import system_prompts as _system_prompts
    except ImportError:
        import system_prompts as _system_prompts
    return _system_prompts._system_thread(tone)


def _system_tweets_and_threads(tone: str) -> str:
    if tone == "biojuho":
        return _system_tweets_and_threads_biojuho()
    try:
        from . import system_prompts as _system_prompts
    except ImportError:
        import system_prompts as _system_prompts
    return _system_prompts._system_tweets_and_threads(tone)
