"""
getdaytrends — Pipeline Step Functions
생성(Step 3) + 저장(Step 4) + 적응형 스케줄링.
core/pipeline.py에서 분리됨.
"""

import asyncio
import contextlib
import dataclasses
import re
import sqlite3
from datetime import datetime

import schedule
from loguru import logger as log
from shared.llm import get_client

try:
    from ..config import AppConfig, VERSION
    from ..db import (
        attach_draft_to_notion_page,
        compute_fingerprint,
        db_transaction,
        get_best_posting_hours,
        get_cached_content,
        get_recent_tweet_contents,
        promote_draft_to_ready,
        record_posting_time_stat,
        save_draft_bundle,
        save_qa_report,
        save_trend,
        save_tweets_batch,
        save_validated_trend,
    )
    from ..generator import generate_for_trend_async, regenerate_content_groups
    from ..models import GeneratedTweet, RunResult, TweetBatch
    from ..storage import save_to_content_hub, save_to_google_sheets, save_to_notion
    from ..workflow_v2 import build_draft_bundles, build_qa_report, validate_trend_candidate
except ImportError:
    from config import AppConfig, VERSION
    from db import (
        attach_draft_to_notion_page,
        compute_fingerprint,
        db_transaction,
        get_best_posting_hours,
        get_cached_content,
        get_recent_tweet_contents,
        promote_draft_to_ready,
        record_posting_time_stat,
        save_draft_bundle,
        save_qa_report,
        save_trend,
        save_tweets_batch,
        save_validated_trend,
    )
    from generator import generate_for_trend_async, regenerate_content_groups
    from models import GeneratedTweet, RunResult, TweetBatch
    from storage import save_to_content_hub, save_to_google_sheets, save_to_notion
    from workflow_v2 import build_draft_bundles, build_qa_report, validate_trend_candidate



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


