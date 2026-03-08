"""
=======================================================
  X(Twitter) 트렌드 자동 트윗 생성기 v3.0
  - 멀티소스 트렌드 병렬 수집 + 클러스터링
  - Claude AI 바이럴 스코어링 (배치 + 캐시 + 재시도)
  - 5종 단문 + Premium+ 장문 + Threads + 강화 쓰레드
  - 감성 필터(safety_flag) + A/B 변형 + 멀티언어
  - Notion / Google Sheets / SQLite 원자적 트랜잭션 저장
  - 스마트 스케줄링 + 야간 슬립 + SIGTERM 우아한 종료
=======================================================
"""

import argparse
import asyncio
import io
import signal
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

# Windows stdout UTF-8 설정 (pytest 실행 중에는 건너뜀: capture 충돌 방지)
if sys.platform == "win32" and "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# shared.llm 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
import re

import schedule

from alerts import check_and_alert, check_watchlist, send_weekly_cost_report
from analyzer import analyze_trends, detect_trend_patterns
from config import AppConfig, VERSION
from db import (
    cleanup_old_records, close_pg_pool, compute_fingerprint,
    db_transaction, get_cached_content, get_connection, get_meta,
    get_recent_avg_viral_score, get_recent_tweet_contents,
    get_trend_history_batch, get_trend_stats, init_db,
    record_posting_time_stat, save_run, save_trend, save_tweets_batch,
    set_meta, update_run,
)
from generator import (
    generate_ab_variant_async,
    generate_for_trend_async,
    generate_for_trend_multilang_async,
)
from models import GeneratedTweet, RunResult, TweetBatch
from scraper import collect_trends
from shared.llm import get_client
from storage import save_to_google_sheets, save_to_notion
from utils import run_async

from loguru import logger as log

# ══════════════════════════════════════════════════════
#  우아한 종료 (SIGTERM / SIGINT)
# ══════════════════════════════════════════════════════

_SHUTDOWN_FLAG = threading.Event()


def _install_signal_handlers() -> None:
    """SIGTERM·SIGINT 수신 시 종료 플래그 설정."""
    def _handler(signum: int, _frame: object) -> None:
        log.warning(f"종료 신호 수신 (signal {signum}) — 현재 파이프라인 완료 후 종료합니다.")
        _SHUTDOWN_FLAG.set()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


# ══════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════

def _should_skip_qa(trend, is_cached: bool, config: AppConfig) -> bool:
    """[v9.0] QA Audit를 생략할 수 있는 조건.
    - 캐시 재사용 콘텐츠: 이미 검증된 내용
    - 고바이럴 트렌드: 품질 리스크 낮음
    - 저위험 카테고리: 날씨/음식/스포츠 등
    """
    if not getattr(config, "enable_quality_feedback", True):
        return True
    if is_cached and getattr(config, "qa_skip_cached", True):
        return True
    skip_score = getattr(config, "qa_skip_high_score", 85)
    if trend.viral_potential >= skip_score:
        return True
    skip_cats = set(getattr(config, "qa_skip_categories", []))
    category = getattr(trend, "category", "") or ""
    if category in skip_cats:
        return True
    return False


def _is_accelerating(trend_acceleration: str) -> bool:
    """
    trend_acceleration 문자열이 급상승 상태인지 판별.
    '+3%', '+30%', '급상승' 등을 처리.
    이전 버그: '+3' in '+30%' → True 오탐 ('+30'도 매칭됨).
    수정: 정규식으로 정확한 수치 파싱.
    """
    if "급상승" in trend_acceleration:
        return True
    m = re.search(r"\+(\d+(?:\.\d+)?)\s*%?", trend_acceleration)
    if m:
        try:
            return float(m.group(1)) >= 3.0
        except ValueError:
            pass
    return False


# ══════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="X 트렌드 자동 트윗 생성기 v4.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--country", default=None, help="국가 코드 (korea, us, japan 등)")
    parser.add_argument("--countries", default=None, help="쉼표 구분 다국가 (korea,us,japan) — 순차 실행")
    parser.add_argument("--limit", type=int, default=None, help="처리할 트렌드 수")
    parser.add_argument("--one-shot", action="store_true", help="1회 실행 후 종료")
    parser.add_argument("--dry-run", action="store_true", help="수집+분석만 (저장 안 함)")
    parser.add_argument("--verbose", action="store_true", help="상세 로그 출력")
    parser.add_argument("--no-alerts", action="store_true", help="알림 전송 안 함")
    parser.add_argument("--schedule-min", type=int, default=None, help="스케줄 간격(분) 오버라이드")
    parser.add_argument("--stats", action="store_true", help="히스토리 통계만 출력 후 종료")
    parser.add_argument("--serve", action="store_true", help="대시보드 웹 서버 실행 (포트 8080)")
    return parser.parse_args()


# ══════════════════════════════════════════════════════
#  Logging
# ══════════════════════════════════════════════════════

def setup_logging(verbose: bool = False) -> None:
    from loguru import logger

    logger.remove()
    level = "DEBUG" if verbose else "INFO"

    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    logger.add(
        "tweet_bot.log",
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )


# ══════════════════════════════════════════════════════
#  Banner
# ══════════════════════════════════════════════════════

