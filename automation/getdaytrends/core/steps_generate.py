"""
getdaytrends — Step 3: Content Generation
트윗/쓰레드 전체 병렬 생성 (캐시 우선 + EDAPE 적응형 프롬프트 + TAP 선점).
core/pipeline_steps.py에서 분리됨.
"""

import asyncio
import contextlib
import dataclasses
import re
import sqlite3

from loguru import logger as log

from shared.llm import get_client

# Optional dependencies — gracefully degrade when unavailable
try:
    try:
        from ..performance_tracker import PerformanceTracker
    except ImportError:
        from performance_tracker import PerformanceTracker
except ImportError:
    PerformanceTracker = None  # type: ignore[assignment,misc]

try:
    try:
        from ..fact_checker import check_cross_source_consistency
        from ..fact_checker import verify_batch as verify_fact_batch
    except ImportError:
        from fact_checker import check_cross_source_consistency
        from fact_checker import verify_batch as verify_fact_batch
except ImportError:
    check_cross_source_consistency = None  # type: ignore[assignment]
    verify_fact_batch = None  # type: ignore[assignment]

try:
    from shared.embeddings import cosine_similarity as _cosine_similarity
    from shared.embeddings import embed_texts as _embed_texts
except ImportError:
    _cosine_similarity = None  # type: ignore[assignment]
    _embed_texts = None  # type: ignore[assignment]

try:
    from ..config import VERSION, AppConfig
    from ..db import (
        compute_fingerprint,
        get_approved_post_bank,
        get_cached_content,
        get_recent_tweet_contents,
        record_posting_time_stat,
    )
    from ..generator import (
        audit_generated_content,
        build_regeneration_feedback,
        generate_for_trend_async,
        regenerate_content_groups,
    )
    from ..models import GeneratedTweet, TweetBatch
except ImportError:
    from config import VERSION, AppConfig
    from db import (
        compute_fingerprint,
        get_approved_post_bank,
        get_cached_content,
        get_recent_tweet_contents,
    )
    from generator import (
        audit_generated_content,
        build_regeneration_feedback,
        generate_for_trend_async,
        regenerate_content_groups,
    )
    from models import GeneratedTweet, TweetBatch


# ══════════════════════════════════════════════════════
#  Helper Functions
# ══════════════════════════════════════════════════════


def _content_hub_enabled(config: AppConfig) -> bool:
    if getattr(config, "storage_type", "none") not in ("notion", "both"):
        return False
    if not getattr(config, "enable_content_hub", False):
        return False

    hub_db_id = (getattr(config, "content_hub_database_id", "") or "").replace("-", "")
    notion_db_id = (getattr(config, "notion_database_id", "") or "").replace("-", "")
    if not hub_db_id:
        return False
    return not (notion_db_id and hub_db_id == notion_db_id)


def _should_skip_qa(trend, is_cached: bool, config: AppConfig) -> bool:
    if not getattr(config, "enable_quality_feedback", True):
        return True
    if is_cached and getattr(config, "qa_skip_cached", True):
        return True
    skip_score = getattr(config, "qa_skip_high_score", 85)
    if trend.viral_potential >= skip_score:
        return True
    skip_cats = set(getattr(config, "qa_skip_categories", []))
    category = getattr(trend, "category", "") or ""
    return category in skip_cats


def _is_accelerating(trend_acceleration: str) -> bool:
    if "급상승" in trend_acceleration:
        return True
    m = re.search(r"\+(\d+(?:\.\d+)?)\s*%?", trend_acceleration)
    if m:
        try:
            return float(m.group(1)) >= 3.0
        except ValueError:
            pass
    return False


