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

try:
    from .config import AppConfig
    from .models import GeneratedTweet, ScoredTrend, TweetBatch
    from .utils import run_async, sanitize_keyword
except ImportError:
    from config import AppConfig
    from models import GeneratedTweet, ScoredTrend, TweetBatch
    from utils import run_async, sanitize_keyword

# [Phase 1] Instructor 구조화된 출력 (선택 의존성)
try:
    try:
        from .structured_output import (
            INSTRUCTOR_AVAILABLE as _INST_OK,
        )
        from .structured_output import (
            TweetGenerationResponse,
            TweetItem,
            extract_structured,
        )
    except ImportError:
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

_TWEET_MAX_CHARS = 240  # [shortform-only] 160~240자 범위 상한 (config.tweet_max_chars와 동기화)
_TWEET_MIN_CHARS = 160  # [shortform-only] 단문 트윗 최소 길이


def _parse_tweets_to_batch(
    data: dict,
    trend: ScoredTrend,
    *,
    variant_id: str = "",
    language: str = "",
    include_extras: bool = True,
) -> TweetBatch | None:
    """JSON 응답을 GeneratedTweet 리스트 → TweetBatch로 변환하는 공통 파서.

    Args:
        include_extras: True면 best_posting_time/expected_engagement/reasoning 포함.
                        A/B 변형 생성에서는 False.
    """
    if not data:
        log.error(f"트윗 생성 JSON 파싱 실패: {trend.keyword}")
        return None

    tweets = []
    for t in data.get("tweets", []):
        content = t.get("content", "")
        if len(content) > _TWEET_MAX_CHARS:
            content = content[: _TWEET_MAX_CHARS - 3] + "..."
            log.warning(f"트윗 {_TWEET_MAX_CHARS}자 초과 트리밍: {trend.keyword} [{t.get('type', '')}]")
        elif len(content) < _TWEET_MIN_CHARS:
            log.warning(
                f"트윗 {_TWEET_MIN_CHARS}자 미만 (실제 {len(content)}자): "
                f"{trend.keyword} [{t.get('type', '')}] — QA에서 감점 처리"
            )
        kwargs: dict = {
            "tweet_type": t.get("type", ""),
            "content": content,
            "content_type": "short",
        }
        if variant_id:
            kwargs["variant_id"] = variant_id
        if language:
            kwargs["language"] = language
        if include_extras:
            kwargs["best_posting_time"] = t.get("best_posting_time", "")
            kwargs["expected_engagement"] = t.get("expected_engagement", "")
            kwargs["reasoning"] = t.get("reasoning", "")
        tweets.append(GeneratedTweet(**kwargs))

    log.info(f"트윗 생성 완료: '{trend.keyword}' ({len(tweets)}개)")
    return TweetBatch(
        topic=data.get("topic", trend.keyword),
        tweets=tweets,
        viral_score=trend.viral_potential,
    )


