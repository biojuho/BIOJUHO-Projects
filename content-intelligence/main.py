"""
=======================================================
  Content Intelligence Engine (CIE) v1.0
  트렌드 & 플랫폼 규제 반영 콘텐츠 창작 시스템

  4단계 파이프라인:
    1단계: 트렌드 수집 (X, Threads, 네이버)
    2단계: 플랫폼 규제 & 알고리즘 점검
    3단계: 콘텐츠 생성 / 최적화 / QA 검증
    보너스: 월간 회고 & 시스템 업데이트

  Usage:
    python main.py --mode full          # 전체 파이프라인
    python main.py --mode trend         # 트렌드 수집만
    python main.py --mode regulation    # 규제 점검만
    python main.py --mode review        # 월간 회고
    python main.py --dry-run            # LLM 호출 없이 구조 검증
=======================================================
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# ── PYTHONPATH 설정 ──
_CIE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CIE_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_CIE_DIR) not in sys.path:
    sys.path.insert(0, str(_CIE_DIR))

from loguru import logger as log

from config import CIEConfig
from storage.models import MergedTrendReport


# ══════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Content Intelligence Engine — 트렌드 반영 콘텐츠 창작 시스템"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "trend", "regulation", "review"],
        default="full",
        help="실행 모드 (기본: full)",
    )
    parser.add_argument("--dry-run", action="store_true", help="LLM 호출 없이 구조 검증")
    parser.add_argument("--verbose", action="store_true", help="상세 로그")
    return parser.parse_args()


# ══════════════════════════════════════════════════════
#  Logging
# ══════════════════════════════════════════════════════

def setup_logging(verbose: bool = False) -> None:
    log.remove()
    level = "DEBUG" if verbose else "INFO"
    log.add(sys.stderr, level=level, format="{time:HH:mm:ss} | {level:7} | {message}")
    log.add(
        str(_CIE_DIR / "logs" / "cie.log"),
        rotation="1 week",
        retention="4 weeks",
        level="DEBUG",
    )


# ══════════════════════════════════════════════════════
#  Banner
# ══════════════════════════════════════════════════════

def print_banner(config: CIEConfig, mode: str) -> None:
    log.info("═" * 55)
    log.info("  Content Intelligence Engine (CIE) v1.0")
    log.info("  트렌드 & 플랫폼 규제 반영 콘텐츠 창작 시스템")
    log.info("═" * 55)
    log.info(f"  모드: {mode.upper()}")
    log.info(config.summary())
    log.info("═" * 55)


# ══════════════════════════════════════════════════════
#  Pipeline Steps
# ══════════════════════════════════════════════════════

async def step_collect_trends(config: CIEConfig) -> MergedTrendReport:
    """Step 1: 멀티플랫폼 트렌드 수집 (병렬)."""
    log.info("\n" + "─" * 40)
    log.info("📡 STEP 1: 트렌드 수집")
    log.info("─" * 40)

    from collectors.x_collector import collect_x_trends
    from collectors.threads_collector import collect_threads_trends
    from collectors.naver_collector import collect_naver_trends

    collector_map = {
        "x": collect_x_trends,
        "threads": collect_threads_trends,
        "naver": collect_naver_trends,
    }

    tasks = []
    for platform in config.platforms:
        if platform in collector_map:
            tasks.append(collector_map[platform](config))
        else:
            log.warning(f"  ⚠️ 알 수 없는 플랫폼: {platform}")

    reports = await asyncio.gather(*tasks, return_exceptions=True)

    valid_reports = []
    for r in reports:
        if isinstance(r, Exception):
            log.error(f"  ❌ 수집 실패: {r}")
        else:
            valid_reports.append(r)

    # 교차 플랫폼 키워드 식별
    all_keywords: dict[str, int] = {}
    for report in valid_reports:
        for t in report.trends:
            kw = t.keyword.lower()
            all_keywords[kw] = all_keywords.get(kw, 0) + 1

    cross_platform = [k for k, v in all_keywords.items() if v >= 2]

    # 인사이트 통합
    all_insights = []
    for report in valid_reports:
        all_insights.extend(report.key_insights[:2])

    merged = MergedTrendReport(
        platform_reports=valid_reports,
        cross_platform_keywords=cross_platform,
        top_insights=all_insights[:5],
        created_at=datetime.now(),
    )

    total_trends = sum(len(r.trends) for r in valid_reports)
    log.info(
        f"\n  📊 트렌드 수집 요약: {len(valid_reports)}개 플랫폼, "
        f"{total_trends}개 트렌드"
    )
    if cross_platform:
        log.info(f"  🔗 교차 플랫폼 키워드: {', '.join(cross_platform)}")

    return merged


async def step_check_regulations(config: CIEConfig):
    """Step 2: 플랫폼 규제 & 알고리즘 점검."""
    log.info("\n" + "─" * 40)
    log.info("🔍 STEP 2: 규제 점검")
    log.info("─" * 40)

    from regulators.checklist import check_all_regulations, generate_unified_checklist

    reports = await check_all_regulations(config)
    checklist = generate_unified_checklist(reports)

    return reports, checklist


async def step_generate_content(config, trend_report, checklist):
    """Step 3: 콘텐츠 생성 + QA 검증."""
    log.info("\n" + "─" * 40)
    log.info("✍️ STEP 3: 콘텐츠 생성")
    log.info("─" * 40)

    from generators.content_engine import generate_all_content, validate_and_regenerate

    batch = await generate_all_content(trend_report, checklist, config)

    if config.enable_qa_validation:
        log.info("\n  🔬 QA 검증 시작...")
        batch = await validate_and_regenerate(batch, config)

    return batch


async def step_save(config, trend_report=None, regulation_reports=None, batch=None):
    """Step 4: 로컬 DB 저장."""
    log.info("\n" + "─" * 40)
    log.info("💾 STEP 4: 저장")
    log.info("─" * 40)

    from storage.local_db import get_connection, save_trends, save_regulations, save_contents

    conn = get_connection(config)
    try:
        if trend_report:
            save_trends(conn, trend_report)
        if regulation_reports:
            save_regulations(conn, regulation_reports)
        if batch:
            save_contents(conn, batch)
    finally:
        conn.close()


# ══════════════════════════════════════════════════════
#  Main Pipeline
# ══════════════════════════════════════════════════════

async def run_pipeline(config: CIEConfig, mode: str = "full") -> None:
    """CIE 메인 파이프라인."""
    start = datetime.now()

    if mode == "trend":
        trend_report = await step_collect_trends(config)
        await step_save(config, trend_report=trend_report)

    elif mode == "regulation":
        reports, checklist = await step_check_regulations(config)
        await step_save(config, regulation_reports=reports)
        log.info(f"\n📋 체크리스트:\n{checklist.to_checklist_text()}")

    elif mode == "review":
        from review.monthly_review import run_monthly_review
        from storage.local_db import get_connection, save_review

        review = await run_monthly_review(config)
        conn = get_connection(config)
        try:
            save_review(conn, review)
        finally:
            conn.close()

        # 결과 출력
        log.info("\n📊 월간 회고 결과:")
        for s in review.next_month_strategy:
            log.info(f"  📌 {s}")
        for imp in review.system_improvements:
            log.info(f"  🔧 {imp}")

    else:  # full
        # Step 1
        trend_report = await step_collect_trends(config)

        # Step 2
        reports, checklist = await step_check_regulations(config)

        # Step 3
        batch = await step_generate_content(config, trend_report, checklist)

        # Step 4
        await step_save(config, trend_report, reports, batch)

        # 결과 요약
        log.info("\n" + "═" * 55)
        log.info("  📦 파이프라인 결과 요약")
        log.info("═" * 55)
        log.info(f"  {batch.summary()}")
        for c in batch.contents:
            qa_str = c.qa_report.to_emoji_report() if c.qa_report else "(미검증)"
            log.info(f"  [{c.platform.upper()}/{c.content_type}] {qa_str}")
            if c.body:
                preview = c.body[:100].replace("\n", " ") + "..."
                log.info(f"    📝 {preview}")

    elapsed = (datetime.now() - start).total_seconds()
    log.info(f"\n⏱️ 소요 시간: {elapsed:.1f}초")


# ══════════════════════════════════════════════════════
#  Entry Point
# ══════════════════════════════════════════════════════

def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)
    config = CIEConfig()
    print_banner(config, args.mode)

    if args.dry_run:
        log.info("🧪 DRY RUN 모드 — LLM 호출 없이 구조 검증만 수행")
        log.info(f"  설정 로드: ✅")
        log.info(f"  플랫폼: {config.platforms}")
        log.info(f"  DB 경로: {config.sqlite_path}")
        log.info(f"  Notion: {'연결됨' if config.notion_database_id else '미설정'}")

        from storage.local_db import get_connection, ensure_schema
        conn = get_connection(config)
        ensure_schema(conn)
        conn.close()
        log.info("  DB 스키마: ✅")
        log.info("🧪 DRY RUN 완료 — 모든 구조 정상")
        return

    asyncio.run(run_pipeline(config, args.mode))


if __name__ == "__main__":
    main()