def print_banner():
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║  X 트렌드 자동 트윗 생성기 v{VERSION}                          ║
║  Cache × Retry × Multi-Country × Cost Tracking            ║
╚═══════════════════════════════════════════════════════════╝
""")


def print_config_summary(config: AppConfig):
    sources = ["getdaytrends.com"]
    if config.twitter_bearer_token:
        sources.append("X API")
    sources.extend(["Reddit", "Google News"])

    alerts_info = []
    if config.telegram_bot_token and config.telegram_chat_id:
        alerts_info.append("Telegram")
    if config.discord_webhook_url:
        alerts_info.append("Discord")

    features = []
    if config.enable_clustering:
        features.append("클러스터링")
    if config.enable_long_form:
        features.append(f"Premium+ 장문(≥{config.long_form_min_score}점)")
    if config.enable_threads:
        features.append("Threads")
    if config.smart_schedule:
        features.append("스마트 스케줄")
    if config.night_mode:
        features.append("야간 슬립(02-07시)")

    print(f"""
  설정 요약
  ─────────────────────────────────
  국가         : {config.country}
  트렌드 수    : {config.limit}개
  중복 제외    : {config.dedupe_window_hours}시간 이내 처리 키워드
  저장 방식    : {config.storage_type.upper()}
  실행 간격    : {config.schedule_minutes}분
  톤앤매너     : {config.tone}
  데이터 소스  : {', '.join(sources)}
  병렬 워커    : {config.max_workers}개
  알림 채널    : {', '.join(alerts_info) or '없음'}
  알림 임계값  : {config.alert_threshold}점
  LLM 라우팅   : shared.llm (티어 기반 자동 폴백)
  v2.1 기능    : {', '.join(features) or '없음'}