async def _step_generate(quality_trends, config: AppConfig, conn) -> list:
    """Step 3: 트윗/쓰레드 전체 병렬 생성 (캐시 우선)."""
    print(f"\n[3/4] 트윗 병렬 생성 중... ({len(quality_trends)}개 동시)")
    client = get_client()

    # Adaptive Voice 패턴 가중치 로드
    golden_refs = None
    pattern_weights = None
    if getattr(config, "enable_adaptive_voice", False) or getattr(config, "enable_golden_reference_qa", False):
        try:
            try:
                from ..performance_tracker import PerformanceTracker
            except ImportError:
                from performance_tracker import PerformanceTracker

            tracker = PerformanceTracker(db_path=config.db_path, bearer_token=config.twitter_bearer_token)
            if getattr(config, "enable_adaptive_voice", False):
                pattern_weights = tracker.get_optimal_pattern_weights(
                    days=getattr(config, "pattern_weight_days", 30),
                    min_samples=getattr(config, "pattern_weight_min_samples", 3),
                )
                angle_w = pattern_weights.get("angle_weights", {})
                top_angle = max(angle_w, key=angle_w.get, default="-") if angle_w else "-"
                log.info(f"  [Adaptive Voice] 패턴 가중치 로드 완료 (최우선 앵글: {top_angle})")
            if getattr(config, "enable_golden_reference_qa", False):
                golden_refs = tracker.get_golden_references(limit=getattr(config, "golden_reference_limit", 3))
                log.info(f"  [Benchmark QA] 골든 레퍼런스 {len(golden_refs)}개 로드")
        except (ImportError, RuntimeError, ValueError) as _e:
            log.debug(f"  성과 데이터 로드 실패 (무시): {type(_e).__name__}: {_e}")

    # 시간대별 생성 모드
    gen_mode = config.get_generation_mode()
    if gen_mode == "lite":
        log.info("  [생성 모드] lite (비피크 시간) — 장문 생성 생략")

    async def _get_or_generate(trend):
        """콘텐츠 캐시 히트 시 LLM 건너뜀. 가속도 기반 TTL 차등화."""
        fp = compute_fingerprint(trend.keyword, trend.volume_last_24h, bucket=config.cache_volume_bucket)

        # 키워드 교정 적용
        effective_keyword = getattr(trend, "corrected_keyword", "") or trend.keyword
        if effective_keyword != trend.keyword:
            log.info(f"  [키워드 교정 적용] '{trend.keyword}' → '{effective_keyword}'")
            trend.keyword = effective_keyword

        # 동적 캐시 TTL
        peak_status = getattr(trend, "peak_status", "")
        cache_ttl = config.get_cache_ttl(peak_status)
        cached = await get_cached_content(conn, fp, max_age_hours=cache_ttl)
        is_cached = bool(cached)

        if is_cached:
            log.info(f"  [콘텐츠 캐시] '{trend.keyword}' 재사용 ({len(cached)}개 항목, TTL={cache_ttl}h)")
            return _batch_from_cache(trend.keyword, cached)

        # 콘텐츠 다양성: 이전 생성 트윗 조회
        recent_tweets: list[str] = []
        if getattr(config, "enable_content_diversity", True):
            try:
                hours = getattr(config, "content_diversity_hours", 24)
                recent_tweets = await get_recent_tweet_contents(conn, trend.keyword, hours=hours)
            except (ImportError, sqlite3.Error, ValueError) as _e:
                log.debug(f"  이전 트윗 조회 실패 (무시): {type(_e).__name__}: {_e}")

        # 시간대별 생성 모드: lite면 장문 생성 생략
        effective_config = config
        if gen_mode == "lite" and config.enable_long_form:
            effective_config = dataclasses.replace(config, enable_long_form=False)

        # 기본 생성
        primary = await generate_for_trend_async(
            trend, effective_config, client, recent_tweets, golden_refs, pattern_weights
        )
        if primary is None:
            return primary

        # QA 조건부 스킵
        final_qa: dict | None = None
        if not _should_skip_qa(trend, is_cached, config):
            try:
                from ..generator import audit_generated_content
            except ImportError:
                from generator import audit_generated_content

            qa = await audit_generated_content(primary, trend, config, client)
            final_qa = qa
            failed_groups = qa.get("failed_groups", []) if qa else []
            if failed_groups:
                details = qa.get("group_results", {})
                failed_summary = ", ".join(
                    f"{group}={details.get(group, {}).get('total', '?')}/{details.get(group, {}).get('threshold', '?')}"
                    for group in failed_groups
                )
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
                )
                qa_after = await audit_generated_content(primary, trend, config, client)
                final_qa = qa_after or qa
                if qa_after and qa_after.get("failed_groups"):
                    log.warning(
                        f"  [QA 재검사 미달] '{trend.keyword}' {', '.join(qa_after['failed_groups'])} (사유: {qa_after.get('reason', '-')})"
                    )
        else:
            log.debug(f"  [QA 스킵] '{trend.keyword}' (cached={is_cached}, score={trend.viral_potential})")

        # 교차 출처 일관성 검증
        if not is_cached and trend.context:
            try:
                try:
                    from ..fact_checker import check_cross_source_consistency as _csc
                except ImportError:
                    from fact_checker import check_cross_source_consistency as _csc

                csc = _csc(trend)
                trend.cross_source_agreement = csc.get("agreement_score", 0.5)
                trend.cross_source_consistent = csc.get("consistent", True)
                if not csc.get("consistent", True):
                    conflicts_str = "; ".join(csc.get("conflicts", [])[:3])
                    log.warning(
                        f"  [CrossSource 충돌] '{trend.keyword}' agreement={trend.cross_source_agreement:.2f} 충돌: {conflicts_str}"
                    )
            except (ImportError, RuntimeError, ValueError) as _csc_err:
                log.debug(f"  [CrossSource] 실행 실패 (무시): {type(_csc_err).__name__}: {_csc_err}")

        # 팩트 체크
        if getattr(effective_config, "enable_fact_checking", True) and not is_cached:
            try:
                try:
                    from ..fact_checker import verify_batch as _fc_verify
                except ImportError:
                    from fact_checker import verify_batch as _fc_verify

                fc_results = _fc_verify(
                    primary,
                    trend,
                    strict_mode=getattr(effective_config, "fact_check_strict_mode", False),
                    min_accuracy=getattr(effective_config, "fact_check_min_accuracy", 0.6),
                )
                any_failed = False
                fc_issues: list[str] = []
                for group_name, fc_result in fc_results.items():
                    if not fc_result.passed:
                        any_failed = True
                        fc_issues.extend(fc_result.issues[:2])
                        log.warning(f"  [FactCheck 실패] '{trend.keyword}' {group_name}: {fc_result.summary}")
                    trend.fact_check_score = min(trend.fact_check_score, fc_result.accuracy_score)
                    trend.source_credibility = max(trend.source_credibility, fc_result.source_credibility)
                    if fc_result.hallucinated_claims > 0:
                        trend.hallucination_flags.extend(
                            f"[{group_name}] {issue}" for issue in fc_result.issues if "환각" in issue
                        )

                # 환각 감지 시 재생성
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
                        )
            except (ImportError, RuntimeError, ConnectionError, TimeoutError, ValueError) as _fc_err:
                log.debug(f"  [FactCheck] 실행 실패 (무시): {type(_fc_err).__name__}: {_fc_err}")

        return primary

    return await asyncio.gather(*[_get_or_generate(t) for t in quality_trends], return_exceptions=True)