def _batch_from_cache(topic: str, rows: list[dict]) -> TweetBatch:
    tweets: list[GeneratedTweet] = []
    long_posts: list[GeneratedTweet] = []
    threads_posts: list[GeneratedTweet] = []
    blog_posts: list[GeneratedTweet] = []
    seen: set[tuple[str, str]] = set()

    for row in rows:
        content_type = row.get("content_type", "short")
        tweet_type = row.get("tweet_type", "")
        if (tweet_type, content_type) in seen:
            continue
        seen.add((tweet_type, content_type))

        tweet = GeneratedTweet(
            tweet_type=tweet_type,
            content=row["content"],
            content_type=content_type,
            char_count=row.get("char_count", len(row["content"])),
        )
        if content_type == "long":
            long_posts.append(tweet)
        elif content_type == "threads":
            threads_posts.append(tweet)
        elif content_type == "naver_blog":
            blog_posts.append(tweet)
        else:
            tweets.append(tweet)

    return TweetBatch(
        topic=topic,
        tweets=tweets,
        long_posts=long_posts,
        threads_posts=threads_posts,
        blog_posts=blog_posts,
        viral_score=0,
    )


async def _load_adaptive_voice(config: AppConfig) -> tuple[list | None, dict | None, str]:
    """Load EDAPE context, adaptive voice weights, and golden references."""
    edape_block = await _load_edape_block(config)
    if not _needs_voice_tracker(config):
        return None, None, edape_block
    tracker = _voice_tracker(config)
    if tracker is None:
        return None, None, edape_block
    pattern_weights, golden_refs = await _load_voice_assets(config, tracker)
    return golden_refs, pattern_weights, edape_block


async def _load_edape_block(config: AppConfig) -> str:
    if not getattr(config, "enable_edape", True):
        log.debug("  [EDAPE] disabled (config.enable_edape=False)")
        return ""
    try:
        from edape import build_adaptive_context_async

        adaptive_ctx = await build_adaptive_context_async(config)
        edape_block = adaptive_ctx.to_prompt_block()
        _log_edape_block(adaptive_ctx, edape_block)
        return edape_block
    except Exception as exc:
        log.debug(f"  [EDAPE] load failed, continuing with legacy prompt path: {type(exc).__name__}: {exc}")
        return ""


def _log_edape_block(adaptive_ctx, edape_block: str) -> None:
    if not edape_block:
        return
    log.info(
        f"  [EDAPE] adaptive prompt context ready "
        f"(angles={len(adaptive_ctx.top_angles)} "
        f"golden={len(adaptive_ctx.golden_snippets)} "
        f"suppressed={len(adaptive_ctx.suppressed_angles) + len(adaptive_ctx.suppressed_hooks) + len(adaptive_ctx.suppressed_kicks)})"
    )


def _needs_voice_tracker(config: AppConfig) -> bool:
    return bool(getattr(config, "enable_adaptive_voice", False) or getattr(config, "enable_golden_reference_qa", False))


def _voice_tracker(config: AppConfig) -> object:
    if PerformanceTracker is None:
        log.debug("  performance data load skipped: PerformanceTracker unavailable")
        return None
    try:
        return PerformanceTracker(
            db_path=config.db_path,
            bearer_token=config.twitter_bearer_token,
            database_url=config.database_url,
            allow_sqlite_fallback=config.allow_sqlite_fallback,
        )
    except (RuntimeError, ValueError) as exc:
        log.debug(f"  performance tracker init failed: {type(exc).__name__}: {exc}")
        return None


async def _load_voice_assets(config: AppConfig, tracker) -> tuple[dict | None, list | None]:
    pattern_weights = None
    golden_refs = None
    try:
        if getattr(config, "enable_adaptive_voice", False):
            pattern_weights = await _load_pattern_weights(config, tracker)
        if getattr(config, "enable_golden_reference_qa", False):
            golden_refs = await _load_golden_references(config, tracker)
    except (RuntimeError, ValueError) as exc:
        log.debug(f"  performance data load failed: {type(exc).__name__}: {exc}")
    return pattern_weights, golden_refs