""")


# ══════════════════════════════════════════════════════
#  Content Cache Helper (C2)
# ══════════════════════════════════════════════════════

def _batch_from_cache(topic: str, rows: list[dict]) -> TweetBatch:
    """캐시된 트윗 행 → TweetBatch 재구성. 중복 tweet_type 중 최신 1개만 사용."""
    tweets: list[GeneratedTweet] = []
    long_posts: list[GeneratedTweet] = []
    threads_posts: list[GeneratedTweet] = []
    seen: set[tuple[str, str]] = set()

    for row in rows:
        ct = row.get("content_type", "short")
        tt = row.get("tweet_type", "")
        if (tt, ct) in seen:
            continue
        seen.add((tt, ct))
        t = GeneratedTweet(
            tweet_type=tt,
            content=row["content"],
            content_type=ct,
            char_count=row.get("char_count", len(row["content"])),
        )
        if ct == "long":
            long_posts.append(t)
        elif ct == "threads":
            threads_posts.append(t)
        else:
            tweets.append(t)

    return TweetBatch(topic=topic, tweets=tweets, long_posts=long_posts, threads_posts=threads_posts)


# ══════════════════════════════════════════════════════
#  Pipeline
# ══════════════════════════════════════════════════════

# ── Pipeline Sub-steps ─────────────────────────────────


async def _check_budget_and_adjust_limit(config: AppConfig, conn) -> tuple[AppConfig, bool]:
    """
    예산 상한 체크 + 적응형 limit 조정.
    [Q1] config를 직접 변경하지 않고 불변 복사본을 반환 (race condition 방지).
    Returns: (pipeline_config, budget_disabled_sonnet)
    """
    import dataclasses

    budget_disabled = False
    overrides: dict = {}

    # [C2] 시간대별 유효 예산 적용
    effective_budget = config.get_effective_budget()
    if effective_budget > 0:
        try:
            from shared.llm.stats import CostTracker
            from shared.llm.stats import _DB_PATH as _llm_db
            if _llm_db.exists():
                _tracker = CostTracker(persist=True)
                _daily = _tracker.get_daily_stats(1)
                _tracker.close()
                from datetime import date as _date
                _today = str(_date.today())
                _today_cost = sum(r["cost_usd"] for r in _daily if r.get("date") == _today)
                if _today_cost >= effective_budget:
                    overrides["enable_long_form"] = False
                    overrides["thread_min_score"] = 999
                    budget_disabled = True
                    print(f"\n  [예산 상한] 오늘 누적 ${_today_cost:.4f} ≥ ${config.daily_budget_usd:.2f} → Sonnet 비활성화")
        except Exception as _e:
            log.debug(f"예산 체크 실패 (무시): {_e}")

    # C4: 적응형 limit — 직전 런 평균 점수 기반 동적 조정
    prev_avg = await get_recent_avg_viral_score(conn, lookback_hours=3)
    if prev_avg is not None:
        if prev_avg < 60:
            overrides["limit"] = max(5, config.limit // 2)
            print(f"\n  [적응형 limit] 직전 평균 {prev_avg}점 → limit {overrides['limit']}개 (저품질 절약)")
        elif prev_avg >= 80:
            overrides["limit"] = min(15, config.limit + 2)
            print(f"\n  [적응형 limit] 직전 평균 {prev_avg}점 → limit {overrides['limit']}개 (고품질 확장)")

    # 불변 복사본 생성
    pipeline_config = dataclasses.replace(config, **overrides) if overrides else config
    return pipeline_config, budget_disabled


def _step_collect(config: AppConfig, conn, run: RunResult) -> tuple:
    """Step 1: 멀티소스 트렌드 수집."""
    print("\n[1/4] 멀티소스 트렌드 수집 중...")
    raw_trends, contexts = collect_trends(config, conn)
    run.trends_collected = len(raw_trends)
    print(f"  수집 완료: {len(raw_trends)}개 트렌드")
    return raw_trends, contexts


def _ensure_quality_and_diversity(
    scored_trends: list,
    config: AppConfig,
) -> list:
    """
    [v6.0] 카테고리 다양성 + 최소 기사 수 보장.

    3단계 선택 알고리즘:
    1. 카테고리별 최고 점수 1개씩 우선 선택 (다양성 보장)
    2. 남은 슬롯은 바이럴 점수 순으로 채움 (max_same_category 제한)
    3. min_article_count 미달 시 기준 동적 하향 (floor = min_viral_score * 0.6)
    """
    min_score = config.min_viral_score
    min_count = getattr(config, "min_article_count", 3)
    max_same = getattr(config, "max_same_category", 2)

    # safety_flag 트렌드 사전 제거
    safe_trends = [
        t for t in scored_trends
        if not (config.enable_sentiment_filter and getattr(t, "safety_flag", False))
    ]

    # [v7.0] 제외 카테고리 필터 + [v9.1] 가변형 카테고리 필터링(Dynamic Filtering)
    excluded_cats = set(getattr(config, "exclude_categories", []))
    if excluded_cats:
        before = len(safe_trends)
        filtered_trends = [
            t for t in safe_trends
            if (getattr(t, "category", "기타") or "기타") not in excluded_cats
        ]
        
        if len(filtered_trends) < getattr(config, "limit", min_count):
            log.warning(f"  [가변 필터] 트렌드 풀({len(filtered_trends)}개)이 부족. exclude_categories 조건 일시 해제 (부분 성공 허용).")
        else:
            safe_trends = filtered_trends
            excluded_count = before - len(safe_trends)
            if excluded_count:
                log.info(f"  [카테고리 제외] {excluded_count}개 제거 ({', '.join(excluded_cats)})")

    # 제외 후 남은 트렌드에 맞게 min_count 동적 축소
    min_count = min(min_count, len(safe_trends))

    if not safe_trends:
        return []

    # ── [v6.1] 최신성 등급 부여 + 만료 트렌드 패널티 ──
    _FRESHNESS_GRADES = [
        (0, 6, "fresh"),
        (6, 12, "recent"),
        (12, 24, "stale"),
        (24, float("inf"), "expired"),
    ]
    stale_penalty = getattr(config, "freshness_penalty_stale", 0.85)
    expired_penalty = getattr(config, "freshness_penalty_expired", 0.7)
    _PENALTY_MAP = {"fresh": 1.0, "recent": 1.0, "stale": stale_penalty, "expired": expired_penalty, "unknown": 0.95}

    for t in safe_trends:
        age = getattr(t, "content_age_hours", 0.0)
        grade = "unknown"
        for lo, hi, g in _FRESHNESS_GRADES:
            if lo <= age < hi:
                grade = g
                break
        t.freshness_grade = grade

        mult = _PENALTY_MAP.get(grade, 0.95)
        if mult < 1.0:
            original = t.viral_potential
            t.viral_potential = int(t.viral_potential * mult)
            log.debug(f"  [최신성 패널티] '{t.keyword}' {grade} ({age:.1f}h) ×{mult} → {original}→{t.viral_potential}점")

    # ── Pass 1: 카테고리별 최고 점수 1개씩 선택 (다양성 시드) ──
    cat_best: dict[str, list] = {}  # category → [trends by viral desc]
    for t in safe_trends:
        cat = getattr(t, "category", "기타") or "기타"
        cat_best.setdefault(cat, []).append(t)

    # 각 카테고리 내에서 바이럴 점수 내림차순 정렬
    for cat in cat_best:
        cat_best[cat].sort(key=lambda x: x.viral_potential, reverse=True)

    selected: list = []
    selected_set: set = set()
    cat_count: dict[str, int] = {}

    # 카테고리 우선순위: 각 카테고리의 최고 점수 기준 내림차순
    sorted_cats = sorted(
        cat_best.keys(),
        key=lambda c: cat_best[c][0].viral_potential if cat_best[c] else 0,
        reverse=True,
    )

    for cat in sorted_cats:
        candidates = cat_best[cat]
        best = candidates[0] if candidates else None
        if best and best.viral_potential >= min_score and id(best) not in selected_set:
            selected.append(best)
            selected_set.add(id(best))
            cat_count[cat] = cat_count.get(cat, 0) + 1

    log.debug(f"  [다양성 Pass1] 카테고리별 시드: {len(selected)}개 ({len(sorted_cats)}개 카테고리)")

    # ── Pass 2: 남은 슬롯을 바이럴 점수 순으로 채움 ──
    remaining = sorted(
        [t for t in safe_trends if id(t) not in selected_set],
        key=lambda x: x.viral_potential, reverse=True,
    )

    for t in remaining:
        if t.viral_potential < min_score:
            break
        cat = getattr(t, "category", "기타") or "기타"
        if cat_count.get(cat, 0) >= max_same:
            log.debug(f"  [다양성] '{t.keyword}' ({cat}) 스킵 — 카테고리 상한 {max_same}개 도달")
            continue
        selected.append(t)
        selected_set.add(id(t))
        cat_count[cat] = cat_count.get(cat, 0) + 1

    # ── Pass 3: 최소 기사 수 보장 (동적 기준 하향) ──
    if len(selected) < min_count:
        floor_score = int(min_score * 0.5)
        log.info(
            f"  [최소 기사] {len(selected)}개 < {min_count}개 → 기준 {min_score}점 → {floor_score}점 하향"
        )
        extras = sorted(
            [t for t in safe_trends if id(t) not in selected_set],
            key=lambda x: x.viral_potential, reverse=True,
        )
        for t in extras:
            if len(selected) >= min_count:
                break
            if t.viral_potential < floor_score:
                break
            cat = getattr(t, "category", "기타") or "기타"
            # Pass 3에서는 max_same_category 한도를 1개 여유 줌
            if cat_count.get(cat, 0) >= max_same + 1:
                continue
            selected.append(t)
            selected_set.add(id(t))
            cat_count[cat] = cat_count.get(cat, 0) + 1
            log.debug(f"  [최소 기사 보충] '{t.keyword}' ({t.viral_potential}점, {cat}) 추가")

    if len(selected) < min_count:
        log.warning(
            f"  [최소 기사] floor({floor_score}점) 적용 후에도 {len(selected)}/{min_count}개 → 가용 트렌드 부족"
        )

    # 바이럴 점수 내림차순 최종 정렬
    selected.sort(key=lambda x: x.viral_potential, reverse=True)
    return selected


async def _step_score_and_alert(
    raw_trends, contexts, config: AppConfig, conn, run: RunResult,
) -> tuple:
    """Step 2-3: 바이럴 스코어링 + 품질 필터 + 카테고리 다양성 + 최소 기사 보장 + 알림."""
    print("\n[2/4] 바이럴 스코어링 중 (병렬)...")
    scored_trends = analyze_trends(raw_trends, contexts, config, conn)
    run.trends_scored = len(scored_trends)

    # [v6.0] 카테고리 다양성 + 최소 기사 수 보장
    quality_trends = _ensure_quality_and_diversity(scored_trends, config)
    filtered_count = len(scored_trends) - len(quality_trends)
    if filtered_count:
        print(f"\n  ⚡ 품질 필터: {filtered_count}개 제외 (다양성+바이럴 기반)")

    # 카테고리 분포 로깅
    cat_dist: dict[str, int] = {}
    for t in quality_trends:
        cat = getattr(t, "category", "기타") or "기타"
        cat_dist[cat] = cat_dist.get(cat, 0) + 1
    run.category_distribution = cat_dist
    if cat_dist:
        dist_str = ", ".join(f"{k}:{v}" for k, v in sorted(cat_dist.items(), key=lambda x: -x[1]))
        print(f"  📊 카테고리 분포: {dist_str}")

    # verbose 모드: 배치 히스토리 조회 (N번 대신 1번 쿼리)
    history_map = {}
    if config.verbose:
        history_map = await get_trend_history_batch(conn, [st.keyword for st in scored_trends])

    # 스코어 미리보기
    for st in scored_trends:
        marker = " ✓" if st in quality_trends else " ✗"
        score_bar = "█" * (st.viral_potential // 10) + "░" * (10 - st.viral_potential // 10)
        print(f"  #{st.rank} [{score_bar}] {st.viral_potential:3d}점 | {st.keyword}{marker}")

        if config.verbose:
            history = history_map.get(st.keyword, [])
            if history:
                avg = round(sum(h["viral_potential"] for h in history) / len(history), 1)
                print(f"       ↳ 히스토리: {len(history)}회 등장, 평균 {avg}점")

    # [v9.0] Watchlist 모니터링 (스코어링 직후)
    if config.watchlist_keywords:
        wl_count = check_watchlist(scored_trends, config)
        if wl_count:
            print(f"\n  [WATCHLIST] 관심 키워드 {wl_count}건 감지 — 알림 전송")

    # 알림 전송 (스코어링 직후, 생성 전)
    if not config.no_alerts:
        alerts_sent = check_and_alert(scored_trends, config)
        run.alerts_sent = alerts_sent
        if alerts_sent:
            print(f"\n  알림 전송: {alerts_sent}건")

    return scored_trends, quality_trends


async def _step_generate(quality_trends, config: AppConfig, conn) -> list:
    """
    Step 4: 트윗/쓰레드 전체 병렬 생성 (C2 캐시 우선).
    v3.0: A/B 변형 + 멀티언어 추가 배치를 primary 배치에 병합.
    v6.0: 생성 후 QA 피드백 → 미달 시 1회 재생성.
    v9.0: QA 조건부 스킵 + 콘텐츠 다양성 주입 + 시간대별 생성 모드.
    """
    print(f"\n[3/4] 트윗 병렬 생성 중... ({len(quality_trends)}개 동시)")
    client = get_client()

    # [v9.0] 시간대별 생성 모드 결정
    gen_mode = config.get_generation_mode()
    if gen_mode == "lite":
        log.info(f"  [생성 모드] lite (비피크 시간) — 장문 생성 생략")

    async def _get_or_generate(trend):
        """C2: 콘텐츠 캐시 히트 시 LLM 건너뜀. 가속도 기반 TTL 차등화."""
        fp = compute_fingerprint(trend.keyword, trend.volume_last_24h,
                                 bucket=config.cache_volume_bucket)
        acc = getattr(trend, "trend_acceleration", "+0%")
        cache_ttl = 48 if (acc.startswith("-") or acc == "+0%") else 24
        cached = await get_cached_content(conn, fp, max_age_hours=cache_ttl)
        is_cached = bool(cached)

        if is_cached:
            log.info(f"  [콘텐츠 캐시] '{trend.keyword}' 재사용 ({len(cached)}개 항목, TTL={cache_ttl}h)")
            return _batch_from_cache(trend.keyword, cached)

        # [v9.0] 콘텐츠 다양성: 이전 생성 트윗 조회
        recent_tweets: list[str] = []
        if getattr(config, "enable_content_diversity", True):
            try:
                hours = getattr(config, "content_diversity_hours", 24)
                recent_tweets = await get_recent_tweet_contents(conn, trend.keyword, hours=hours)
            except Exception as _e:
                log.debug(f"  이전 트윗 조회 실패 (무시): {_e}")

        # [v9.0] 시간대별 생성 모드: lite면 장문 조건 일시 우회
        effective_config = config
        if gen_mode == "lite" and config.enable_long_form:
            import dataclasses
            effective_config = dataclasses.replace(config, enable_long_form=False)

        # 기본 생성
        primary = await generate_for_trend_async(trend, effective_config, client, recent_tweets)
        if primary is None:
            return primary

        # [v9.0] QA 조건부 스킵
        if not _should_skip_qa(trend, is_cached, config):
            from generator import audit_generated_content
            qa = await audit_generated_content(primary, trend, config, client)
            qa_min = getattr(config, "quality_feedback_min_score", 50)
            if qa and qa.get("avg_score", 100) < qa_min:
                corrected = qa.get("corrected_tweets", [])
                if corrected and primary.tweets:
                    corrected_map = {c.get("type", ""): c.get("content", "") for c in corrected}
                    applied = 0
                    for tweet in primary.tweets:
                        fixed = corrected_map.get(tweet.tweet_type, "")
                        if fixed:
                            tweet.content = fixed
                            tweet.char_count = len(fixed)
                            applied += 1
                    log.info(
                        f"  [QA 교정] '{trend.keyword}' {qa['avg_score']}점 → "
                        f"교정본 {applied}개 적용 (재생성 건너뜀)"
                    )
                else:
                    log.warning(
                        f"  [QA 미달] '{trend.keyword}' {qa['avg_score']}점 < {qa_min}점"
                        f" (사유: {qa.get('reason', '-')}) → 재생성"
                    )
                    primary = await generate_for_trend_async(trend, effective_config, client, recent_tweets)
                    if primary is None:
                        return primary
        else:
            log.debug(f"  [QA 스킵] '{trend.keyword}' (cached={is_cached}, score={trend.viral_potential})")

        # [v3.0 Phase 4] A/B 변형 병합
        if config.enable_ab_variants:
            ab = await generate_ab_variant_async(trend, config, client)
            if ab:
                primary.tweets.extend(ab.tweets)
                log.debug(f"A/B 변형 B 병합: '{trend.keyword}' (+{len(ab.tweets)}개)")

        # [v3.0 Phase 4] 멀티언어 병합
        if config.enable_multilang:
            lang_batches = await generate_for_trend_multilang_async(trend, config, client)
            for lb in lang_batches:
                primary.tweets.extend(lb.tweets)
                log.debug(f"멀티언어 [{lb.language}] 병합: '{trend.keyword}' (+{len(lb.tweets)}개)")

        return primary

    return await asyncio.gather(
        *[_get_or_generate(t) for t in quality_trends],
        return_exceptions=True,
    )


async def _step_save(
    quality_trends: list,
    batch_results: list,
    config: AppConfig,
    conn,
    run: RunResult,
    run_row_id: int,
) -> int:
    """
    Step 5: SQLite 원자적 트랜잭션 저장 + 외부 저장 병렬 처리.
    v3.0:
    - db_transaction()으로 trend + tweets 원자적 저장 (부분 저장 방지)
    - safety_flag=True 트렌드 스킵
    - 외부 저장 실패 시 run.errors에 기록 (무성 실패 제거)
    """
    print("\n[4/4] 저장 중...")
    success_count = 0
    ext_pairs: list[tuple] = []
    failed_saves: list[str] = []

    for trend, batch in zip(quality_trends, batch_results):
        # [v3.0 Phase 4] safety_flag 트렌드 스킵
        if config.enable_sentiment_filter and getattr(trend, "safety_flag", False):
            log.warning(f"유해 트렌드 스킵: '{trend.keyword}' (sentiment={trend.sentiment})")
            run.errors.append(f"safety_flag 스킵: {trend.keyword}")
            continue

        print(f"\n  '{trend.keyword}' (바이럴: {trend.viral_potential}점)")

        if isinstance(batch, Exception):
            log.error(f"생성 예외 ({trend.keyword}): {type(batch).__name__}: {batch}")
            run.errors.append(f"생성 예외: {trend.keyword}")
            continue
        if not batch:
            run.errors.append(f"생성 실패: {trend.keyword}")
            continue

        run.tweets_generated += len(batch.tweets) + len(batch.long_posts) + len(batch.threads_posts)

        for t in batch.tweets:
            preview = t.content[:50] + "..." if len(t.content) > 50 else t.content
            print(f"    [{t.tweet_type}] {preview}")
            # [v9.0] 게시 시간 학습 기록
            if t.best_posting_time and t.expected_engagement:
                try:
                    _hour = datetime.now().hour
                    category = getattr(trend, "category", "기타") or "기타"
                    await record_posting_time_stat(conn, category, _hour, t.expected_engagement)
                except Exception:
                    pass
        if batch.long_posts:
            print(f"    [Premium+ 장문] {len(batch.long_posts)}편")
        if batch.threads_posts:
            print(f"    [Threads] {len(batch.threads_posts)}편")
        if batch.thread:
            print(f"    [쓰레드] {len(batch.thread.tweets)}개 트윗")

        # [v3.0] 원자적 트랜잭션: trend + tweets 동시 실패 시 rollback
        try:
            async with db_transaction(conn):
                trend_id = await save_trend(
                    conn, trend, run_row_id,
                    bucket=config.cache_volume_bucket,
                )
                saved_to: list[str] = []

                if batch.tweets:
                    await save_tweets_batch(conn, batch.tweets, trend_id, run_row_id, saved_to=saved_to)
                    run.tweets_saved += len(batch.tweets)

                if batch.long_posts:
                    await save_tweets_batch(conn, batch.long_posts, trend_id, run_row_id, saved_to=saved_to)
                    run.tweets_saved += len(batch.long_posts)

                if batch.threads_posts:
                    await save_tweets_batch(conn, batch.threads_posts, trend_id, run_row_id, saved_to=saved_to)
                    run.tweets_saved += len(batch.threads_posts)

                if getattr(batch, "thread", None) and batch.thread.tweets:
                    await save_tweets_batch(
                        conn, batch.thread.tweets, trend_id, run_row_id,
                        is_thread=True, saved_to=saved_to,
                    )
                    run.tweets_saved += len(batch.thread.tweets)
        except Exception as e:
            log.error(f"SQLite 저장 실패 ({trend.keyword}): {e}")
            run.errors.append(f"DB 저장 실패: {trend.keyword}")
            failed_saves.append(trend.keyword)
            continue

        success_count += 1
        if not config.dry_run:
            ext_pairs.append((batch, trend))

    # Notion/Sheets 병렬 저장 (config.notion_sem_limit 동시, rate limit 보호)
    if ext_pairs and not config.dry_run:
        notion_sem = asyncio.Semaphore(config.notion_sem_limit)

        async def _do_ext_save(b, t) -> None:
            if config.storage_type in ("notion", "both"):
                async with notion_sem:
                    await asyncio.to_thread(save_to_notion, b, t, config)
            if config.storage_type in ("google_sheets", "both"):
                await asyncio.to_thread(save_to_google_sheets, b, t, config)

        ext_results = await asyncio.gather(
            *[_do_ext_save(b, t) for b, t in ext_pairs],
            return_exceptions=True,
        )
        ext_failed: list[str] = []
        for i, exc in enumerate(ext_results):
            if isinstance(exc, Exception):
                keyword = ext_pairs[i][1].keyword
                log.error(f"외부 저장 실패 ({keyword}): {exc}")
                run.errors.append(f"외부 저장 실패: {keyword}")
                ext_failed.append(keyword)

        if ext_failed:
            print(f"\n  외부 저장 실패 {len(ext_failed)}건: {', '.join(ext_failed)}")

    if failed_saves:
        print(f"\n  DB 저장 실패 {len(failed_saves)}건: {', '.join(failed_saves)}")

    return success_count


async def _adjust_schedule(scored_trends, config: AppConfig, schedule_callback=None):
    """O2-2: 적응형 스케줄링 — 평균 점수 기반 간격 조정."""
    if not (config.smart_schedule and not config.one_shot):
        if not config.one_shot:
            print(f"  다음 실행: {config.schedule_minutes}분 후")
        return

    callback = schedule_callback or (lambda: None)
    hot = [t for t in scored_trends
           if t.viral_potential >= 90 and _is_accelerating(t.trend_acceleration)]
    avg_score = (
        sum(t.viral_potential for t in scored_trends) / len(scored_trends)
        if scored_trends else 0
    )
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


# ── Pipeline Orchestrator ────────────────────────────────


async def _async_run_pipeline(config: AppConfig, schedule_callback=None) -> RunResult:
    """전체 파이프라인 (비동기): 수집 → 스코어링 → 알림 → 병렬생성 → 저장."""
    conn = await get_connection(config.db_path, database_url=config.database_url)
    try:
        await init_db(conn)
        run = RunResult(run_id=str(uuid.uuid4()), country=config.country)
        run_row_id = await save_run(conn, run)

        separator = "=" * 55
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{separator}")
        print(f"  작업 시작: {now_str}")
        print(separator)

        # Pre: 예산 + 적응형 limit 조정 (불변 복사본 반환)
        pipeline_config, budget_disabled = await _check_budget_and_adjust_limit(config, conn)

        # Step 1: 수집
        _t0 = time.time()
        raw_trends, contexts = _step_collect(pipeline_config, conn, run)
        _t1 = time.time()
        log.info(f"  [타이밍] 수집: {_t1 - _t0:.1f}초")
        if not raw_trends:
            run.errors.append("트렌드 수집 실패")
            run.finished_at = datetime.now()
            await update_run(conn, run, run_row_id)
            return run

        # Step 2-3: 스코어링 + 알림
        scored_trends, quality_trends = await _step_score_and_alert(
            raw_trends, contexts, pipeline_config, conn, run,
        )
        _t2 = time.time()
        log.info(f"  [타이밍] 스코어링+알림: {_t2 - _t1:.1f}초")

        # Step 4: 생성
        batch_results = await _step_generate(quality_trends, pipeline_config, conn)
        _t3 = time.time()
        log.info(f"  [타이밍] 생성: {_t3 - _t2:.1f}초")

        # Step 5: 저장
        success_count = await _step_save(
            quality_trends, batch_results, pipeline_config, conn, run, run_row_id,
        )
        _t4 = time.time()
        log.info(f"  [타이밍] 저장: {_t4 - _t3:.1f}초")

        # Post: 완료 기록 (config 원복 불필요 — 불변 복사본 사용)
        run.finished_at = datetime.now()
        await update_run(conn, run, run_row_id)

        elapsed = (run.finished_at - run.started_at).total_seconds()
        print(f"\n{separator}")
        print(f"  완료: {success_count}/{len(quality_trends)}개 저장")
        print(f"  소요: {elapsed:.1f}초")

        # [v3.0 Phase 3] 구조화 메트릭 로깅
        if pipeline_config.enable_structured_metrics:
            _total_cost = 0.0
            try:
                from shared.llm.stats import CostTracker
                from shared.llm.stats import _DB_PATH as _llm_db
                if _llm_db.exists():
                    _tracker = CostTracker(persist=True)
                    _daily = _tracker.get_daily_stats(1)
                    _tracker.close()
                    from datetime import date as _date
                    _today = str(_date.today())
                    _total_cost = sum(r["cost_usd"] for r in _daily if r.get("date") == _today)
            except Exception:
                pass
            log.info(
                "pipeline_metrics | "
                f"run_id={run.run_id[:8]} "
                f"country={run.country} "
                f"collected={run.trends_collected} "
                f"scored={run.trends_scored} "
                f"generated={run.tweets_generated} "
                f"saved={run.tweets_saved} "
                f"errors={len(run.errors)} "
                f"cost_usd={_total_cost:.4f} "
                f"duration_s={elapsed:.1f}"
            )

        # Post: 적응형 스케줄링
        await _adjust_schedule(scored_trends, config, schedule_callback)

        # [C3] 일일 비용 알림 (예산 70%+ 도달 시)
        try:
            from alerts import send_daily_cost_alert
            send_daily_cost_alert(pipeline_config)
        except Exception:
            pass

        print(separator)
        return run
    finally:
        await conn.close()


def run_pipeline(config: AppConfig, schedule_callback=None) -> RunResult:
    """동기 래퍼 (schedule 호환). 내부적으로 비동기 파이프라인 실행."""
    return run_async(_async_run_pipeline(config, schedule_callback))


# ══════════════════════════════════════════════════════
#  Cleanup (주 1회 주기)
# ══════════════════════════════════════════════════════

async def _maybe_cleanup(conn, days: int = 90) -> None:
    """마지막 정리 후 7일 이상 경과했을 때만 cleanup_old_records 실행."""
    last = await get_meta(conn, "last_cleanup")
    if last:
        elapsed = (datetime.now() - datetime.fromisoformat(last)).days
        if elapsed < 7:
            return
    count = await cleanup_old_records(conn, days=days)
    await set_meta(conn, "last_cleanup", datetime.now().isoformat())
    if count:
        log.info(f"자동 DB 정리: {count}개 레코드 삭제 ({days}일 초과)")


async def _maybe_send_weekly_cost_report(conn, config) -> None:
    """마지막 주간 비용 리포트 전송 후 7일 이상 경과했을 때만 전송."""
    if not (config.telegram_bot_token and config.telegram_chat_id):
        return
    last = await get_meta(conn, "last_weekly_cost_report")
    if last:
        elapsed = (datetime.now() - datetime.fromisoformat(last)).days
        if elapsed < 7:
            return
    if send_weekly_cost_report(config):
        await set_meta(conn, "last_weekly_cost_report", datetime.now().isoformat())


# ══════════════════════════════════════════════════════
#  Stats
# ══════════════════════════════════════════════════════

async def print_stats(config: AppConfig):
    """히스토리 통계 + LLM 비용 통계 출력."""
    conn = await get_connection(config.db_path, config.database_url)
    try:
        stats = await get_trend_stats(conn)
        print(f"""
  히스토리 통계
  ─────────────────────────────────
  총 실행 수      : {stats['total_runs']}회
  총 트렌드 수    : {stats['total_trends']}개
  평균 바이럴 점수: {stats['avg_viral_score']}점
  총 생성 트윗 수 : {stats['total_tweets']}개
