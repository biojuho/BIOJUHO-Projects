"""
getdaytrends v4.1 - Tweet & Thread & Long-form & Threads Generation
컨텍스트 기반 트윗 3종 + X Premium+ 장문 + Meta Threads 3종 + 강화 쓰레드 3개.
async/await 기반 병렬 생성 + JSON structured output 지원.

v4.1 변경 (프롬프트 고도화):
- Few-shot 예시 추가: 좋은 글/나쁜 글 대비로 LLM 방향 유도
- 훅(첫 문장) 패턴 라이브러리: 6가지 시작 방식 (숫자충격/체감환산/반전선언/내부자/대조/질문)
- 킥(마무리) 패턴 라이브러리: 5가지 마무리 방식 (뒤통수/자조/질문/선언/반전)
- 앵글 분화 강화: 5개 트윗 각도별 구체적 예시 + 시작 방식 교차 강제
- 금지 패턴 확장: 설명체/간접인용/상투구 추가
- 핵심 마인드셋: 정보 30% + 해석 70% 비율 명시
- 장문/Threads 프롬프트 동일 수준 고도화
"""

import asyncio
import sys
from typing import Any

from loguru import logger as log
from shared.llm import LLMClient, TaskTier
from shared.llm.models import LLMPolicy

from config import AppConfig
from models import GeneratedTweet, ScoredTrend, TweetBatch
from utils import run_async, sanitize_keyword

# [Phase 1] Instructor 구조화된 출력 (선택 의존성)
try:
    from structured_output import (
        INSTRUCTOR_AVAILABLE as _INST_OK,
    )
    from structured_output import (
        TweetGenerationResponse,
        TweetItem,
        extract_structured,
    )
except ImportError:
    _INST_OK = False

_JSON_POLICY = LLMPolicy(response_mode="json")
_PY314_SERIAL_GENERATION = sys.version_info >= (3, 14)


# -- prompt builder import --
# -- 추출된 모듈 re-export (후방 호환) --
from generation.marl import (  # noqa: F401
    _should_use_marl,
    generate_tweets_with_marl_async,
)
from prompt_builder import (  # noqa: F401
    _LANG_NAME_MAP,
    _REPORT_BLOG_SYSTEM,
    _build_account_identity_section,
    _build_audience_format_section,
    _build_available_facts_section,
    _build_category_tone_hint,
    _build_context_section,
    _build_deep_why_section,
    _build_diversity_section,
    _build_fact_guardrail_section,
    _build_golden_reference_section,
    _build_pattern_weights_section,
    _build_scoring_section,
    _parse_json,
    _resolve_language,
    _retry_generate,
    _select_generation_tier,
    _system_long_form,
    _system_thread,
    _system_threads,
    _system_tweets,
    _system_tweets_and_threads,
    _use_report_profile,
)

# ══════════════════════════════════════════════════════
#  1) 단문 트윗 5종 (280자) — Haiku tier
# ══════════════════════════════════════════════════════