async def _load_pattern_weights(config: AppConfig, tracker) -> dict:
    pattern_weights = await tracker.get_optimal_pattern_weights(
        days=getattr(config, "pattern_weight_days", 30),
        min_samples=getattr(config, "pattern_weight_min_samples", 3),
    )
    angle_w = pattern_weights.get("angle_weights", {})
    top_angle = max(angle_w, key=angle_w.get, default="-") if angle_w else "-"
    log.info(f"  [Adaptive Voice] pattern weights loaded (top angle: {top_angle})")
    return pattern_weights


async def _load_golden_references(config: AppConfig, tracker) -> list:
    golden_refs = await tracker.get_golden_references(limit=getattr(config, "golden_reference_limit", 3))
    log.info(f"  [Benchmark QA] golden references loaded: {len(golden_refs)}")
    return golden_refs


async def _try_cache_hit(trend, config: AppConfig, conn) -> TweetBatch | None:
    """캐시 히트 시 배치 반환, 미스 시 None."""
    effective_keyword = getattr(trend, "corrected_keyword", "") or trend.keyword
    if effective_keyword != trend.keyword:
        log.info(f"  [키워드 교정 적용] '{trend.keyword}' → '{effective_keyword}'")
        trend.keyword = effective_keyword

    fp = compute_fingerprint(trend.keyword, trend.volume_last_24h, bucket=config.cache_volume_bucket)
    peak_status = getattr(trend, "peak_status", "")
    cache_ttl = config.get_cache_ttl(peak_status)
    cached = await get_cached_content(conn, fp, max_age_hours=cache_ttl)
    if cached:
        log.info(f"  [콘텐츠 캐시] '{trend.keyword}' 재사용 ({len(cached)}개 항목, TTL={cache_ttl}h)")
        return _batch_from_cache(trend.keyword, cached)
    return None


async def _load_recent_tweets(trend, config: AppConfig, conn) -> list[str]:
    """콘텐츠 다양성을 위한 이전 생성 트윗 조회."""
    if not getattr(config, "enable_content_diversity", True):
        return []
    try:
        hours = getattr(config, "content_diversity_hours", 24)
        return await get_recent_tweet_contents(conn, trend.keyword, hours=hours)
    except (ImportError, sqlite3.Error, ValueError) as _e:
        log.debug(f"  이전 트윗 조회 실패 (무시): {type(_e).__name__}: {_e}")
        return []


async def _load_approved_post_bank(config: AppConfig, conn) -> list[dict]:
    """Load a few approved/published drafts as voice anchors for new prompts."""
    if not getattr(config, "enable_approved_post_bank", True):
        return []
    try:
        limit = int(getattr(config, "approved_post_bank_limit", 5))
        platforms = tuple(getattr(config, "approved_post_bank_platforms", ["x"]) or ["x"])
        return await get_approved_post_bank(conn, limit=limit, platforms=platforms)
    except (ImportError, sqlite3.Error, TypeError, ValueError) as _e:
        log.debug(f"  [Approved Post Bank] 濡쒕뱶 ?ㅽ뙣 (臾댁떆): {type(_e).__name__}: {_e}")
        return []


def _build_empty_qa(trend, *, reason: str = "qa_skipped") -> dict:
    return {
        "failed_groups": [],
        "warnings": [],
        "reason": reason,
        "group_results": {},
        "total_score": float(getattr(trend, "viral_potential", 0) or 0),
    }


def _format_qa_failure_summary(group_name: str, result: dict) -> str:
    issues = list(result.get("issues", []) or [])
    extras: list[str] = [f"{result.get('total', '?')}/{result.get('threshold', '?')}"]
    if result.get("worst"):
        extras.append(f"worst={result['worst']}")
    if issues:
        extras.append(issues[0])
    return f"{group_name} ({', '.join(extras)})"


def _format_fact_check_failure_summary(group_name: str, fc_result) -> str:
    details: list[str] = []
    accuracy_score = getattr(fc_result, "accuracy_score", None)
    if accuracy_score is not None:
        with contextlib.suppress(TypeError, ValueError):
            details.append(f"accuracy={float(accuracy_score):.0%}")
    hallucinated_claims = int(getattr(fc_result, "hallucinated_claims", 0) or 0)
    if hallucinated_claims > 0:
        details.append(f"hallucinated={hallucinated_claims}")
    issues = list(getattr(fc_result, "issues", []) or [])
    if issues:
        details.append(issues[0])
    return f"{group_name} ({', '.join(details)})" if details else group_name