# -- prompt builder import --
# -- 추출된 모듈 re-export (후방 호환) --
try:
    from .generation.marl import (  # noqa: F401
        _should_use_marl,
        generate_tweets_with_marl_async,
    )
    from .prompt_builder import (  # noqa: F401
        _LANG_NAME_MAP,
        _REPORT_BLOG_SYSTEM,
        _build_account_identity_section,
        _build_ai_frame_guard_section,
        _build_approved_post_bank_section,
        _build_audience_format_section,
        _build_available_facts_section,
        _build_category_tone_hint,
        _build_context_section,
        _build_deep_why_section,
        _build_diversity_section,
        _build_fact_guardrail_section,
        _build_golden_reference_section,
        _build_pattern_weights_section,
        _build_revision_feedback_section,
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
except ImportError:
    from generation.marl import (  # noqa: F401
        _should_use_marl,
        generate_tweets_with_marl_async,
    )
    from prompt_builder import (  # noqa: F401
        _LANG_NAME_MAP,
        _REPORT_BLOG_SYSTEM,
        _build_account_identity_section,
        _build_ai_frame_guard_section,
        _build_approved_post_bank_section,
        _build_audience_format_section,
        _build_available_facts_section,
        _build_category_tone_hint,
        _build_context_section,
        _build_deep_why_section,
        _build_diversity_section,
        _build_fact_guardrail_section,
        _build_golden_reference_section,
        _build_pattern_weights_section,
        _build_revision_feedback_section,
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


def _tweet_generation_user_message(
    trend: ScoredTrend,
    config: AppConfig,
    recent_tweets: list[str] | None,
    approved_post_bank: list[dict[str, Any]] | None,
    golden_refs: list | None,
    pattern_weights: dict | None,
    edape_block: str,
    revision_feedback: dict | None,
) -> str:
    from datetime import datetime as _dt

    target_language = _resolve_language(config)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")
    ai_frame_guard_section = _build_ai_frame_guard_section(trend) if getattr(config, "tone", "") == "biojuho" else ""
    return (
        f"Topic: {safe_keyword}\n"
        f"Current time: {current_time}\n"
        f"Output language: write only in {target_language}.\n"
        f"{_build_account_identity_section(config)}"
        f"{_build_fact_guardrail_section(trend)}"
        f"{_build_deep_why_section(trend)}"
        f"{_build_context_section(trend)}"
        f"{_build_scoring_section(trend)}"
        f"{_build_category_tone_hint(trend)}"
        f"{_build_pattern_weights_section(pattern_weights)}"
        f"{_build_golden_reference_section(golden_refs)}"
        f"{_build_diversity_section(recent_tweets or [])}"
        f"{_build_approved_post_bank_section(approved_post_bank)}"
        f"{_build_revision_feedback_section(revision_feedback)}"
        f"{_build_audience_format_section(trend)}"
        f"{ai_frame_guard_section}"
        f"{edape_block}\n"
        "Write five sharply differentiated tweets. Use concrete facts from context, "
        "but make interpretation and point of view the main value. Output JSON only."
    )


async def _tweet_generation_instructor_data(trend: ScoredTrend, config: AppConfig, user_message: str) -> dict | None:
    if not _INST_OK:
        return None
    try:
        full_prompt = f"[system]\n{_system_tweets(config.tone)}\n\n[user]\n{user_message}"
        inst_result = await extract_structured(
            full_prompt,
            TweetGenerationResponse,
            tier="lightweight",
            max_tokens=1500,
        )
        if inst_result and inst_result.tweets:
            log.info(f"[Instructor] tweet generation parsed: '{trend.keyword}'")
            return inst_result.model_dump()
    except (RuntimeError, ConnectionError, TimeoutError) as e:
        log.debug(f"[Instructor] tweet generation fallback: {type(e).__name__}: {e}")
    return None


async def _tweet_generation_json_data(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    user_message: str,
) -> dict | None:
    try:
        response = await client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=1500,
            policy=_JSON_POLICY,
            system=_system_tweets(config.tone),
            messages=[{"role": "user", "content": user_message}],
        )
        return _parse_json(response.text)
    except (RuntimeError, ConnectionError, TimeoutError) as e:
        log.error(f"Tweet generation LLM failed ({trend.keyword}): {type(e).__name__}: {e}")
    except Exception as e:
        log.error(f"Tweet generation unexpected error ({trend.keyword}): {type(e).__name__}: {e}")
    return None


async def _tweet_generation_data(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    user_message: str,
) -> dict | None:
    data = await _tweet_generation_instructor_data(trend, config, user_message)
    if data is None:
        data = await _tweet_generation_json_data(trend, config, client, user_message)
    if data is None:
        log.warning(f"[retry] JSON parse failed; regenerating once: '{trend.keyword}'")
        data = await _tweet_generation_json_data(trend, config, client, user_message)
    return data


async def generate_tweets_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None = None,
    approved_post_bank: list[dict[str, Any]] | None = None,
    golden_refs: list | None = None,
    pattern_weights: dict | None = None,
    *,
    edape_block: str = "",
    revision_feedback: dict | None = None,
) -> TweetBatch | None:
    """Generate five short tweets asynchronously."""
    user_message = _tweet_generation_user_message(
        trend,
        config,
        recent_tweets,
        approved_post_bank,
        golden_refs,
        pattern_weights,
        edape_block,
        revision_feedback,
    )
    data = await _tweet_generation_data(trend, config, client, user_message)
    return _parse_tweets_to_batch(data, trend)