async def generate_tweets_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None = None,
    golden_refs: list | None = None,
    pattern_weights: dict | None = None,
) -> TweetBatch | None:
    """5종 단문 트윗 비동기 생성 (Haiku — 비용 절감).
    [v9.0] recent_tweets: 이전 생성 내용 주입으로 표현 다양성 보장.
    [v5.0] golden_refs: 골든 레퍼런스 벤치마크 (E. Benchmark QA).
    [v5.0] pattern_weights: 훅/킥 성과 가중치 (B. Adaptive Voice).
    """
    from datetime import datetime as _dt

    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    identity_section = _build_account_identity_section(config)
    diversity_section = _build_diversity_section(recent_tweets or [])
    category_hint = _build_category_tone_hint(trend)
    deep_why_section = _build_deep_why_section(trend)
    golden_ref_section = _build_golden_reference_section(golden_refs)
    pattern_weights_section = _build_pattern_weights_section(pattern_weights)
    audience_format_section = _build_audience_format_section(trend)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{identity_section}{deep_why_section}{context_section}{scoring_section}"
        f"{category_hint}{pattern_weights_section}{golden_ref_section}{diversity_section}{audience_format_section}\n"
        "위 배경과 컨텍스트를 깊이 소화한 뒤, 쟁점을 추출하고 각 쟁점별로 날카로운 각도의 트윗 작성.\n"
        "중요: 너는 뉴스를 '전달'하는 사람이 아니라 뉴스를 보고 '한마디 하는' 사람임.\n"
        "정보 전달 30% + 너의 해석/시각 70% 비율로 작성.\n"
        "컨텍스트의 구체적 수치/사건/반응을 반드시 활용하되, 그걸 '내 관점'으로 재해석할 것.\n"
        "5개 트윗의 첫 문장이 전부 다른 방식으로 시작해야 함.\n"
        "반드시 JSON만 출력."
    )

    # [Phase 1] Instructor 우선 시도 → 실패 시 기존 JSON 파싱 폴백
    data = None
    if _INST_OK:
        try:
            full_prompt = f"[시스템]\n{_system_tweets(config.tone)}\n\n[사용자]\n{user_message}"
            inst_result = await extract_structured(
                full_prompt,
                TweetGenerationResponse,
                tier="lightweight",
                max_tokens=1500,
            )
            if inst_result and inst_result.tweets:
                data = inst_result.model_dump()
                log.info(f"[Instructor] 트윗 생성 파싱 성공: '{trend.keyword}'")
        except Exception as e:
            log.debug(f"[Instructor] 트윗 생성 폴백: {e}")

    if data is None:
        try:
            response = await client.acreate(
                tier=TaskTier.LIGHTWEIGHT,
                max_tokens=1500,
                policy=_JSON_POLICY,
                system=_system_tweets(config.tone),
                messages=[{"role": "user", "content": user_message}],
            )
            data = _parse_json(response.text)
        except Exception as e:
            log.error(f"트윗 생성 실패 ({trend.keyword}): {e}")
            return None

    if not data:
        log.error(f"트윗 생성 JSON 파싱 실패: {trend.keyword}")
        return None

    tweets = []
    for t in data.get("tweets", []):
        content = t.get("content", "")
        if len(content) > 280:
            content = content[:277] + "..."
            log.warning(f"트윗 280자 초과 트리밍: {trend.keyword} [{t.get('type', '')}]")
        tweets.append(
            GeneratedTweet(
                tweet_type=t.get("type", ""),
                content=content,
                content_type="short",
                best_posting_time=t.get("best_posting_time", ""),
                expected_engagement=t.get("expected_engagement", ""),
                reasoning=t.get("reasoning", ""),
            )
        )

    log.info(f"트윗 생성 완료: '{trend.keyword}' ({len(tweets)}개)")
    return TweetBatch(
        topic=data.get("topic", trend.keyword),
        tweets=tweets,
        viral_score=trend.viral_potential,
    )


# -- 추출된 모듈 re-export (후방 호환) --
from generation.long_form import (  # noqa: F401
    _BLOG_SYSTEM_JOONGYEON,
    _system_blog_post,
    generate_blog_async,
    generate_long_form_async,
)
from generation.threads import (
    generate_thread_async,
    generate_threads_content_async,
)

# ══════════════════════════════════════════════════════
#  5) 통합 배치 생성: 단문 5종 + Threads 2종 (1회 호출) — Haiku tier
# ══════════════════════════════════════════════════════


async def generate_tweets_and_threads_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None = None,
    golden_refs: list | None = None,
    pattern_weights: dict | None = None,
) -> TweetBatch | None:
    """단문 트윗과 Threads를 품질 우선으로 분리 생성한 뒤 배치로 합친다."""
    if _PY314_SERIAL_GENERATION:
        try:
            tweet_result = await generate_tweets_async(
                trend, config, client, recent_tweets, golden_refs, pattern_weights
            )
        except Exception as exc:
            tweet_result = exc

        try:
            threads_result = await generate_threads_content_async(trend, config, client)
        except Exception as exc:
            threads_result = exc
    else:
        tweet_result, threads_result = await asyncio.gather(
            generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights),
            generate_threads_content_async(trend, config, client),
            return_exceptions=True,
        )

    if isinstance(tweet_result, Exception):
        log.error(f"통합 생성(트윗) 실패 ({trend.keyword}): {tweet_result}")
        return None

    batch = tweet_result
    if not batch:
        return None

    if isinstance(threads_result, Exception):
        log.warning(f"통합 생성(Threads) 실패 ({trend.keyword}): {threads_result}")
    elif threads_result:
        batch.threads_posts = threads_result

    log.info(
        f"통합 생성 완료: '{trend.keyword}' " f"(트윗 {len(batch.tweets)}개 + Threads {len(batch.threads_posts)}개)"
    )
    return batch