# ══════════════════════════════════════════════════════
#  QA Pipeline
# ══════════════════════════════════════════════════════


async def _run_qa_pipeline(
    primary: TweetBatch,
    trend,
    config: AppConfig,
    effective_config: AppConfig,
    client,
    is_cached: bool,
    recent_tweets: list[str],
    approved_post_bank: list[dict],
) -> tuple[TweetBatch, dict]:
    """Run content QA and regenerate failed groups once."""
    if _should_skip_qa(trend, is_cached, config):
        log.debug(f"  [QA skip] '{trend.keyword}' (cached={is_cached}, score={trend.viral_potential})")
        return primary, _build_empty_qa(trend)

    qa = await audit_generated_content(primary, trend, config, client)
    _record_first_pass_qa(primary, qa)
    failed_groups = qa.get("failed_groups", []) if qa else []
    if not failed_groups:
        return primary, qa

    primary = await _regenerate_failed_qa_groups(
        primary,
        trend,
        effective_config,
        client,
        failed_groups,
        qa,
        recent_tweets,
        approved_post_bank,
    )
    qa_after = await audit_generated_content(primary, trend, config, client)
    _log_remaining_qa_failures(trend, qa_after)
    return primary, qa_after or qa


def _record_first_pass_qa(primary: TweetBatch, qa: dict) -> None:
    if not hasattr(primary, "metadata") or primary.metadata is None:
        primary.metadata = {}
    primary.metadata["qa_report_first_pass"] = qa


async def _regenerate_failed_qa_groups(
    primary: TweetBatch,
    trend,
    effective_config: AppConfig,
    client,
    failed_groups: list,
    qa: dict,
    recent_tweets: list[str],
    approved_post_bank: list[dict],
) -> TweetBatch:
    details = qa.get("group_results", {})
    failed_summary = _qa_failure_summary(failed_groups, details)
    qa_feedback = build_regeneration_feedback(qa_summary=qa)
    log.warning(f"  [QA failed] '{trend.keyword}' -> {failed_summary} (reason: {qa.get('reason', '-')}); regenerating failed groups")
    return await regenerate_content_groups(
        primary,
        trend,
        effective_config,
        client,
        failed_groups,
        recent_tweets=recent_tweets,
        approved_post_bank=approved_post_bank,
        qa_feedback=qa_feedback,
    )


def _qa_failure_summary(failed_groups: list, details: dict) -> str:
    return ", ".join(_format_qa_failure_summary(group, details.get(group, {})) for group in failed_groups)


def _log_remaining_qa_failures(trend, qa_after: dict | None) -> None:
    if not qa_after or not qa_after.get("failed_groups"):
        return
    failed_summary = _qa_failure_summary(qa_after["failed_groups"], qa_after.get("group_results", {}))
    log.warning(f"  [QA retry failed] '{trend.keyword}' {failed_summary} (reason: {qa_after.get('reason', '-')})")


def _run_cross_source_check(trend) -> None:
    """교차 출처 일관성 검증."""
    if check_cross_source_consistency is None:
        return
    try:
        csc = check_cross_source_consistency(trend)
        trend.cross_source_agreement = csc.get("agreement_score", 0.5)
        trend.cross_source_consistent = csc.get("consistent", True)
        if not csc.get("consistent", True):
            conflicts_str = "; ".join(csc.get("conflicts", [])[:3])
            log.warning(
                f"  [CrossSource 충돌] '{trend.keyword}' agreement={trend.cross_source_agreement:.2f} 충돌: {conflicts_str}"
            )
    except (RuntimeError, ValueError) as _csc_err:
        log.debug(f"  [CrossSource] 실행 실패 (무시): {type(_csc_err).__name__}: {_csc_err}")