# -- 추출된 모듈 re-export (후방 호환) --
try:
    from .generation.long_form import (  # noqa: F401
        _BLOG_SYSTEM_JOONGYEON,
        _system_blog_post,
        generate_blog_async,
        generate_long_form_async,
    )
    from .generation.threads import (
        generate_thread_async,
        generate_threads_content_async,
    )
except ImportError:
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
    approved_post_bank: list[dict[str, Any]] | None = None,
    golden_refs: list | None = None,
    pattern_weights: dict | None = None,
    *,
    edape_block: str = "",
) -> TweetBatch | None:
    """단문 트윗과 Threads를 품질 우선으로 분리 생성한 뒤 배치로 합친다."""
    if _PY314_SERIAL_GENERATION:
        try:
            tweet_result = await generate_tweets_async(
                trend,
                config,
                client,
                recent_tweets,
                approved_post_bank,
                golden_refs,
                pattern_weights,
                edape_block=edape_block,
            )
        except Exception as exc:
            tweet_result = exc

        try:
            threads_result = await generate_threads_content_async(trend, config, client)
        except Exception as exc:
            threads_result = exc
    else:
        tweet_result, threads_result = await asyncio.gather(
            generate_tweets_async(
                trend,
                config,
                client,
                recent_tweets,
                approved_post_bank,
                golden_refs,
                pattern_weights,
                edape_block=edape_block,
            ),
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

    log.info(f"통합 생성 완료: '{trend.keyword}' (트윗 {len(batch.tweets)}개 + Threads {len(batch.threads_posts)}개)")
    return batch


# ══════════════════════════════════════════════════════
#  Async Orchestrator — 트렌드 내 모든 생성 병렬 실행
# ══════════════════════════════════════════════════════


async def _resolve_combined_fallback(
    result_map: dict[str, Any],
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    approved_post_bank: list[dict[str, Any]] | None,
    golden_refs: list | None,
    pattern_weights: dict | None,
    *,
    edape_block: str = "",
) -> TweetBatch | None:
    """'combined' 키 결과에서 배치를 추출하고 실패 시 개별 폴백 실행."""
    combined = result_map["combined"]
    if combined and not isinstance(combined, Exception):
        return combined
    if isinstance(combined, Exception):
        log.warning(f"통합 생성 예외, 개별 폴백: {combined}")
    fallback_results = await asyncio.gather(
        generate_tweets_async(
            trend,
            config,
            client,
            None,
            approved_post_bank,
            golden_refs,
            pattern_weights,
            edape_block=edape_block,
        ),
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


def _primary_generation_call(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None,
    approved_post_bank: list[dict[str, Any]] | None,
    golden_refs: list | None,
    pattern_weights: dict | None,
    edape_block: str,
    threads_enabled: bool,
) -> tuple[str, Any]:
    if threads_enabled:
        return (
            "combined",
            generate_tweets_and_threads_async(
                trend,
                config,
                client,
                recent_tweets,
                approved_post_bank,
                golden_refs,
                pattern_weights,
                edape_block=edape_block,
            ),
        )
    return (
        "tweets",
        generate_tweets_async(
            trend,
            config,
            client,
            recent_tweets,
            approved_post_bank,
            golden_refs,
            pattern_weights,
            edape_block=edape_block,
        ),
    )


def _optional_generation_calls(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    blog_enabled: bool,
    gen_tier: TaskTier,
) -> list[tuple[str, Any]]:
    calls: list[tuple[str, Any]] = []
    if config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
        calls.append(("long", generate_long_form_async(trend, config, client, tier=gen_tier)))
    if trend.viral_potential >= config.thread_min_score:
        calls.append(("thread", generate_thread_async(trend, config, client, tier=gen_tier)))
    if blog_enabled:
        calls.append(("blog", generate_blog_async(trend, config, client)))
    return calls


async def _run_serial_generation(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None,
    approved_post_bank: list[dict[str, Any]] | None,
    golden_refs: list | None,
    pattern_weights: dict | None,
    edape_block: str,
    threads_enabled: bool,
    blog_enabled: bool,
    gen_tier: TaskTier,
) -> dict[str, Any]:
    result_map: dict[str, Any] = {}
    primary_key, primary_coro = _primary_generation_call(
        trend,
        config,
        client,
        recent_tweets,
        approved_post_bank,
        golden_refs,
        pattern_weights,
        edape_block,
        threads_enabled,
    )
    try:
        result_map[primary_key] = await primary_coro
    except Exception as exc:
        result_map[primary_key] = exc

    for key, coro in _optional_generation_calls(trend, config, client, blog_enabled, gen_tier):
        try:
            result_map[key] = await coro
        except Exception as exc:
            result_map[key] = exc
    return result_map


async def _run_parallel_generation(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None,
    approved_post_bank: list[dict[str, Any]] | None,
    golden_refs: list | None,
    pattern_weights: dict | None,
    edape_block: str,
    threads_enabled: bool,
    blog_enabled: bool,
    gen_tier: TaskTier,
) -> dict[str, Any]:
    tasks: dict[str, asyncio.Task] = {}
    if threads_enabled:
        tasks["combined"] = asyncio.ensure_future(
            generate_tweets_and_threads_async(
                trend,
                config,
                client,
                recent_tweets,
                approved_post_bank,
                golden_refs,
                pattern_weights,
                edape_block=edape_block,
            )
        )
    else:
        tasks["tweets"] = asyncio.ensure_future(
            generate_tweets_async(
                trend,
                config,
                client,
                recent_tweets,
                approved_post_bank,
                golden_refs,
                pattern_weights,
                edape_block=edape_block,
            )
        )
    if config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
        tasks["long"] = asyncio.ensure_future(generate_long_form_async(trend, config, client, tier=gen_tier))
    if trend.viral_potential >= config.thread_min_score:
        tasks["thread"] = asyncio.ensure_future(generate_thread_async(trend, config, client, tier=gen_tier))
    if blog_enabled:
        tasks["blog"] = asyncio.ensure_future(generate_blog_async(trend, config, client))
    keys = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    return dict(zip(keys, results, strict=False))


async def generate_for_trend_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None = None,
    approved_post_bank: list[dict[str, Any]] | None = None,
    golden_refs: list | None = None,
    pattern_weights: dict | None = None,
    *,
    edape_block: str = "",
) -> TweetBatch | None:
    """Generate the enabled content formats for one scored trend."""
    plan = _generation_plan(trend, config)
    _log_generation_plan(trend, config, plan)
    result_map = await _execute_generation_plan(
        plan,
        trend,
        config,
        client,
        recent_tweets,
        approved_post_bank,
        golden_refs,
        pattern_weights,
        edape_block,
    )
    batch = await _primary_generation_batch(
        result_map,
        trend,
        config,
        client,
        approved_post_bank,
        golden_refs,
        pattern_weights,
        edape_block,
    )
    if not _valid_generation_batch(batch, trend):
        return None

    _attach_optional_results(batch, result_map)
    return batch


def _generation_plan(trend: ScoredTrend, config: AppConfig) -> dict[str, Any]:
    gen_tier = _select_generation_tier(trend, config)
    platforms = getattr(config, "target_platforms", ["x"])
    return {
        "gen_tier": gen_tier,
        "tier_label": "Sonnet" if gen_tier == TaskTier.HEAVY else "Haiku",
        "threads_enabled": (
            config.enable_threads and trend.viral_potential >= config.threads_min_score and "threads" in platforms
        ),
        "blog_enabled": "naver_blog" in platforms and trend.viral_potential >= getattr(config, "blog_min_score", 70),
    }


def _log_generation_plan(trend: ScoredTrend, config: AppConfig, plan: dict[str, Any]) -> None:
    category = getattr(trend, "category", "") or "unclassified"
    tier_parts = ["tweets(5)" + ("+threads(combined)" if plan["threads_enabled"] else "")]
    if config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
        tier_parts.append(f"premium+ long-form({plan['tier_label']})")
    if trend.viral_potential >= config.thread_min_score:
        tier_parts.append(f"x-thread({plan['tier_label']})")
    if plan["blog_enabled"]:
        tier_parts.append("blog(heavy)")
    log.info(f"  [{trend.viral_potential}][{category}] '{trend.keyword}' -> {' + '.join(tier_parts)}")


async def _execute_generation_plan(
    plan: dict[str, Any],
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None,
    approved_post_bank: list[dict[str, Any]] | None,
    golden_refs: list | None,
    pattern_weights: dict | None,
    edape_block: str,
) -> dict[str, Any]:
    runner = _run_serial_generation if _PY314_SERIAL_GENERATION else _run_parallel_generation
    return await runner(
        trend,
        config,
        client,
        recent_tweets,
        approved_post_bank,
        golden_refs,
        pattern_weights,
        edape_block,
        plan["threads_enabled"],
        plan["blog_enabled"],
        plan["gen_tier"],
    )


async def _primary_generation_batch(
    result_map: dict[str, Any],
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    approved_post_bank: list[dict[str, Any]] | None,
    golden_refs: list | None,
    pattern_weights: dict | None,
    edape_block: str,
) -> TweetBatch | Exception | None:
    if "combined" not in result_map:
        return result_map.get("tweets")
    return await _resolve_combined_fallback(
        result_map,
        trend,
        config,
        client,
        approved_post_bank,
        golden_refs,
        pattern_weights,
        edape_block=edape_block,
    )


def _valid_generation_batch(batch: TweetBatch | Exception | None, trend: ScoredTrend) -> bool:
    if isinstance(batch, Exception):
        log.error(f"tweet generation exception ({trend.keyword}): {batch}")
        return False
    return bool(batch)


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
        lang = config.target_languages[0] if config.target_languages else "ko"
        return _parse_tweets_to_batch(data, trend, variant_id="B", language=lang, include_extras=False)

    except (RuntimeError, ConnectionError, TimeoutError) as e:
        log.error(f"A/B 변형 B LLM 실패 ({trend.keyword}): {type(e).__name__}: {e}")
        return None
    except Exception as e:
        log.error(f"A/B 변형 B 예상외 오류 ({trend.keyword}): {type(e).__name__}: {e}")
        return None


# -- backward-compat re-exports --
try:
    from .content_qa import (  # noqa: F401
        audit_generated_content,
        build_regeneration_feedback,
        regenerate_content_groups,
    )
    from .generation.persona import _round_robin_counter, select_persona  # noqa: F401
    from .multilang import (  # noqa: F401
        generate_for_trend_multilang_async,
    )
except ImportError:
    from content_qa import (  # noqa: F401
        audit_generated_content,
        build_regeneration_feedback,
        regenerate_content_groups,
    )
    from generation.persona import _round_robin_counter, select_persona  # noqa: F401
    from multilang import (  # noqa: F401
        generate_for_trend_multilang_async,
    )