# ══════════════════════════════════════════════════════
#  Async Orchestrator — 트렌드 내 모든 생성 병렬 실행
# ══════════════════════════════════════════════════════


async def _resolve_combined_fallback(
    result_map: dict[str, Any],
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    golden_refs: list | None,
    pattern_weights: dict | None,
) -> TweetBatch | None:
    """'combined' 키 결과에서 배치를 추출하고 실패 시 개별 폴백 실행."""
    combined = result_map["combined"]
    if combined and not isinstance(combined, Exception):
        return combined
    if isinstance(combined, Exception):
        log.warning(f"통합 생성 예외, 개별 폴백: {combined}")
    fallback_results = await asyncio.gather(
        generate_tweets_async(trend, config, client, None, golden_refs, pattern_weights),
        generate_threads_content_async(trend, config, client),
        return_exceptions=True,
    )
    batch = fallback_results[0] if not isinstance(fallback_results[0], Exception) else None
    if batch and not isinstance(fallback_results[1], Exception) and fallback_results[1]:
        batch.threads_posts = fallback_results[1]
    return batch


def _attach_optional_results(batch: TweetBatch, result_map: dict[str, Any]) -> None:
    """result_map의 선택적 생성 결과(장문/쓰레드/블로그)를 배치에 병합."""
    for key, attr in (("long", "long_posts"), ("thread", "thread"), ("blog", "blog_posts")):
        result = result_map.get(key)
        if result and not isinstance(result, Exception):
            setattr(batch, attr, result)


async def generate_for_trend_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None = None,
    golden_refs: list | None = None,
    pattern_weights: dict | None = None,
) -> TweetBatch | None:
    """
    오케스트레이터 (비동기): 트윗 5종 + 조건부 장문/Threads/쓰레드/블로그 동시 생성.

    C1 최적화: Threads 활성 시 단문+Threads를 통합 1회 호출로 처리.
    [v12.0] target_platforms 기반 멀티플랫폼 라우팅.
    [v9.0] recent_tweets: 이전 생성 표현 주입 (콘텐츠 다양성).
    [v5.0] golden_refs / pattern_weights: 성과 기반 벤치마크 + 패턴 가중치.
    """
    gen_tier = _select_generation_tier(trend, config)
    category = getattr(trend, "category", "") or "미분류"
    tier_label = "Sonnet" if gen_tier == TaskTier.HEAVY else "Haiku↓"
    platforms = getattr(config, "target_platforms", ["x"])

    threads_enabled = (
        config.enable_threads and trend.viral_potential >= config.threads_min_score and "threads" in platforms
    )
    blog_enabled = "naver_blog" in platforms and trend.viral_potential >= getattr(config, "blog_min_score", 70)

    tier_parts = ["단문(5종)" + ("+Threads(통합)" if threads_enabled else "")]
    if config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
        tier_parts.append(f"Premium+장문({tier_label})")
    if trend.viral_potential >= config.thread_min_score:
        tier_parts.append(f"X쓰레드({tier_label})")
    if blog_enabled:
        tier_parts.append("블로그(HEAVY)")
    log.info(f"  [{trend.viral_potential}점/{category}] '{trend.keyword}' → {' + '.join(tier_parts)}")

    # 직렬 실행 경로 (Python 3.14+ 호환용)
    if _PY314_SERIAL_GENERATION:
        result_map: dict[str, Any] = {}
        primary_key = "combined" if threads_enabled else "tweets"
        primary_coro = (
            generate_tweets_and_threads_async(trend, config, client, recent_tweets, golden_refs, pattern_weights)
            if threads_enabled
            else generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights)
        )
        try:
            result_map[primary_key] = await primary_coro
        except Exception as exc:
            result_map[primary_key] = exc

        for key, coro in [
            ("long", generate_long_form_async(trend, config, client, tier=gen_tier)
             if config.enable_long_form and trend.viral_potential >= config.long_form_min_score else None),
            ("thread", generate_thread_async(trend, config, client, tier=gen_tier)
             if trend.viral_potential >= config.thread_min_score else None),
            ("blog", generate_blog_async(trend, config, client) if blog_enabled else None),
        ]:
            if coro is not None:
                try:
                    result_map[key] = await coro
                except Exception as exc:
                    result_map[key] = exc
    else:
        # 병렬 실행 경로 (기본)
        tasks: dict[str, asyncio.Task] = {}
        if threads_enabled:
            tasks["combined"] = asyncio.ensure_future(
                generate_tweets_and_threads_async(trend, config, client, recent_tweets, golden_refs, pattern_weights)
            )
        else:
            tasks["tweets"] = asyncio.ensure_future(
                generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights)
            )
        if config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
            tasks["long"] = asyncio.ensure_future(generate_long_form_async(trend, config, client, tier=gen_tier))
        if trend.viral_potential >= config.thread_min_score:
            tasks["thread"] = asyncio.ensure_future(generate_thread_async(trend, config, client, tier=gen_tier))
        if blog_enabled:
            tasks["blog"] = asyncio.ensure_future(generate_blog_async(trend, config, client))
        keys = list(tasks.keys())
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        result_map = dict(zip(keys, results, strict=False))

    # 기본 배치 추출 (combined 또는 tweets)
    if "combined" in result_map:
        batch = await _resolve_combined_fallback(result_map, trend, config, client, golden_refs, pattern_weights)
    else:
        batch = result_map.get("tweets")

    if not batch or isinstance(batch, Exception):
        if isinstance(batch, Exception):
            log.error(f"트윗 생성 예외 ({trend.keyword}): {batch}")
        return None

    _attach_optional_results(batch, result_map)
    return batch