async def _run_diversity_qa(batch: TweetBatch, trend, run: RunResult) -> None:
    """생성물 다양성 QA — 코사인 유사도 0.88 초과 쌍 경고."""
    if len(batch.tweets) < 2:
        return
    try:
        from shared.embeddings import cosine_similarity as _cos
        from shared.embeddings import embed_texts as _embed

        vectors = _embed([t.content for t in batch.tweets], task_type="SEMANTIC_SIMILARITY")
        if not vectors:
            return
        dupes = [
            f"트윗{i + 1}↔트윗{j + 1} (유사도={_cos(vectors[i], vectors[j]):.2f})"
            for i in range(len(vectors))
            for j in range(i + 1, len(vectors))
            if _cos(vectors[i], vectors[j]) > 0.88
        ]
        if dupes:
            log.warning(f"[다양성 QA] '{trend.keyword}' 유사도 높음: " + ", ".join(dupes))
            run.errors.append(f"다양성 경고: {trend.keyword} ({len(dupes)}쌍)")
    except (ImportError, RuntimeError, ConnectionError, ValueError):
        pass


async def _save_single_trend_db(
    batch: TweetBatch,
    trend,
    config: AppConfig,
    conn,
    run: RunResult,
    run_row_id: int,
) -> bool:
    """단일 트렌드를 SQLite 원자적 트랜잭션으로 저장. 성공 여부 반환."""
    try:
        async with db_transaction(conn):
            trend_id = await save_trend(conn, trend, run_row_id, bucket=config.cache_volume_bucket)
            try:
                from shared.business_metrics import biz

                biz.trend_scored()
            except ImportError:
                pass
            saved_to: list[str] = []
            for content_list, _is_thread in [
                (batch.tweets, False),
                (batch.long_posts, False),
                (batch.threads_posts, False),
                (getattr(batch, "blog_posts", []), False),
            ]:
                if content_list:
                    await save_tweets_batch(conn, content_list, trend_id, run_row_id, saved_to=saved_to)
                    run.tweets_saved += len(content_list)
            if getattr(batch, "thread", None) and batch.thread.tweets:
                await save_tweets_batch(
                    conn,
                    batch.thread.tweets,
                    trend_id,
                    run_row_id,
                    is_thread=True,
                    saved_to=saved_to,
                )
                run.tweets_saved += len(batch.thread.tweets)
    except (ImportError, sqlite3.Error, ValueError) as e:
        log.error(f"SQLite 저장 실패 ({trend.keyword}): {type(e).__name__}: {e}")
        run.errors.append(f"DB 저장 실패: {trend.keyword}")
        return False
    return True