def _fact_check_results(primary: TweetBatch, trend, effective_config: AppConfig) -> dict:
    return verify_fact_batch(
        primary,
        trend,
        strict_mode=getattr(effective_config, "fact_check_strict_mode", False),
        min_accuracy=getattr(effective_config, "fact_check_min_accuracy", 0.6),
    )


def _store_fact_check_report(primary: TweetBatch, fc_results: dict) -> None:
    if not hasattr(primary, "metadata") or primary.metadata is None:
        primary.metadata = {}
    primary.metadata["fact_check_report"] = {
        k: {
            "passed": v.passed,
            "hallucinated_claims": v.hallucinated_claims,
            "accuracy_score": v.accuracy_score,
            "issues": v.issues,
        }
        for k, v in fc_results.items()
    }


def _apply_fact_check_results(trend, fc_results: dict) -> bool:
    any_failed = False
    for group_name, fc_result in fc_results.items():
        if not fc_result.passed:
            any_failed = True
            log.warning(
                f"  [FactCheck 실패] '{trend.keyword}' "
                f"{_format_fact_check_failure_summary(group_name, fc_result)}: {fc_result.summary}"
            )
        trend.fact_check_score = min(trend.fact_check_score, fc_result.accuracy_score)
        trend.source_credibility = max(trend.source_credibility, fc_result.source_credibility)
        if fc_result.hallucinated_claims > 0:
            trend.hallucination_flags.extend(f"[{group_name}] {issue}" for issue in fc_result.issues if "환각" in issue)
    return any_failed


def _hallucinated_fact_check_groups(fc_results: dict) -> list:
    return [group_name for group_name, result in fc_results.items() if result.hallucinated_claims > 0]


async def _regenerate_hallucinated_groups(
    primary: TweetBatch,
    trend,
    effective_config: AppConfig,
    client,
    recent_tweets: list[str],
    approved_post_bank: list[dict],
    fc_results: dict,
) -> TweetBatch:
    halluc_groups = _hallucinated_fact_check_groups(fc_results)
    if not halluc_groups:
        return primary
    fact_check_feedback = build_regeneration_feedback(fact_check_results=fc_results)
    log.warning(f"  [FactCheck regenerate] '{trend.keyword}' hallucination groups: {', '.join(halluc_groups)}")
    return await regenerate_content_groups(
        primary,
        trend,
        effective_config,
        client,
        halluc_groups,
        recent_tweets=recent_tweets,
        approved_post_bank=approved_post_bank,
        fact_check_feedback=fact_check_feedback,
    )


async def _run_fact_check(
    primary: TweetBatch,
    trend,
    effective_config: AppConfig,
    client,
    recent_tweets: list[str],
    approved_post_bank: list[dict],
) -> TweetBatch:
    """팩트 체크 + 환각 감지 시 재생성."""
    if not getattr(effective_config, "enable_fact_checking", True):
        return primary
    if verify_fact_batch is None:
        return primary
    try:
        fc_results = _fact_check_results(primary, trend, effective_config)
        _store_fact_check_report(primary, fc_results)
        any_failed = _apply_fact_check_results(trend, fc_results)
        if any_failed and getattr(effective_config, "hallucination_zero_tolerance", True):
            primary = await _regenerate_hallucinated_groups(
                primary,
                trend,
                effective_config,
                client,
                recent_tweets,
                approved_post_bank,
                fc_results,
            )
    except (RuntimeError, ConnectionError, TimeoutError, ValueError) as _fc_err:
        log.debug(f"  [FactCheck] 실행 실패 (무시): {type(_fc_err).__name__}: {_fc_err}")
    return primary


