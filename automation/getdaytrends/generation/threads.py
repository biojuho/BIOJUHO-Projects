"""generation/threads.py — Meta Threads + X 쓰레드 생성.

generator.py에서 추출된 모듈.
"""

from loguru import logger as log

from shared.llm import LLMClient, TaskTier
from shared.llm.models import LLMPolicy

try:
    from ..config import AppConfig
    from ..models import GeneratedThread, GeneratedTweet, ScoredTrend
    from ..prompt_builder import (
        _build_account_identity_section,
        _build_audience_format_section,
        _build_context_section,
        _build_deep_why_section,
        _build_fact_guardrail_section,
        _build_revision_feedback_section,
        _build_scoring_section,
        _parse_json,
        _resolve_language,
        _system_thread,
        _system_threads,
        _use_report_profile,
    )
    from ..utils import sanitize_keyword
except ImportError:
    from config import AppConfig
    from models import GeneratedThread, GeneratedTweet, ScoredTrend
    from prompt_builder import (
        _build_account_identity_section,
        _build_audience_format_section,
        _build_context_section,
        _build_deep_why_section,
        _build_fact_guardrail_section,
        _build_revision_feedback_section,
        _build_scoring_section,
        _parse_json,
        _resolve_language,
        _system_thread,
        _system_threads,
        _use_report_profile,
    )
    from utils import sanitize_keyword

_JSON_POLICY = LLMPolicy(response_mode="json")


# ══════════════════════════════════════════════════════
#  Meta Threads 콘텐츠 (500자) — Haiku tier
# ══════════════════════════════════════════════════════


async def generate_threads_content_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    *,
    revision_feedback: dict | None = None,
) -> list[GeneratedTweet]:
    """Meta Threads 최적화 콘텐츠 비동기 생성 (Haiku — 단문)."""
    from datetime import datetime as _dt

    report_profile = _use_report_profile(config)
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    deep_why_section = _build_deep_why_section(trend)
    fact_guardrail_section = _build_fact_guardrail_section(trend)
    revision_feedback_section = _build_revision_feedback_section(revision_feedback)
    identity_section = _build_account_identity_section(config, include_tone=not report_profile)
    audience_format_section = _build_audience_format_section(trend)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{identity_section}{fact_guardrail_section}{deep_why_section}{context_section}{scoring_section}"
        f"{revision_feedback_section}{audience_format_section}\n"
        + (
            "위 배경과 컨텍스트를 소화한 뒤, Threads용 리포트형 포스트 2개를 작성.\n"
            "핵심: 뉴스 전달이 아니라 '이 현상에 대한 내 해석'.\n"
            "컨텍스트의 구체적 수치/사건을 반드시 활용할 것.\n"
            "1) 핵심 브리프: 지금 중요한 사실과 의미를 간결하게 정리\n"
            "2) 쟁점 질문: 팩트를 짚은 뒤 생각할 질문 하나만 남기기\n\n"
            if report_profile
            else "위 배경과 컨텍스트를 소화한 뒤, Threads에서 '친구한테 공유' 하고 싶은 글 작성.\n"
            "핵심: 뉴스 전달이 아니라 '이 현상에 대한 내 해석'.\n"
            "컨텍스트의 구체적 수치/사건을 반드시 활용할 것.\n"
            "1) 훅 포스트: 구체적 팩트/숫자로 스크롤 멈추게\n"
            "2) 참여형 포스트: 공감 스토리 + 양자택일 질문\n\n"
        )
        + "각 포스트 500자 이내. 반드시 JSON만 출력하세요."
    )

    try:
        response = await client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=1200,
            policy=_JSON_POLICY,
            system=_system_threads(config.tone, config.editorial_profile),
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json(response.text)

        if not data:
            log.warning(f"Threads 생성 JSON 파싱 실패: {trend.keyword}")
            return []

        posts = [
            GeneratedTweet(
                tweet_type=p.get("type", "Threads"),
                content=p.get("content", ""),
                content_type="threads",
            )
            for p in data.get("posts", [])
        ]

        log.info(f"Threads 생성 완료: '{trend.keyword}' ({len(posts)}개)")
        return posts

    except Exception as e:
        log.error(f"Threads 생성 실패 ({trend.keyword}): {e}")
        return []


# ══════════════════════════════════════════════════════
#  X 쓰레드 (Premium+ 강화: 2트윗) — Sonnet tier
# ══════════════════════════════════════════════════════


async def generate_thread_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    tier: TaskTier = TaskTier.HEAVY,
) -> GeneratedThread | None:
    """고바이럴 트렌드용 강화 쓰레드 비동기 생성 (기본 Sonnet, 경량 카테고리는 Haiku)."""
    context_text = trend.context.to_combined_text() if trend.context else ""
    target_language = _resolve_language(config)
    safe_keyword = sanitize_keyword(trend.keyword)
    angles_text = ", ".join(trend.suggested_angles) if trend.suggested_angles else "없음"

    user_message = (
        f"주제: {safe_keyword}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n\n"
        f"[실시간 데이터]\n{context_text}\n\n"
        f"[분석 요약]\n"
        f"- 바이럴 점수: {trend.viral_potential}/100\n"
        f"- 핵심: {trend.top_insight}\n"
        f"- 추천 훅: {trend.best_hook_starter}\n"
        f"- 추천 앵글: {angles_text}\n\n"
        "위 데이터를 기반으로 정확히 2개 트윗의 바이럴 쓰레드를 JSON 형식으로 작성해주세요.\n"
        "첫 트윗(훅)은 최대 2,500자까지 충분히 길게 작성 가능합니다.\n"
        "나머지 트윗도 각 500~1,000자로 깊이 있게 작성해주세요."
    )

    try:
        response = await client.acreate(
            tier=tier,
            max_tokens=5000,
            policy=_JSON_POLICY,
            system=_system_thread(config.tone),
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json(response.text)

        if not data:
            log.warning(f"쓰레드 JSON 파싱 실패: {trend.keyword}")
            return None

        thread_tweets = data.get("tweets", [])
        hook = data.get("hook", thread_tweets[0] if thread_tweets else "")

        total_chars = sum(len(t) for t in thread_tweets)
        log.info(f"쓰레드 생성 완료: '{trend.keyword}' ({len(thread_tweets)}개 트윗, 총 {total_chars}자)")
        return GeneratedThread(tweets=thread_tweets, hook=hook)

    except Exception as e:
        log.error(f"쓰레드 생성 실패 ({trend.keyword}): {e}")
        return None
