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
                    f"생성 재시도 ({attempt + 1}/{max_retries}) '{keyword}': " f"{type(e).__name__} → {delay:.0f}s 후"
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


def _build_revision_feedback_section(revision_feedback: dict | None) -> str:
    """Inject retry-specific QA / fact-check guidance into regeneration prompts."""
    if not revision_feedback:
        return ""

    lines = [
        "",
        "[재생성 보정 지시]",
        "- 이번 출력은 자동 QA 또는 FactCheck 실패 후 다시 쓰는 버전이다.",
        "- 핵심 인사이트는 유지하되, 문장만 조금 고치는 수준이 아니라 처음부터 다시 작성할 것.",
    ]

    qa = revision_feedback.get("qa") or {}
    if qa:
        qa_total = qa.get("total")
        qa_threshold = qa.get("threshold")
        weakest_axis = qa.get("worst_axis") or ""
        axis_guidance = {
            "hook": "첫 문장은 숫자, 대비, 질문, 강한 관찰 중 하나로 바로 주목도를 만들어라.",
            "fact": "컨텍스트에 직접 있는 고유명사, 수치, 인용만 사용하고 추정 사실은 새로 만들지 마라.",
            "tone": "상투구, AI 말투, 기사체 표현을 줄이고 사람이 바로 말하는 듯한 문장으로 바꿔라.",
            "kick": "마무리는 밋밋한 정리 대신 독자가 가져갈 해석이나 한 줄 관찰로 끝내라.",
            "angle": "뉴스 요약 반복을 피하고, 왜 중요한지에 대한 명확한 관점이나 해석을 추가하라.",
            "regulation": "플랫폼 규칙을 엄수하고 길이, 형식, 해시태그 제한을 다시 점검하라.",
            "algorithm": "스크롤을 멈추게 하는 구조와 참여를 부르는 흐름을 더 분명히 설계하라.",
        }
        lines.append(
            f"- QA 총점/기준: "
            f"{qa_total if qa_total not in (None, '') else '?'}/"
            f"{qa_threshold if qa_threshold not in (None, '') else '?'}"
        )
        if weakest_axis:
            lines.append(f"- 가장 약한 축: {weakest_axis}")
        if qa.get("reason"):
            lines.append(f"- 대표 실패 사유: {qa['reason']}")
        for issue in list(qa.get("issues", []) or [])[:3]:
            lines.append(f"- 보완 포인트: {issue}")
        if qa.get("fact_violation"):
            lines.append("- 컨텍스트 밖 고유명사, 수치, 출처 불명 인용은 모두 제거하거나 완곡하게 낮춰라.")
        if (qa.get("regulation") or 10) <= 3:
            lines.append("- 이전 출력에서 플랫폼 규칙 위반이 있었으니 형식 규칙을 우선적으로 바로잡아라.")
        if weakest_axis in axis_guidance:
            lines.append(f"- 우선 수정 방향: {axis_guidance[weakest_axis]}")

    fact_check = revision_feedback.get("fact_check") or {}
    if fact_check:
        accuracy_score = fact_check.get("accuracy_score")
        if fact_check.get("summary"):
            lines.append(f"- FactCheck 요약: {fact_check['summary']}")
        if accuracy_score is not None:
            with contextlib.suppress(TypeError, ValueError):
                lines.append(f"- 검증 정확도: {float(accuracy_score):.0%}")
        if fact_check.get("hallucinated_claims", 0):
            lines.append(
                f"- 환각 의심 주장 수: {fact_check.get('hallucinated_claims', 0)}"
            )
        for issue in list(fact_check.get("issues", []) or [])[:3]:
            lines.append(f"- 제거 또는 완화할 주장: {issue}")
        lines.append("- 소스에서 직접 확인된 사실만 단정형으로 쓰고, 불확실한 내용은 추정 표현으로 낮춰라.")

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
    raw_blocks: list[str] = []
    if getattr(trend, "trend_context", None):
        raw_blocks.append(trend.trend_context.to_prompt_text())
    if getattr(trend, "context", None):
        raw_blocks.append(trend.context.to_combined_text())
    if getattr(trend, "top_insight", ""):
        raw_blocks.append(trend.top_insight)
    if getattr(trend, "why_trending", ""):
        raw_blocks.append(trend.why_trending)

    facts: list[str] = []
    seen: set[str] = set()
    for block in raw_blocks:
        for raw_line in block.splitlines():
            line = _clean_fact_line(raw_line)
            if not line:
                continue
            key = line.casefold()
            if key in seen:
                continue
            seen.add(key)
            if len(line) > 220:
                line = line[:217].rstrip() + "..."
            facts.append(line)
            if len(facts) >= limit:
                break
        if len(facts) >= limit:
            break

    if not facts:
        return ""
    bullets = "\n".join(f"- {fact}" for fact in facts)
    return f"\n[사용 가능한 사실]\n{bullets}\n"


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
    return rules + facts_section


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


def _build_pattern_weights_section(pattern_weights: dict | None) -> str:
    """[B] 훅/킥/앵글 패턴별 성과 가중치를 프롬프트에 주입 — 고성과 패턴 우선 사용 유도."""
    if not pattern_weights:
        return ""
    hook_w = pattern_weights.get("hook_weights", {})
    kick_w = pattern_weights.get("kick_weights", {})
    angle_w = pattern_weights.get("angle_weights", {})

    if not hook_w and not kick_w and not angle_w:
        return ""

    hook_labels = {
        "number_shock": "숫자충격", "relatable_math": "체감환산", "reversal": "반전선언",
        "insider": "내부자시선", "contrast": "대조병치", "question": "질문도발",
    }
    kick_labels = {
        "mic_drop": "뒤통수", "self_deprecation": "자조형", "uncertainty": "질문형",
        "manifesto": "선언형", "twist": "반전형",
    }
    angle_labels = {
        "reversal": "반전시각", "data_punch": "데이터펀치", "empathy": "공감형",
        "tips": "실용팁", "debate": "논쟁유발",
    }

    lines = ["\n[성과 기반 패턴 가중치 — 높은 가중치 패턴을 우선 사용할 것]"]
    if hook_w:
        hook_sorted = sorted(hook_w.items(), key=lambda x: x[1], reverse=True)[:3]
        lines.append("- 훅(첫 문장) 성과 순위: " + ", ".join(f"{hook_labels.get(k, k)}({v:.0%})" for k, v in hook_sorted))
    if kick_w:
        kick_sorted = sorted(kick_w.items(), key=lambda x: x[1], reverse=True)[:3]
        lines.append("- 킥(마무리) 성과 순위: " + ", ".join(f"{kick_labels.get(k, k)}({v:.0%})" for k, v in kick_sorted))
    if angle_w:
        angle_sorted = sorted(angle_w.items(), key=lambda x: x[1], reverse=True)[:2]
        lines.append("- 앵글(전달 시각) 성과 순위: " + ", ".join(f"{angle_labels.get(k, k)}({v:.0%})" for k, v in angle_sorted))

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


def _parse_json(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        preview = raw[:200].replace("\n", "\\n")
        log.warning(f"[_parse_json] JSON 파싱 실패: {exc} | 원본 미리보기: {preview}")
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