def generate_for_trend(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
) -> TweetBatch | None:
    """동기 래퍼 (하위 호환)."""
    return run_async(generate_for_trend_async(trend, config, client))


# ══════════════════════════════════════════════════════
#  Phase 4: A/B 변형 생성
# ══════════════════════════════════════════════════════

_AB_TONE_B = "직설적이고 논쟁적인 논평가"  # 변형 B 고정 톤


async def generate_ab_variant_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
) -> TweetBatch | None:
    """
    A/B 변형 B: 기본 톤과 다른 스타일(직설적·논쟁적)로 단문 트윗 5종 생성.
    결과 tweets의 variant_id="B", language=기본언어.
    실패 시 None 반환.
    """
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    safe_keyword = sanitize_keyword(trend.keyword)

    user_message = (
        f"오늘 다룰 주제/상황: {safe_keyword}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{context_section}{scoring_section}\n"
        "위 데이터를 참고하여 5가지 유형의 트윗 시안을 JSON 형식으로만 작성해주세요.\n"
        "반드시 JSON만 출력하고 다른 설명은 일절 없어야 합니다."
    )

    try:
        response = await client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=1500,
            policy=_JSON_POLICY,
            system=_system_tweets(_AB_TONE_B),
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json(response.text)
        if not data:
            return None

        tweets = []
        for t in data.get("tweets", []):
            content = t.get("content", "")
            if len(content) > 280:
                content = content[:277] + "..."
            tweets.append(
                GeneratedTweet(
                    tweet_type=t.get("type", ""),
                    content=content,
                    content_type="short",
                    variant_id="B",
                    language=config.target_languages[0] if config.target_languages else "ko",
                )
            )

        log.info(f"A/B 변형 B 생성 완료: '{trend.keyword}' ({len(tweets)}개)")
        return TweetBatch(topic=data.get("topic", trend.keyword), tweets=tweets, viral_score=trend.viral_potential)

    except Exception as e:
        log.error(f"A/B 변형 B 생성 실패 ({trend.keyword}): {e}")
        return None


# -- backward-compat re-exports --
from content_qa import (  # noqa: F401
    audit_generated_content,
    regenerate_content_groups,
)
from generation.persona import _round_robin_counter, select_persona  # noqa: F401
from multilang import (  # noqa: F401
    generate_for_trend_multilang_async,
)