async def _save_external(
    ext_pairs: list[tuple],
    config: AppConfig,
    run: RunResult,
) -> None:
    """Notion/Sheets + Content Hub 병렬 외부 저장."""
    notion_sem = asyncio.Semaphore(config.notion_sem_limit)

    async def _do_ext_save(b, t) -> dict[str, bool]:
        results: dict[str, bool] = {}
        if config.storage_type in ("notion", "both"):
            async with notion_sem:
                results["notion"] = await asyncio.to_thread(save_to_notion, b, t, config)
        if config.storage_type in ("google_sheets", "both"):
            results["google_sheets"] = await asyncio.to_thread(save_to_google_sheets, b, t, config)
        return results

    ext_results = await asyncio.gather(*[_do_ext_save(b, t) for b, t in ext_pairs], return_exceptions=True)
    ext_failed: list[str] = []
    for i, result in enumerate(ext_results):
        keyword = ext_pairs[i][1].keyword
        if isinstance(result, Exception):
            log.error(f"External save raised ({keyword}): {result}")
            run.errors.append(f"external save raised: {keyword}")
            ext_failed.append(keyword)
            continue
        failed_targets = sorted(name for name, ok in result.items() if not ok)
        if failed_targets:
            failed_label = ", ".join(failed_targets)
            log.error(f"External save failed ({keyword}): {failed_label}")
            run.errors.append(f"external save failed ({failed_label}): {keyword}")
            ext_failed.append(f"{keyword}[{failed_label}]")
    if ext_failed:
        print(f"\n  External save failed for {len(ext_failed)} item(s): {', '.join(ext_failed)}")

    if not _content_hub_enabled(config):
        return
    platforms = getattr(config, "target_platforms", ["x"])
    for b, t in ext_pairs:
        for plat in platforms:
            has_content = (
                (plat == "x" and b.tweets)
                or (plat == "threads" and b.threads_posts)
                or (plat == "naver_blog" and getattr(b, "blog_posts", []))
            )
            if not has_content:
                continue
            try:
                async with notion_sem:
                    hub_ok = await asyncio.to_thread(save_to_content_hub, b, t, config, plat)
            except (ImportError, RuntimeError, ConnectionError, TimeoutError, ValueError) as hub_err:
                log.warning(f"Content Hub save raised [{plat}] ({t.keyword}): {type(hub_err).__name__}: {hub_err}")
                run.errors.append(f"content hub raised ({plat}): {t.keyword}")
                continue
            if not hub_ok:
                log.warning(f"Content Hub save failed [{plat}] ({t.keyword})")
                run.errors.append(f"content hub failed ({plat}): {t.keyword}")


async def _preview_and_record_stats(batch, category: str, conn) -> None:
    """배치 콘텐츠 미리보기 출력 + 게시 시간 통계 기록."""
    for t in batch.tweets:
        preview = t.content[:50] + "..." if len(t.content) > 50 else t.content
        print(f"    [{t.tweet_type}] {preview}")
        if t.best_posting_time and t.expected_engagement:
            with contextlib.suppress(ImportError, sqlite3.Error, ValueError):
                await record_posting_time_stat(conn, category, datetime.now().hour, t.expected_engagement)
    if batch.long_posts:
        print(f"    [Premium+ 장문] {len(batch.long_posts)}편")
    if batch.threads_posts:
        print(f"    [Threads] {len(batch.threads_posts)}편")
    if getattr(batch, "blog_posts", []):
        print(f"    [블로그] {len(batch.blog_posts)}편 ({sum(p.char_count for p in batch.blog_posts):,}자)")
    if batch.thread:
        print(f"    [쓰레드] {len(batch.thread.tweets)}개 트윗")


def _attach_best_hours(batch, category: str, best_hours: list[int]) -> None:
    """배치 메타데이터에 추천 게시 시간 기록 + 출력."""
    if not best_hours:
        return
    if not hasattr(batch, "metadata") or batch.metadata is None:
        batch.metadata = {}
    batch.metadata["best_posting_hours"] = best_hours
    print(f"    추천 게시 시간 ({category}): {', '.join(f'{h}시' for h in best_hours)}")