def _attach_generation_metadata(primary: TweetBatch, trend, final_qa: dict) -> None:
    """QA 리포트 + 프롬프트/모델 메타데이터를 배치에 부착."""
    if not hasattr(primary, "metadata") or primary.metadata is None:
        primary.metadata = {}
    primary.metadata["qa_report"] = final_qa or _build_empty_qa(trend, reason="qa_not_available")
    primary.metadata.setdefault("prompt_version", f"getdaytrends-v2.{VERSION}")
    primary.metadata.setdefault("generator_provider", "shared.llm")
    primary.metadata.setdefault("generator_model", "shared.llm.default")
    primary.metadata.setdefault("degraded_mode", False)


# ══════════════════════════════════════════════════════
#  Diversity Rewrite Pass
# ══════════════════════════════════════════════════════


def _detect_duplicate_tweet_indices(vectors: list, threshold: float) -> tuple[set[int], list[str]]:
    dupe_indices: set[int] = set()
    dupes_log: list[str] = []
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            sim = _cosine_similarity(vectors[i], vectors[j])
            if sim > threshold:
                dupes_log.append(f"tweet {i + 1} vs {j + 1} (similarity={sim:.2f})")
                dupe_indices.add(j)
    return dupe_indices, dupes_log


def _record_diversity_warning(batch: TweetBatch, trend, threshold: float, dupes_log: list[str]) -> None:
    log.warning(f"[Diversity QA] '{trend.keyword}' duplicate threshold {threshold} exceeded: " + ", ".join(dupes_log))
    if not hasattr(batch, "metadata") or batch.metadata is None:
        batch.metadata = {}
    qa_report = batch.metadata.setdefault("qa_report", {})
    warnings = qa_report.setdefault("warnings", [])
    warnings.append(f"diversity rewrite: {trend.keyword} ({len(dupes_log)} pairs)")


def _rewrite_context_for_index(batch: TweetBatch, idx: int, dupe_indices: set[int]) -> tuple[str, str]:
    original_tweet = batch.tweets[idx].content
    other_tweets = [batch.tweets[k].content for k in range(len(batch.tweets)) if k != idx and k not in dupe_indices]
    others_text = "\n".join(f"- {other}" for other in other_tweets)
    return original_tweet, others_text


def _diversity_rewrite_prompt(original_tweet: str, others_text: str, trend, lang: str) -> str:
    return (
        "The following tweet overlaps too much with the other drafts in angle or wording.\n"
        "Rewrite it with a clearly different hook, emotion, rhythm, and framing while preserving the factual topic.\n\n"
        f"[Keyword]: {trend.keyword}\n"
        f"[Other drafts]:\n{others_text}\n\n"
        f"[Original]:\n{original_tweet}\n\n"
        f"Write only the rewritten tweet in {lang}. Maximum 280 characters."
    )


async def _rewrite_duplicate_tweet(batch: TweetBatch, trend, config: AppConfig, client, idx: int, dupe_indices: set[int]) -> None:
    from shared.llm import TaskTier

    lang = config.target_languages[0] if getattr(config, "target_languages", None) else "ko"
    original_tweet, others_text = _rewrite_context_for_index(batch, idx, dupe_indices)
    prompt = _diversity_rewrite_prompt(original_tweet, others_text, trend, lang)
    try:
        resp = await client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            system="Rewrite social drafts to improve diversity without changing the factual topic.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        rewritten = resp.text.strip().strip("\"'")
        if rewritten and len(rewritten) > 10:
            log.info(f"  [Diversity rewrite] '{trend.keyword}' tweet {idx + 1} complete")
            batch.tweets[idx].content = rewritten
    except Exception as exc:
        log.warning(f"  [Diversity rewrite failed] {type(exc).__name__}: {exc}")


async def _rewrite_duplicate_tweets(batch: TweetBatch, trend, config: AppConfig, client, dupe_indices: set[int]) -> None:
    if not dupe_indices:
        return
    log.info(f"  [Diversity rewrite] rewriting {len(dupe_indices)} duplicate tweets")
    await asyncio.gather(*[_rewrite_duplicate_tweet(batch, trend, config, client, idx, dupe_indices) for idx in dupe_indices])


