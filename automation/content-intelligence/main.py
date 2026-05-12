"""
=======================================================
  Content Intelligence Engine (CIE) v2.0
  트렌드 & 플랫폼 규제 반영 콘텐츠 창작 + 자동 발행 시스템

  5단계 파이프라인:
    1단계: 트렌드 수집 (GDT Bridge + X, Threads, 네이버)
    2단계: 플랫폼 규제 & 컴플라이언스 점검
    3단계: 콘텐츠 생성 / 최적화 / QA 검증
    4단계: 로컬 DB 저장
    5단계: 발행 (Notion + X)
    보너스: 월간 리뷰 & 시스템 업데이트

  Usage:
    python main.py --mode full              # 전체 파이프라인(발행 제외)
    python main.py --mode full --publish    # 전체 + Notion/X 발행
    python main.py --mode trend             # 트렌드 수집만
    python main.py --mode regulation        # 규제 점검만
    python main.py --mode review            # 월간 리뷰
    python main.py --mode publish-only      # 미발행 콘텐츠 발행
    python main.py --dry-run                # LLM 호출 없이 구조 검증
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

from config import CIEConfig
from loguru import logger as log
from storage.models import MergedTrendReport

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CLI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Content Intelligence Engine v2.0 trend-aware content generation pipeline",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "trend", "regulation", "review", "publish-only"],
        default="full",
        help="실행 모드 (기본: full)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate structure without live LLM calls")
    parser.add_argument("--publish", action="store_true", help="콘텐츠 자동 발행 (Notion + X)")
    parser.add_argument("--verbose", action="store_true", help="상세 로그")
    return parser.parse_args()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Logging
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Banner
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def print_banner(config: CIEConfig, mode: str, publish: bool) -> None:
    log.info("=" * 55)
    log.info("  Content Intelligence Engine (CIE) v2.0")
    log.info("  트렌드 & 플랫폼 규제 반영 콘텐츠 창작 + 발행")
    log.info("=" * 55)
    log.info(f"  모드: {mode.upper()}" + (" + 발행" if publish else ""))
    log.info(config.summary())
    log.info("=" * 55)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Pipeline Steps
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _trend_quorum_required(platform_count: int) -> int:
    if platform_count <= 0:
        return 0
    if platform_count == 1:
        return 1
    return 2


def _has_trend_quorum(report: MergedTrendReport) -> bool:
    return len(report.platform_reports) >= report.quorum_required


async def step_collect_trends(config: CIEConfig) -> MergedTrendReport:
    """Step 1: 멀티플랫폼 트렌드 수집 (병렬)."""
    log.info("\n" + "━" * 40)
    log.info("📊 STEP 1: 트렌드 수집")
    log.info("━" * 40)

    from collectors.naver_collector import collect_naver_trends
    from collectors.threads_collector import collect_threads_trends
    from collectors.x_collector import collect_x_trends

    collector_map = {
        "x": collect_x_trends,
        "threads": collect_threads_trends,
        "naver": collect_naver_trends,
    }

    declared_platforms = list(dict.fromkeys(config.platforms))
    requested_platforms: list[str] = []
    failed_platforms: list[str] = []
    tasks = []
    for platform in declared_platforms:
        if platform in collector_map:
            requested_platforms.append(platform)
            tasks.append(collector_map[platform](config))
        else:
            failed_platforms.append(platform)
            log.warning(f"  수집 불가능한 플랫폼: {platform}")

    reports = await asyncio.gather(*tasks, return_exceptions=True)

    valid_reports = []
    for r in reports:
        if isinstance(r, BaseException):
            log.error(f"  수집 실패: {r}")
        else:
            valid_reports.append(r)

    for platform, result in zip(requested_platforms, reports, strict=False):
        if isinstance(result, BaseException):
            failed_platforms.append(platform)
    failed_platforms = list(dict.fromkeys(failed_platforms))
    quorum_required = _trend_quorum_required(len(declared_platforms))
    degraded = bool(failed_platforms)
    publish_blocked = degraded or len(valid_reports) < quorum_required

    if not valid_reports:
        return MergedTrendReport(
            platform_reports=[],
            cross_platform_keywords=[],
            top_insights=[],
            failed_platforms=failed_platforms or declared_platforms,
            degraded=True,
            publish_blocked=True,
            quorum_required=quorum_required,
        )



    # 교차 플랫폼 키워드 집계
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
    merged.degraded = degraded
    merged.failed_platforms = failed_platforms
    merged.publish_blocked = publish_blocked
    merged.quorum_required = quorum_required

    total_trends = sum(len(r.trends) for r in valid_reports)
    log.info(f"\n  Trend collection summary: {len(valid_reports)} platforms / {total_trends} trends")
    if cross_platform:
        log.info(f"  🔗 교차 플랫폼 키워드: {', '.join(cross_platform)}")

    if degraded:
        log.warning(f"  [degraded] failed platforms: {', '.join(failed_platforms)}")
    if publish_blocked:
        log.warning(
            f"  [publish blocked] collected {len(valid_reports)}/{len(declared_platforms)} platforms "
            f"(quorum={quorum_required})"
        )

    return merged


async def step_check_regulations(config: CIEConfig):
    """Step 2: 플랫폼 규제 & 컴플라이언스 점검."""
    log.info("\n" + "━" * 40)
    log.info("📋 STEP 2: 규제 점검")
    log.info("━" * 40)

    from regulators.checklist import check_all_regulations, generate_unified_checklist

    reports = await check_all_regulations(config)
    checklist = generate_unified_checklist(reports)

    return reports, checklist


async def step_generate_content(config, trend_report, checklist):
    """Step 3: 콘텐츠 생성 + QA 검증"""
    log.info("\n" + "━" * 40)
    log.info("✍️ STEP 3: 콘텐츠 생성")
    log.info("━" * 40)

    from generators.content_engine import generate_all_content, validate_and_regenerate

    batch = await generate_all_content(trend_report, checklist, config)

    if config.enable_qa_validation:
        log.info("\n  🔍 QA 검증 시작...")
        batch = await validate_and_regenerate(batch, config)

    return batch


async def step_save(config, trend_report=None, regulation_reports=None, batch=None):
    """Step 4: 로컬 DB 저장 + GDT 피드백 주입."""
    log.info("\n" + "━" * 40)
    log.info("[SAVE] STEP 4")
    log.info("━" * 40)

    from storage.local_db import get_connection, save_contents, save_regulations, save_trends

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

    # GDT 피드백: CIE QA 점수를 GetDayTrends content_feedback 테이블로 전달
    if batch and batch.contents:
        from collectors.gdt_bridge import write_content_feedback_batch

        feedback_items = []
        for c in batch.contents:
            if c.qa_report is None:
                continue
            # 트렌드 키워드별로 각각 피드백 주입 (없으면 제목/플랫폼으로 대체)
            keywords = c.trend_keywords_used or ([c.title] if c.title else [c.platform])
            regenerated = c.qa_report.total_score < config.qa_min_score
            reason = "; ".join(c.qa_report.warnings[:2]) if c.qa_report.warnings else ""
            for kw in keywords[:3]:
                feedback_items.append(
                    {
                        "keyword": kw,
                        "category": c.platform,
                        "qa_score": float(c.qa_report.total_score),
                        "regenerated": regenerated,
                        "reason": reason,
                    }
                )

        write_content_feedback_batch(config, feedback_items)


async def _step_predict_engagement(batch, trend_report, config) -> None:
    """Step 3.5: PEE로 각 콘텐츠 예상 성과를 예측하고 metadata에 기록."""
    try:
        from shared.prediction import PredictionEngine

        workspace = Path(__file__).resolve().parents[2]
        engine = PredictionEngine(
            gdt_db=workspace / "automation" / "getdaytrends" / "data" / "getdaytrends.db",
            cie_db=workspace / "automation" / "content-intelligence" / "data" / "cie.db",
            dn_db=workspace / "automation" / "DailyNews" / "data" / "pipeline_state.db",
            model_dir=workspace / "var" / "models" / "prediction",
        )
        await engine.initialize()

        annotated = 0
        for content in batch.contents:
            qa_scores = {}
            if content.qa_report:
                qa_scores = {"total": content.qa_report.total_score}
            keyword = (content.trend_keywords_used or [""])[0] if content.trend_keywords_used else content.title or ""
            if not keyword:
                continue

            result = await engine.predict(
                content=content.body[:500] if content.body else "",
                trend_keyword=keyword,
                qa_scores=qa_scores,
                category=content.platform or "other",
                content_type=content.content_type or "tweet",
            )
            # dict metadata로 저장 (모든 객체에 ad-hoc 속성 방식)
            if not hasattr(content, "pee_prediction"):
                content.pee_prediction = {}
            content.pee_prediction = {
                "predicted_er": result.predicted_engagement_rate,
                "predicted_impressions": result.predicted_impressions,
                "viral_probability": result.viral_probability,
                "optimal_hours": result.optimal_hours,
                "risk_level": result.risk_level,
            }
            annotated += 1

        if annotated:
            log.info(f"  🎯 [PEE] {annotated}건 성과 예측 완료")
    except ImportError:
        pass  # PEE 미설치 시 skip
    except Exception as e:
        log.debug(f"  [PEE] 예측 실패 (무시): {type(e).__name__}: {e}")


async def step_publish(config: CIEConfig, batch):
    """Step 5: 콘텐츠 발행 (Notion + X)."""
    log.info("\n" + "━" * 40)
    log.info("🚀 STEP 5: 발행")
    log.info("━" * 40)

    all_results = []

    # Notion 발행
    if config.can_publish_notion:
        from storage.notion_publisher import publish_batch_to_notion

        notion_results = await publish_batch_to_notion(batch, config)
        all_results.extend(notion_results)
        success = sum(1 for r in notion_results if r.success)
        log.info(f"  📝 Notion: {success}/{len(notion_results)} 발행 성공")
    else:
        log.info("  📝 Notion 발행: 비활성 (CIE_NOTION_PUBLISH=true 필요)")

    # X 발행
    if config.can_publish_x:
        from storage.x_publisher import publish_batch_to_x

        x_results = await publish_batch_to_x(batch, config)
        all_results.extend(x_results)
        success = sum(1 for r in x_results if r.success)
        log.info(f"  🐦 X: {success}/{len(x_results)} 발행 성공")
    else:
        log.info("  🐦 X 발행: 비활성 (CIE_X_PUBLISH=true 필요)")

    batch.publish_results = all_results
    return all_results


async def step_publish_only(config: CIEConfig):
    """미발행 콘텐츠를 DB에서 읽어 발행한다."""
    log.info("\n" + "━" * 40)
    log.info("🚀 미발행 콘텐츠 발행")
    log.info("━" * 40)

    from storage.local_db import get_connection, load_unpublished_contents

    conn = get_connection(config)
    try:
        contents = load_unpublished_contents(conn, min_qa_score=config.qa_min_score)
        if not contents:
            log.info("  📭 발행할 미발행 콘텐츠가 없습니다.")
            return

        log.info(f"  📬 미발행 콘텐츠 {len(contents)}건 발견")

        from storage.models import ContentBatch

        batch = ContentBatch(contents=contents)
        await step_publish(config, batch)
    finally:
        conn.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main Pipeline
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def run_pipeline(
    config: CIEConfig,
    mode: str = "full",
    publish: bool = False,
) -> None:
    """CIE 메인 파이프라인"""
    start = datetime.now()

    # [Observability] Notifier 초기화 — [QA 수정] from_env()로 환경변수 로드
    try:
        from shared.notifications import Notifier
        notifier = Notifier.from_env()
    except Exception:
        notifier = None

    try:
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

            log.info("\n📊 월간 리뷰 결과:")
            for s in review.next_month_strategy:
                log.info(f"  📌 {s}")
            for imp in review.system_improvements:
                log.info(f"  🔧 {imp}")

        elif mode == "publish-only":
            await step_publish_only(config)

        else:  # full
            # Step 1
            trend_report = await step_collect_trends(config)
            if trend_report.publish_blocked and not _has_trend_quorum(trend_report):
                await step_save(config, trend_report=trend_report)
                log.error(
                    f"[pipeline halted] trend quorum missed: {len(trend_report.platform_reports)}/"
                    f"{max(len(config.platforms), 1)} platforms collected "
                    f"(required={trend_report.quorum_required})"
                )
                elapsed = (datetime.now() - start).total_seconds()
                log.info(f"\nElapsed time: {elapsed:.1f}s")
                if notifier:  # [QA 수정] sync 메서드 — await 제거
                    notifier.send(f"⚠️ *CIE Pipeline* 중단: Trend quorum missed (모드: {mode})\n⏱ 소요시간: {int(elapsed)}초")
                return

            # Step 1.5: AI Convergence Guard v3
            from regulators.ai_convergence_guard_v3 import apply_ai_convergence_guard_v3

            ai_guard = apply_ai_convergence_guard_v3(trend_report)
            log.info(f"  {ai_guard.summary()}")
            if ai_guard.convergence_signal:
                log.info(f"    boosted: {', '.join(ai_guard.boosted_keywords[:5])}")
                if ai_guard.cross_platform_hits:
                    log.info(f"    cross-platform: {', '.join(ai_guard.cross_platform_hits[:5])}")
                if ai_guard.topic_clusters:
                    for cl in ai_guard.topic_clusters[:3]:
                        log.info(f"    cluster [{cl.name}]: {', '.join(cl.keywords[:3])} ({cl.phase.value})")

            # Step 2
            reports, checklist = await step_check_regulations(config)

            # Step 3
            batch = await step_generate_content(config, trend_report, checklist)

            # Step 3.5: PEE 성과 예측 (optional)
            await _step_predict_engagement(batch, trend_report, config)

            # Step 4
            await step_save(config, trend_report, reports, batch)

            # Step 5 (발행은 --publish 플래그 필요)
            if publish and trend_report.publish_blocked:
                log.warning(
                    f"[publish skipped] degraded trend collection; failed platforms: "
                    f"{', '.join(trend_report.failed_platforms) or 'unknown'}"
                )
            elif publish:
                await step_publish(config, batch)

            # 결과 요약
            log.info("\n" + "=" * 55)
            log.info("  📊 파이프라인 결과 요약")
            log.info("=" * 55)
            log.info(f"  {batch.summary()}")
            for c in batch.contents:
                qa_str = c.qa_report.to_emoji_report() if c.qa_report else "(미검증)"
                pub_str = f" | 발행: {c.publish_target}" if c.is_published else ""
                pee_str = ""
                pee = getattr(c, "pee_prediction", None)
                if pee:
                    pee_str = f" | PEE: ER={pee['predicted_er']:.2%} 바이럴={pee['viral_probability']:.0%}"
                log.info(f"  [{c.platform.upper()}/{c.content_type}] {qa_str}{pub_str}{pee_str}")
                if c.body:
                    preview = c.body[:100].replace("\n", " ") + "..."
                    log.info(f"    📄 {preview}")

        elapsed = (datetime.now() - start).total_seconds()
        log.info(f"\nElapsed time: {elapsed:.1f}s")

        if notifier:  # [QA 수정] sync 메서드 — await 제거
            notifier.send_heartbeat(
                "CIE-Pipeline",
                details=f"모드: {mode}, 소요시간: {int(elapsed)}초",
            )

    except Exception as e:
        log.error(f"[CIE Pipeline Error] {e}")
        import traceback
        if notifier:  # [QA 수정] send_alert → send_error (정식 API), await 제거
            try:
                notifier.send_error(
                    f"CIE Pipeline Critical Failure (모드: {mode})\n{traceback.format_exc()[:1000]}",
                    error=e,
                    source="CIE-Pipeline",
                )
            except Exception as notify_err:
                log.error(f"[Notification Error] {notify_err}")
        sys.exit(1)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Entry Point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def main() -> None:
    # Windows stdout UTF-8 설정
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = parse_args()
    setup_logging(args.verbose)
    config = CIEConfig()
    print_banner(config, args.mode, args.publish)

    if not args.dry_run:
        config.validate()

    if args.dry_run:
        log.info("🧪 DRY RUN 모드 — LLM 호출 없이 구조 검증만 실행")
        log.info("  Config loaded: OK")
        log.info(f"  Platforms: {config.platforms}")
        log.info(f"  DB path: {config.sqlite_path}")
        log.info(f"  Notion configured: {bool(config.notion_database_id)}")
        log.info("  Notion publish: ON" if config.can_publish_notion else "  Notion publish: OFF")
        log.info("  X publish: ON" if config.can_publish_x else "  X publish: OFF")

        # GDT Bridge 확인
        from collectors.gdt_bridge import _find_gdt_db

        gdt_path = _find_gdt_db(config)
        log.info(f"  GDT DB: {gdt_path}") if gdt_path else log.info("  GDT DB: not found")

        from storage.local_db import ensure_schema, get_connection

        conn = get_connection(config)
        ensure_schema(conn)
        conn.close()
        log.info("  DB schema: OK")
        log.info("DRY RUN complete: structure looks healthy")
        return

    asyncio.run(run_pipeline(config, args.mode, args.publish))


if __name__ == "__main__":
    main()