""")
    finally:
        await conn.close()

    # LLM 비용 통계 (최근 7일)
    try:
        from shared.llm.stats import CostTracker
        from shared.llm.stats import _DB_PATH as llm_db_path
        if llm_db_path.exists():
            tracker = CostTracker(persist=True)
            daily = tracker.get_daily_stats(7)
            tracker.close()

            if daily:
                print("  LLM 비용 (최근 7일)")
                print("  ─────────────────────────────────")
                by_day: dict = {}
                for row in daily:
                    d = row["date"]
                    by_day.setdefault(d, {"cost": 0.0, "calls": 0})
                    by_day[d]["cost"] += row["cost_usd"]
                    by_day[d]["calls"] += row["calls"]
                total_cost = sum(v["cost"] for v in by_day.values())
                for day in sorted(by_day.keys(), reverse=True)[:7]:
                    v = by_day[day]
                    print(f"  {day} : ${v['cost']:.4f}  ({v['calls']}콜)")
                print(f"  ─────────────────────────────────")
                print(f"  7일 합계       : ${total_cost:.4f}")
                print(f"  월 추정 비용   : ${total_cost / 7 * 30:.2f}")
                print()
    except Exception as e:
        log.debug(f"LLM 비용 통계 조회 실패: {e}")


# ══════════════════════════════════════════════════════
#  Entry Point
# ══════════════════════════════════════════════════════

def main():
    args = parse_args()

    # 설정 로드
    config = AppConfig.from_env()

    # CLI 오버라이드
    if args.countries:
        countries = [c.strip() for c in args.countries.split(",") if c.strip()]
        config.country = countries[0]
        config.countries = countries
    elif args.country:
        config.country = args.country
        config.countries = [args.country]
    if args.limit:
        config.limit = args.limit
    if args.one_shot:
        config.one_shot = True
    if args.dry_run:
        config.dry_run = True
    if args.verbose:
        config.verbose = True
    if args.no_alerts:
        config.no_alerts = True
    if args.schedule_min:
        config.schedule_minutes = args.schedule_min

    setup_logging(config.verbose)
    print_banner()

    # SIGTERM / SIGINT 핸들러 등록
    _install_signal_handlers()

    # DB 초기화 등 앱 레벨 초기 설정
    async def _app_init():
        _conn = await get_connection(config.db_path, database_url=config.database_url)
        await init_db(_conn)
        await _maybe_cleanup(_conn, days=config.data_retention_days)
        await _maybe_send_weekly_cost_report(_conn, config)
        await _conn.close()
    asyncio.run(_app_init())

    # --serve 모드: 대시보드 웹 서버 (O1-3)
    if args.serve:
        try:
            import uvicorn
            from dashboard import app as _dashboard_app
            print("\n  대시보드 서버 시작: http://localhost:8080\n")
            uvicorn.run(_dashboard_app, host="0.0.0.0", port=8080)
        except ImportError as e:
            print(f"\n  서버 실행 실패: {e}")
            print("  → pip install uvicorn 후 재시도\n")
        return

    # --stats 모드
    if args.stats:
        asyncio.run(print_stats(config))
        return

    # 설정 검증 (dry-run이면 storage 키 없어도 허용)
    if config.dry_run:
        from shared.llm.config import load_keys
        keys = load_keys()
        if not any(keys.values()):
            print("\n  설정 오류:\n    LLM API 키가 설정되지 않았습니다.\n  → 루트 .env 파일을 확인해주세요\n")
            return
    else:
        errors = config.validate()
        if errors:
            print("\n  설정 오류:")
            for e in errors:
                print(f"    {e}")
            print("\n  → .env 파일을 확인해주세요\n")
            return

    print_config_summary(config)

    # 즉시 1회 실행 (다국가 지원)
    def _run_all_countries():
        for country in config.countries:
            country_config = config.for_country(country) if country != config.country else config
            if len(config.countries) > 1:
                print(f"\n  ═══ 국가: {country.upper()} ═══")
            run_pipeline(country_config, schedule_callback=_run_all_countries)

    _run_all_countries()

    # one-shot이면 여기서 종료
    if config.one_shot:
        print("\n(one-shot 모드: 종료)")
        return

    # 스케줄 등록
    schedule.every(config.schedule_minutes).minutes.do(_run_all_countries)
    print(f"\n  스케줄러 가동 중... ({config.schedule_minutes}분마다)")
    if config.night_mode:
        print("  야간 슬립: 02:00~07:00 자동 대기")
    print("  중단: Ctrl+C\n")

    try:
        while not _SHUTDOWN_FLAG.is_set():
            # 야간 슬립: 02:00~07:00 사이 실행 건너뜀
            if config.night_mode:
                now_hour = datetime.now().hour
                if 2 <= now_hour < 7:
                    wake_at = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
                    sleep_seconds = (wake_at - datetime.now()).total_seconds()
                    if sleep_seconds > 0:
                        log.info(f"야간 슬립: 07:00까지 {sleep_seconds/60:.0f}분 대기")
                        print(f"  야간 슬립 중... (07:00 기상, {sleep_seconds/60:.0f}분 후)")
                        # 1초씩 나눠 sleep해서 종료 신호를 빠르게 감지
                        for _ in range(int(sleep_seconds)):
                            if _SHUTDOWN_FLAG.is_set():
                                break
                            time.sleep(1)
                        continue

            schedule.run_pending()
            time.sleep(1)  # 1초 단위로 폴링해야 SIGTERM을 즉시 감지
    except KeyboardInterrupt:
        _SHUTDOWN_FLAG.set()
    finally:
        # 우아한 종료: asyncpg Pool 정리
        async def _cleanup():
            await close_pg_pool()
        asyncio.run(_cleanup())
        print("\n\n  스케줄러 종료. 수고하셨습니다!")


if __name__ == "__main__":
    main()