async def _run_diversity_rewrite_pass(batch: TweetBatch, trend, config: AppConfig, client) -> None:
    """Detect highly similar generated tweets and rewrite later duplicates."""
    if len(batch.tweets) < 2 or _embed_texts is None or _cosine_similarity is None:
        return
    try:
        threshold = getattr(config, "diversity_sim_threshold", 0.85)
        vectors = _embed_texts([tweet.content for tweet in batch.tweets], task_type="SEMANTIC_SIMILARITY")
        if not vectors:
            return
        dupe_indices, dupes_log = _detect_duplicate_tweet_indices(vectors, threshold)
        if not dupes_log:
            return
        _record_diversity_warning(batch, trend, threshold, dupes_log)
        await _rewrite_duplicate_tweets(batch, trend, config, client, dupe_indices)
    except (RuntimeError, ConnectionError, ValueError) as exc:
        log.debug(f"[Diversity QA error] {type(exc).__name__}: {exc}")

#  Main Step 3: Generate
# ══════════════════════════════════════════════════════


async def _step_generate(quality_trends, config: AppConfig, conn) -> list:
    """Step 3: 트윗/쓰레드 전체 병렬 생성 (캐시 우선 + EDAPE 적응형 프롬프트 + TAP 선점)."""
    if not quality_trends:
        return []
    print(f"\n[3/4] 트윗 병렬 생성 중... ({len(quality_trends)}개 동시)")
    client = get_client()
    golden_refs, pattern_weights, edape_block = await _load_adaptive_voice(config)

    # ── TAP: 교차국가 트렌드 차익거래 감지 ──
    if getattr(config, "enable_tap", True) and len(getattr(config, "countries", [])) > 1:
        try:
            from tap import detect_arbitrage_opportunities
            from tap.analyzer import ArbitrageAnalyzer

            tap_opps = await detect_arbitrage_opportunities(conn, config=config)
            if tap_opps:
                analyzer = ArbitrageAnalyzer(tap_opps)
                analyzer.log_summary()
                tap_block = analyzer.to_prompt_block(target_country=config.country)
                if tap_block:
                    edape_block = (edape_block or "") + "\n" + tap_block
        except Exception as _tap_err:
            log.debug(f"  [TAP] 감지 실패 (무시): {type(_tap_err).__name__}: {_tap_err}")

    gen_mode = config.get_generation_mode()
    if gen_mode == "lite":
        log.info("  [생성 모드] lite (비피크 시간) — 장문 생성 생략")

    db_lock = asyncio.Lock()

    async def _get_or_generate(trend) -> object:
        """콘텐츠 캐시 히트 시 LLM 건너뜀."""
        async with db_lock:
            cached_batch = await _try_cache_hit(trend, config, conn)
            if cached_batch is not None:
                return cached_batch
            recent_tweets = await _load_recent_tweets(trend, config, conn)
            approved_post_bank = await _load_approved_post_bank(config, conn)

        effective_config = config
        if gen_mode == "lite" and config.enable_long_form:
            effective_config = dataclasses.replace(config, enable_long_form=False)

        primary = await generate_for_trend_async(
            trend,
            effective_config,
            client,
            recent_tweets,
            approved_post_bank,
            golden_refs,
            pattern_weights,
            edape_block=edape_block,
        )
        if primary is None:
            return primary

        primary, final_qa = await _run_qa_pipeline(
            primary,
            trend,
            config,
            effective_config,
            client,
            is_cached=False,
            recent_tweets=recent_tweets,
            approved_post_bank=approved_post_bank,
        )
        _attach_generation_metadata(primary, trend, final_qa)

        if trend.context:
            _run_cross_source_check(trend)

        primary = await _run_fact_check(
            primary,
            trend,
            effective_config,
            client,
            recent_tweets,
            approved_post_bank,
        )
        await _run_diversity_rewrite_pass(primary, trend, config, client)

        return primary

    return await asyncio.gather(*[_get_or_generate(t) for t in quality_trends], return_exceptions=True)
