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
from datetime import datetime

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
        get_cached_content,
        get_recent_tweet_contents,
        record_posting_time_stat,
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
    """Adaptive Voice 패턴 가중치 + 골든 레퍼런스 + EDAPE 적응형 컨텍스트 로드."""
    golden_refs = None
    pattern_weights = None
    edape_block = ""

    if getattr(config, "enable_edape", True):
        try:
            from edape import build_adaptive_context_async

            adaptive_ctx = await build_adaptive_context_async(config)
            edape_block = adaptive_ctx.to_prompt_block()
            if edape_block:
                log.info(
                    f"  [EDAPE] 적응형 프롬프트 주입 준비 완료 "
                    f"(angles={len(adaptive_ctx.top_angles)} "
                    f"golden={len(adaptive_ctx.golden_snippets)} "
                    f"suppressed={len(adaptive_ctx.suppressed_angles)+len(adaptive_ctx.suppressed_hooks)+len(adaptive_ctx.suppressed_kicks)})"
                )
        except Exception as _edape_err:
            log.debug(f"  [EDAPE] 로드 실패 (무시, 기존 경로 사용): {type(_edape_err).__name__}: {_edape_err}")
    else:
        log.debug("  [EDAPE] 비활성화 상태 (config.enable_edape=False)")

    if not (getattr(config, "enable_adaptive_voice", False) or getattr(config, "enable_golden_reference_qa", False)):
        return golden_refs, pattern_weights, edape_block
    if PerformanceTracker is None:
        log.debug("  성과 데이터 로드 실패 (무시): PerformanceTracker 미설치")
        return golden_refs, pattern_weights, edape_block
    try:
        tracker = PerformanceTracker(db_path=config.db_path, bearer_token=config.twitter_bearer_token)
        if getattr(config, "enable_adaptive_voice", False):
            pattern_weights = await tracker.get_optimal_pattern_weights(
                days=getattr(config, "pattern_weight_days", 30),
                min_samples=getattr(config, "pattern_weight_min_samples", 3),
            )
            angle_w = pattern_weights.get("angle_weights", {})
            top_angle = max(angle_w, key=angle_w.get, default="-") if angle_w else "-"
            log.info(f"  [Adaptive Voice] 패턴 가중치 로드 완료 (최우선 앵글: {top_angle})")
        if getattr(config, "enable_golden_reference_qa", False):
            golden_refs = await tracker.get_golden_references(limit=getattr(config, "golden_reference_limit", 3))
            log.info(f"  [Benchmark QA] 골든 레퍼런스 {len(golden_refs)}개 로드")
    except (RuntimeError, ValueError) as _e:
        log.debug(f"  성과 데이터 로드 실패 (무시): {type(_e).__name__}: {_e}")
    return golden_refs, pattern_weights, edape_block


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
) -> tuple[TweetBatch, dict]:
    """QA 검사 + 미달 시 재생성."""
    if _should_skip_qa(trend, is_cached, config):
        log.debug(f"  [QA 스킵] '{trend.keyword}' (cached={is_cached}, score={trend.viral_potential})")
        return primary, _build_empty_qa(trend)

    qa = await audit_generated_content(primary, trend, config, client)
    final_qa = qa
    failed_groups = qa.get("failed_groups", []) if qa else []

    if not hasattr(primary, "metadata") or primary.metadata is None:
        primary.metadata = {}
    primary.metadata["qa_report_first_pass"] = qa

    if failed_groups:
        details = qa.get("group_results", {})
        failed_summary = ", ".join(
            _format_qa_failure_summary(group, details.get(group, {}))
            for group in failed_groups
        )
        qa_feedback = build_regeneration_feedback(qa_summary=qa)
        log.warning(
            f"  [QA 미달] '{trend.keyword}' → {failed_summary} (사유: {qa.get('reason', '-')}) → 실패 그룹만 재생성"
        )
        primary = await regenerate_content_groups(
            primary,
            trend,
            effective_config,
            client,
            failed_groups,
            recent_tweets=recent_tweets,
            qa_feedback=qa_feedback,
        )
        qa_after = await audit_generated_content(primary, trend, config, client)
        final_qa = qa_after or qa
        if qa_after and qa_after.get("failed_groups"):
            qa_after_details = qa_after.get("group_results", {})
            failed_after_summary = ", ".join(
                _format_qa_failure_summary(group, qa_after_details.get(group, {}))
                for group in qa_after["failed_groups"]
            )
            log.warning(
                f"  [QA 재검사 미달] '{trend.keyword}' {failed_after_summary} (사유: {qa_after.get('reason', '-')})"
            )

    return primary, final_qa


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