async def _step_save(
    quality_trends: list,
    batch_results: list,
    config: AppConfig,
    conn,
    run: RunResult,
    run_row_id: int,
) -> int:
    """Step 4: SQLite 원자적 트랜잭션 저장 + 외부 저장 병렬 처리."""
    print("\n[4/4] 저장 중...")
    success_count = 0
    ext_pairs: list[tuple] = []
    failed_saves: list[str] = []

    for trend, batch in zip(quality_trends, batch_results, strict=False):
        if config.enable_sentiment_filter and getattr(trend, "safety_flag", False):
            log.warning(f"유해 트렌드 스킵: '{trend.keyword}' (sentiment={trend.sentiment})")
            run.errors.append(f"safety_flag 스킵: {trend.keyword}")
            continue

        print(f"\n  '{trend.keyword}' (바이럴: {trend.viral_potential}점)")

        category = getattr(trend, "category", "기타") or "기타"
        best_hours: list[int] = []
        with contextlib.suppress(ImportError, sqlite3.Error, ValueError):
            best_hours = await get_best_posting_hours(conn, category, top_n=3)

        if isinstance(batch, Exception):
            log.error(f"생성 예외 ({trend.keyword}): {type(batch).__name__}: {batch}")
            run.errors.append(f"생성 예외: {trend.keyword}")
            continue
        if not batch:
            run.errors.append(f"생성 실패: {trend.keyword}")
            continue

        run.tweets_generated += (
            len(batch.tweets) + len(batch.long_posts) + len(batch.threads_posts) + len(getattr(batch, "blog_posts", []))
        )
        await _run_diversity_qa(batch, trend, run)
        await _preview_and_record_stats(batch, category, conn)
        _attach_best_hours(batch, category, best_hours)

        if not await _save_single_trend_db(batch, trend, config, conn, run, run_row_id):
            failed_saves.append(trend.keyword)
            continue

        success_count += 1
        if not config.dry_run:
            ext_pairs.append((batch, trend))

    if ext_pairs and not config.dry_run:
        await _save_external(ext_pairs, config, run)

    if failed_saves:
        print(f"\n  DB 저장 실패 {len(failed_saves)}건: {', '.join(failed_saves)}")

    return success_count


async def _adjust_schedule(scored_trends, config: AppConfig, schedule_callback=None):
    """적응형 스케줄링 — 평균 점수 기반 간격 조정."""
    if not (config.smart_schedule and not config.one_shot):
        if not config.one_shot:
            print(f"  다음 실행: {config.schedule_minutes}분 후")
        return

    callback = schedule_callback or (lambda: None)
    hot = [t for t in scored_trends if t.viral_potential >= 90 and _is_accelerating(t.trend_acceleration)]
    avg_score = sum(t.viral_potential for t in scored_trends) / len(scored_trends) if scored_trends else 0

    if hot:
        fast_interval = max(config.schedule_minutes // 4, 15)
        print(f"  핫 트렌드 {len(hot)}건 감지 → 다음 실행 {fast_interval}분 후")
        schedule.clear()
        schedule.every(fast_interval).minutes.do(callback)
    elif avg_score >= 75:
        faster = max(int(config.schedule_minutes * 0.85), 30)
        print(f"  평균 {avg_score:.0f}점 (고품질) → 다음 실행 {faster}분 후")
        schedule.clear()
        schedule.every(faster).minutes.do(callback)
    elif 0 < avg_score < 55:
        slower = min(int(config.schedule_minutes * 1.25), 180)
        print(f"  평균 {avg_score:.0f}점 (저품질) → 다음 실행 {slower}분 후")
        schedule.clear()
        schedule.every(slower).minutes.do(callback)
    else:
        schedule.clear()
        schedule.every(config.schedule_minutes).minutes.do(callback)
        print(f"  다음 실행: {config.schedule_minutes}분 후")


# ══════════════════════════════════════════════════════
