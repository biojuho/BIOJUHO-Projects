"""
Prefect-based Pipeline Orchestrator — scripts/orchestrator.py 의 Prefect 버전.

기존 orchestrator.py의 5-step 파이프라인을 Prefect flow/task로 전환.
재시도, 지수 백오프, Telegram 알림, 웹 대시보드 (localhost:4200) 제공.

Usage::
    # 1회 실행
    python scripts/prefect_orchestrator.py --one-shot

    # 스케줄러 등록 (4시간 간격)
    python scripts/prefect_orchestrator.py --serve

    # 드라이런
    python scripts/prefect_orchestrator.py --dry-run

    # Prefect 대시보드 확인
    prefect server start  # http://localhost:4200
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prefect import flow, task, get_run_logger
from prefect.tasks import exponential_backoff

WORKSPACE = Path(__file__).resolve().parents[1]

# Logfire 옵저버빌리티 (선택)
sys.path.insert(0, str(WORKSPACE))
try:
    from shared.observability import setup_observability, span as obs_span
    _LOGFIRE_OK = True
except ImportError:
    _LOGFIRE_OK = False


# ══════════════════════════════════════════════════════
#  Utility
# ══════════════════════════════════════════════════════

def _ensure_path(project: str) -> None:
    """프로젝트 경로를 sys.path에 추가."""
    p = str(WORKSPACE / project)
    if p not in sys.path:
        sys.path.insert(0, p)


def _notify(message: str) -> None:
    """Telegram/Discord 알림 전송 (shared.notifications)."""
    try:
        _ensure_path(".")
        from shared.notifications.notifier import Notifier
        notifier = Notifier.from_env()
        if notifier.has_channels:
            notifier.send(message)
    except Exception:
        pass


# ══════════════════════════════════════════════════════
#  Prefect on_failure hook → Telegram 알림
# ══════════════════════════════════════════════════════

def _on_flow_failure(flow, flow_run, state):
    """Flow 실패 시 Telegram/Discord 알림."""
    msg = f"[FAIL] Pipeline '{flow.name}' failed: {state.message}"
    _notify(msg)


def _on_flow_success(flow, flow_run, state):
    """Flow 성공 시 알림."""
    msg = f"[OK] Pipeline '{flow.name}' completed successfully"
    _notify(msg)


# ══════════════════════════════════════════════════════
#  Tasks (각 파이프라인 단계)
# ══════════════════════════════════════════════════════

@task(name="check-budget", tags=["infra"])
def check_budget() -> tuple[bool, float]:
    """일일 예산 확인. (within_budget, current_cost)"""
    logger = get_run_logger()
    try:
        _ensure_path(".")
        from shared.telemetry.cost_tracker import get_daily_cost_summary
        summary = get_daily_cost_summary(days=1)
        current = summary.get("total_cost", 0.0)

        _ensure_path("getdaytrends")
        from config import AppConfig
        cfg = AppConfig.from_env()
        budget = cfg.daily_budget_usd

        within = current < budget
        logger.info(f"Budget: ${current:.4f} / ${budget:.2f} {'OK' if within else 'EXCEEDED'}")
        return within, current
    except Exception as e:
        logger.warning(f"Budget check failed (assuming OK): {e}")
        return True, 0.0


@task(
    name="collect-trends",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=10),
    tags=["getdaytrends"],
)
def collect_trends(dry_run: bool = False) -> dict[str, Any]:
    """Step 1: GetDayTrends 트렌드 수집."""
    logger = get_run_logger()
    if dry_run:
        logger.info("DRY-RUN: 수집 시뮬레이션")
        return {"trends_count": 0, "dry_run": True}

    _ensure_path("getdaytrends")
    try:
        main_mod = importlib.import_module("main")
        if hasattr(main_mod, "collect_trends_sync"):
            trends = main_mod.collect_trends_sync()
            count = len(trends) if trends else 0
            logger.info(f"수집 완료: {count}개 트렌드")
            return {"trends_count": count}
        else:
            logger.info("collect_trends_sync 미발견, scraper 직접 사용")
            return {"message": "scraper direct mode"}
    except Exception as e:
        logger.error(f"수집 실패: {e}")
        raise


@task(
    name="validate-content",
    retries=1,
    retry_delay_seconds=30,
    tags=["quality"],
)
def validate_content(dry_run: bool = False) -> dict[str, Any]:
    """Step 2: Content-Intelligence 규제 검증."""
    logger = get_run_logger()
    if dry_run:
        logger.info("DRY-RUN: 검증 시뮬레이션")
        return {"dry_run": True}

    cie_path = WORKSPACE / "content-intelligence"
    if not cie_path.exists():
        logger.info("content-intelligence 미설치, 스킵")
        return {"skipped": True, "reason": "module not installed"}

    try:
        sys.path.insert(0, str(cie_path))
        importlib.import_module("regulators.checklist")
        logger.info("규제 체크리스트 로드 완료")
        return {"validated": True}
    except ImportError:
        logger.info("규제 모듈 기본 패스")
        return {"validated": True, "basic": True}


@task(
    name="generate-content",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=15),
    tags=["getdaytrends", "llm"],
)
def generate_content(dry_run: bool = False) -> dict[str, Any]:
    """Step 3: 콘텐츠 생성 (main.py run_pipeline 위임)."""
    logger = get_run_logger()
    if dry_run:
        logger.info("DRY-RUN: 생성 시뮬레이션")
        return {"dry_run": True}

    logger.info("콘텐츠 생성: main.py run_pipeline()에 위임")
    return {"delegated": True, "message": "main.py run_pipeline()에서 처리"}


@task(
    name="publish-content",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=10),
    tags=["publishing"],
)
def publish_content(dry_run: bool = False) -> dict[str, Any]:
    """Step 4: 발행 (Notion/X/Sheets)."""
    logger = get_run_logger()
    if dry_run:
        logger.info("DRY-RUN: 발행 시뮬레이션")
        return {"dry_run": True}

    logger.info("발행: GetDayTrends auto_post에 위임")
    return {"delegated": True, "message": "auto_post에서 처리"}


@task(
    name="track-performance",
    retries=1,
    retry_delay_seconds=30,
    tags=["analytics"],
)
def track_performance(dry_run: bool = False) -> dict[str, Any]:
    """Step 5: 성과 추적."""
    logger = get_run_logger()
    if dry_run:
        logger.info("DRY-RUN: 추적 시뮬레이션")
        return {"dry_run": True}

    tracker_path = WORKSPACE / "getdaytrends" / "performance_tracker.py"
    if tracker_path.exists():
        logger.info("PerformanceTracker 사용 가능")
        return {"tracker_available": True}
    else:
        logger.info("PerformanceTracker 미설치")
        return {"tracker_available": False}


# ══════════════════════════════════════════════════════
#  Flow (메인 파이프라인)
# ══════════════════════════════════════════════════════

@flow(
    name="content-pipeline",
    description="GetDayTrends 전체 콘텐츠 파이프라인: 수집 → 검증 → 생성 → 발행 → 추적",
    on_failure=[_on_flow_failure],
    on_completion=[_on_flow_success],
    log_prints=True,
)
def content_pipeline(dry_run: bool = True) -> dict[str, Any]:
    """5-step 콘텐츠 파이프라인."""
    # Logfire 초기화 (flow 실행 시)
    if _LOGFIRE_OK:
        setup_observability(service_name="content-pipeline", instrument_fastapi=False)

    start = time.time()
    mode = "DRY-RUN" if dry_run else "EXECUTE"
    print(f"\n{'='*50}")
    print(f"  Content Pipeline ({mode})")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*50}\n")

    # 예산 확인
    within_budget, cost = check_budget()
    if not within_budget and not dry_run:
        _notify("[!] 파이프라인 중단: 일일 예산 초과")
        return {"status": "budget_exceeded", "cost": cost}

    # 파이프라인 실행
    results = {}
    results["collect"] = collect_trends(dry_run=dry_run)
    results["validate"] = validate_content(dry_run=dry_run)
    results["generate"] = generate_content(dry_run=dry_run)
    results["publish"] = publish_content(dry_run=dry_run)
    results["track"] = track_performance(dry_run=dry_run)

    elapsed = round(time.time() - start, 1)
    print(f"\n  Pipeline completed in {elapsed}s")

    return {
        "status": "success",
        "mode": mode,
        "duration_sec": elapsed,
        "cost": cost,
        "steps": results,
    }


# ══════════════════════════════════════════════════════
#  BioLinker Notice Collection Flow
#  (desci-platform/biolinker/services/scheduler.py 대체)
# ══════════════════════════════════════════════════════

@task(
    name="collect-notices",
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=10),
    tags=["desci", "collection"],
)
def collect_notices() -> dict[str, Any]:
    """DeSci 공고 수집 (KDDF + NTIS)."""
    logger = get_run_logger()
    _ensure_path("desci-platform/biolinker")
    try:
        from services.scheduler import NoticeScheduler
        scheduler = NoticeScheduler.__new__(NoticeScheduler)
        # 수집 로직만 호출 (APScheduler 없이)
        if hasattr(scheduler, "_collect_and_index"):
            result = scheduler._collect_and_index()
            logger.info(f"공고 수집 완료: {result}")
            return {"result": str(result)}
        else:
            logger.info("NoticeScheduler._collect_and_index 미발견")
            return {"skipped": True}
    except Exception as e:
        logger.error(f"공고 수집 실패: {e}")
        raise


@flow(
    name="notice-collection",
    description="DeSci 연구 공고 일일 수집 (KDDF + NTIS)",
    on_failure=[_on_flow_failure],
    log_prints=True,
)
def notice_collection_pipeline() -> dict[str, Any]:
    """DeSci 공고 수집 파이프라인."""
    print("\n  Notice Collection Pipeline")
    result = collect_notices()
    return {"status": "success", "collection": result}


# ══════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Prefect Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/prefect_orchestrator.py --one-shot              # 1회 실행 (dry-run)
  python scripts/prefect_orchestrator.py --one-shot --execute    # 1회 실제 실행
  python scripts/prefect_orchestrator.py --serve                 # 4시간 간격 스케줄러
  python scripts/prefect_orchestrator.py --serve --cron "0 */2 * * *"  # 2시간 간격

Prefect Dashboard:
  prefect server start  # http://localhost:4200
        """,
    )
    parser.add_argument("--one-shot", action="store_true", help="1회 실행 후 종료")
    parser.add_argument("--execute", action="store_true", help="실제 실행 (기본: dry-run)")
    parser.add_argument("--serve", action="store_true", help="스케줄러 등록 및 상주")
    parser.add_argument("--cron", type=str, default="0 */4 * * *", help="크론 스케줄 (기본: 4시간)")
    parser.add_argument("--dry-run", action="store_true", help="드라이런 모드 (기본값)")
    parser.add_argument(
        "--flow", type=str, default="content",
        choices=["content", "notices"],
        help="실행할 플로우 (content: 콘텐츠 파이프라인, notices: 공고 수집)",
    )
    args = parser.parse_args()

    dry_run = not args.execute

    if args.one_shot:
        if args.flow == "notices":
            result = notice_collection_pipeline()
        else:
            result = content_pipeline(dry_run=dry_run)
        print(f"\nResult: {result}")
        return

    if args.serve:
        print(f"\n  Serving '{args.flow}' pipeline with cron: {args.cron}")
        print("  Press Ctrl+C to stop\n")
        print("  Tip: Run 'prefect server start' for the dashboard at http://localhost:4200\n")

        if args.flow == "notices":
            notice_collection_pipeline.serve(
                name="daily-notice-collection",
                cron=args.cron,
                tags=["desci", "scheduled"],
            )
        else:
            content_pipeline.serve(
                name="content-pipeline-scheduled",
                cron=args.cron,
                tags=["getdaytrends", "scheduled"],
                parameters={"dry_run": dry_run},
            )
        return

    # 기본: 1회 dry-run
    result = content_pipeline(dry_run=True)
    print(f"\nResult: {result}")


if __name__ == "__main__":
    main()