async def _run_fact_check(
    primary: TweetBatch,
    trend,
    effective_config: AppConfig,
    client,
    recent_tweets: list[str],
) -> TweetBatch:
    """팩트 체크 + 환각 감지 시 재생성."""
    if not getattr(effective_config, "enable_fact_checking", True):
        return primary
    if verify_fact_batch is None:
        return primary
    try:
        fc_results = verify_fact_batch(
            primary,
            trend,
            strict_mode=getattr(effective_config, "fact_check_strict_mode", False),
            min_accuracy=getattr(effective_config, "fact_check_min_accuracy", 0.6),
        )
        any_failed = False
        fact_check_feedback = build_regeneration_feedback(fact_check_results=fc_results)

        if not hasattr(primary, "metadata") or primary.metadata is None:
            primary.metadata = {}
        primary.metadata["fact_check_report"] = {
            k: {
                "passed": v.passed,
                "hallucinated_claims": v.hallucinated_claims,
                "accuracy_score": v.accuracy_score,
                "issues": v.issues
            } for k, v in fc_results.items()
        }

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
                trend.hallucination_flags.extend(
                    f"[{group_name}] {issue}" for issue in fc_result.issues if "환각" in issue
                )

        if any_failed and getattr(effective_config, "hallucination_zero_tolerance", True):
            halluc_groups = [gn for gn, r in fc_results.items() if r.hallucinated_claims > 0]
            if halluc_groups:
                log.warning(
                    f"  [FactCheck 재생성] '{trend.keyword}' 환각 감지 그룹: {', '.join(halluc_groups)}"
                )
                primary = await regenerate_content_groups(
                    primary,
                    trend,
                    effective_config,
                    client,
                    halluc_groups,
                    recent_tweets=recent_tweets,
                    fact_check_feedback=fact_check_feedback,
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


async def _run_diversity_rewrite_pass(batch: TweetBatch, trend, config: AppConfig, client) -> None:
    """생성물 다양성 판단 및 강제 재작성 (코사인 유사도 기반)."""
    if len(batch.tweets) < 2 or _embed_texts is None or _cosine_similarity is None:
        return
    try:
        threshold = getattr(config, "diversity_sim_threshold", 0.85)
        vectors = _embed_texts([t.content for t in batch.tweets], task_type="SEMANTIC_SIMILARITY")
        if not vectors:
            return

        dupe_indices = set()
        dupes_log = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                sim = _cosine_similarity(vectors[i], vectors[j])
                if sim > threshold:
                    dupes_log.append(f"트윗{i + 1}↔트윗{j + 1} (유사도={sim:.2f})")
                    dupe_indices.add(j)

        if dupes_log:
            log.warning(f"[다양성 QA] '{trend.keyword}' 유사도 임계치({threshold}) 초과 감지: " + ", ".join(dupes_log))

            if not hasattr(batch, 'metadata') or batch.metadata is None:
                batch.metadata = {}
            if 'qa_report' not in batch.metadata:
                batch.metadata['qa_report'] = {}
            if 'warnings' not in batch.metadata['qa_report']:
                batch.metadata['qa_report']['warnings'] = []
            batch.metadata['qa_report']['warnings'].append(f"다양성 재작성: {trend.keyword} ({len(dupes_log)}쌍)")

            from shared.llm import TaskTier
            lang = config.target_languages[0] if getattr(config, "target_languages", None) else "ko"

            async def _rewrite_tweet(idx: int):
                original_tweet = batch.tweets[idx].content
                other_tweets = [batch.tweets[k].content for k in range(len(batch.tweets)) if k != idx and k not in dupe_indices]
                others_text = "\n".join(f"- {o}" for o in other_tweets)

                prompt = (
                    f"다음 트윗은 다른 시안들과 겹치는 시각/문체가 너무 많습니다.\n"
                    f"아래의 '피해야 할 시안들'에서 사용된 구조(hook), 감정, 리듬을 피해서 완전히 180도 다른 분위기로 재작성해 주세요.\n\n"
                    f"[키워드]: {trend.keyword}\n"
                    f"[피해야 할 시안들]:\n{others_text}\n\n"
                    f"[원래 내용]:\n{original_tweet}\n\n"
                    f"반드시 {lang} 언어로 작성하고, 다른 설명 없이 재작성된 텍스트만 출력하세요. 최대 280자."
                )
                try:
                    resp = await client.acreate(
                        tier=TaskTier.LIGHTWEIGHT,
                        system="당신은 트윗 프레이밍을 다르게 비틀어 재작성하는 숙련된 소셜 에디터입니다.",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=300,
                    )
                    rewritten = resp.text.strip().strip('"\'')
                    if rewritten and len(rewritten) > 10:
                        log.info(f"  [다양성 재작성] '{trend.keyword}' 트윗{idx + 1} 완료")
                        batch.tweets[idx].content = rewritten
                except Exception as e:
                    log.warning(f"  [다양성 재작성 실패] {type(e).__name__}: {e}")

            if dupe_indices:
                log.info(f"  [다양성 실행] 중복도 높은 {len(dupe_indices)}개 트윗에 대해 강제 재작성 진행")
                await asyncio.gather(*[_rewrite_tweet(idx) for idx in dupe_indices])

    except (RuntimeError, ConnectionError, ValueError) as e:
        log.debug(f"[다양성 QA 오류] {type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════
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

    async def _get_or_generate(trend):
        """콘텐츠 캐시 히트 시 LLM 건너뜀."""
        async with db_lock:
            cached_batch = await _try_cache_hit(trend, config, conn)
            if cached_batch is not None:
                return cached_batch
            recent_tweets = await _load_recent_tweets(trend, config, conn)

        effective_config = config
        if gen_mode == "lite" and config.enable_long_form:
            effective_config = dataclasses.replace(config, enable_long_form=False)

        primary = await generate_for_trend_async(
            trend, effective_config, client, recent_tweets, golden_refs, pattern_weights,
            edape_block=edape_block,
        )
        if primary is None:
            return primary

        primary, final_qa = await _run_qa_pipeline(
            primary, trend, config, effective_config, client, is_cached=False, recent_tweets=recent_tweets,
        )
        _attach_generation_metadata(primary, trend, final_qa)

        if trend.context:
            _run_cross_source_check(trend)

        primary = await _run_fact_check(primary, trend, effective_config, client, recent_tweets)
        await _run_diversity_rewrite_pass(primary, trend, config, client)

        return primary

    return await asyncio.gather(*[_get_or_generate(t) for t in quality_trends], return_exceptions=True)
