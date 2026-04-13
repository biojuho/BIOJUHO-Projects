"""
=======================================================
  Content Intelligence Engine (CIE) v2.0
  ?몃젋??& ?뚮옯??洹쒖젣 諛섏쁺 肄섑뀗痢?李쎌옉 + ?먮룞 諛쒗뻾 ?쒖뒪??

  5?④퀎 ?뚯씠?꾨씪??
    1?④퀎: ?몃젋???섏쭛 (GDT Bridge + X, Threads, ?ㅼ씠踰?
    2?④퀎: ?뚮옯??洹쒖젣 & ?뚭퀬由ъ쬁 ?먭?
    3?④퀎: 肄섑뀗痢??앹꽦 / 理쒖쟻??/ QA 寃利?
    4?④퀎: 濡쒖뺄 DB ???
    5?④퀎: 諛쒗뻾 (Notion + X)
    蹂대꼫?? ?붽컙 ?뚭퀬 & ?쒖뒪???낅뜲?댄듃

  Usage:
    python main.py --mode full              # ?꾩껜 ?뚯씠?꾨씪??(諛쒗뻾 ?쒖쇅)
    python main.py --mode full --publish    # ?꾩껜 + Notion/X 諛쒗뻾
    python main.py --mode trend             # ?몃젋???섏쭛留?
    python main.py --mode regulation        # 洹쒖젣 ?먭?留?
    python main.py --mode review            # ?붽컙 ?뚭퀬
    python main.py --mode publish-only      # 誘몃컻??肄섑뀗痢?諛쒗뻾
    python main.py --dry-run                # LLM ?몄텧 ?놁씠 援ъ“ 寃利?
=======================================================
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# ?? PYTHONPATH ?ㅼ젙 ??
_CIE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CIE_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_CIE_DIR) not in sys.path:
    sys.path.insert(0, str(_CIE_DIR))

from config import CIEConfig
from loguru import logger as log
from storage.models import MergedTrendReport

# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧
#  CLI
# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Content Intelligence Engine v2.0 trend-aware content generation pipeline",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "trend", "regulation", "review", "publish-only"],
        default="full",
        help="?ㅽ뻾 紐⑤뱶 (湲곕낯: full)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate structure without live LLM calls")
    parser.add_argument("--publish", action="store_true", help="肄섑뀗痢??먮룞 諛쒗뻾 (Notion + X)")
    parser.add_argument("--verbose", action="store_true", help="?곸꽭 濡쒓렇")
    return parser.parse_args()


# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧
#  Logging
# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧


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


# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧
#  Banner
# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧


def print_banner(config: CIEConfig, mode: str, publish: bool) -> None:
    log.info("=" * 55)
    log.info("  Content Intelligence Engine (CIE) v2.0")
    log.info("  ?몃젋??& ?뚮옯??洹쒖젣 諛섏쁺 肄섑뀗痢?李쎌옉 + 諛쒗뻾")
    log.info("=" * 55)
    log.info(f"  紐⑤뱶: {mode.upper()}" + (" + 諛쒗뻾" if publish else ""))
    log.info(config.summary())
    log.info("=" * 55)


# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧
#  Pipeline Steps
# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧


def _trend_quorum_required(platform_count: int) -> int:
    if platform_count <= 0:
        return 0
    if platform_count == 1:
        return 1
    return 2


def _has_trend_quorum(report: MergedTrendReport) -> bool:
    return len(report.platform_reports) >= report.quorum_required


async def step_collect_trends(config: CIEConfig) -> MergedTrendReport:
    """Step 1: 硫?고뵆?ロ뤌 ?몃젋???섏쭛 (蹂묐젹)."""
    log.info("\n" + "?" * 40)
    log.info("?뱻 STEP 1: ?몃젋???섏쭛")
    log.info("?" * 40)

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
            log.warning(f"  ?좑툘 ?????녿뒗 ?뚮옯?? {platform}")

    reports = await asyncio.gather(*tasks, return_exceptions=True)

    valid_reports = []
    for r in reports:
        if isinstance(r, BaseException):
            log.error(f"  ???섏쭛 ?ㅽ뙣: {r}")
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

    if not valid_reports:
        log.error("  ?슟 紐⑤뱺 ?몃젋???섏쭛湲??ㅽ뙣 ??鍮??곗씠?곕줈 肄섑뀗痢??앹꽦 遺덇?, ?뚯씠?꾨씪??以묐떒")
        return MergedTrendReport(platform_reports=[], cross_platform_keywords=[], top_insights=[])

    # 援먯감 ?뚮옯???ㅼ썙???앸퀎
    all_keywords: dict[str, int] = {}
    for report in valid_reports:
        for t in report.trends:
            kw = t.keyword.lower()
            all_keywords[kw] = all_keywords.get(kw, 0) + 1

    cross_platform = [k for k, v in all_keywords.items() if v >= 2]

    # ?몄궗?댄듃 ?듯빀
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
        log.info(f"  ?뵕 援먯감 ?뚮옯???ㅼ썙?? {', '.join(cross_platform)}")

    if degraded:
        log.warning(f"  [degraded] failed platforms: {', '.join(failed_platforms)}")
    if publish_blocked:
        log.warning(
            f"  [publish blocked] collected {len(valid_reports)}/{len(declared_platforms)} platforms "
            f"(quorum={quorum_required})"
        )

    return merged


async def step_check_regulations(config: CIEConfig):
    """Step 2: ?뚮옯??洹쒖젣 & ?뚭퀬由ъ쬁 ?먭?."""
    log.info("\n" + "?" * 40)
    log.info("?뵇 STEP 2: 洹쒖젣 ?먭?")
    log.info("?" * 40)

    from regulators.checklist import check_all_regulations, generate_unified_checklist

    reports = await check_all_regulations(config)
    checklist = generate_unified_checklist(reports)

    return reports, checklist


async def step_generate_content(config, trend_report, checklist):
    """Step 3: 肄섑뀗痢??앹꽦 + QA 寃利?"""
    log.info("\n" + "?" * 40)
    log.info("?랃툘 STEP 3: 肄섑뀗痢??앹꽦")
    log.info("?" * 40)

    from generators.content_engine import generate_all_content, validate_and_regenerate

    batch = await generate_all_content(trend_report, checklist, config)

    if config.enable_qa_validation:
        log.info("\n  ?뵮 QA 寃利??쒖옉...")
        batch = await validate_and_regenerate(batch, config)

    return batch


async def step_save(config, trend_report=None, regulation_reports=None, batch=None):
    """Step 4: 濡쒖뺄 DB ???+ GDT ??뵾?쒕갚 二쇱엯."""
    log.info("\n" + "?" * 40)
    log.info("[SAVE] STEP 4")
    log.info("?" * 40)

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

    # GDT ??뵾?쒕갚: CIE QA ?먯닔 ??GetDayTrends content_feedback ?뚯씠釉?
    if batch and batch.contents:
        from collectors.gdt_bridge import write_content_feedback_batch

        feedback_items = []
        for c in batch.contents:
            if c.qa_report is None:
                continue
            # ?몃젋???ㅼ썙?쒕퀎濡?媛곴컖 ?쇰뱶諛?二쇱엯 (?놁쑝硫??쒕ぉ/?뚮옯?쇱쑝濡??泥?
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
    """Step 3.5: PEE濡?媛?肄섑뀗痢??덉긽 ?깃낵瑜??덉륫?섍퀬 metadata??湲곕줉."""
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
            # dict metadata?????(紐⑤뜽 媛앹껜??ad-hoc ?띿꽦 諛⑹?)
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
            log.info(f"  ?뵰 [PEE] {annotated}嫄??깃낵 ?덉륫 ?꾨즺")
    except ImportError:
        pass  # PEE 誘몄꽕移???skip
    except Exception as e:
        log.debug(f"  [PEE] ?덉륫 ?ㅽ뙣 (臾댁떆): {type(e).__name__}: {e}")


async def step_publish(config: CIEConfig, batch):
    """Step 5: 肄섑뀗痢?諛쒗뻾 (Notion + X)."""
    log.info("\n" + "?" * 40)
    log.info("?? STEP 5: 諛쒗뻾")
    log.info("?" * 40)

    all_results = []

    # Notion 諛쒗뻾
    if config.can_publish_notion:
        from storage.notion_publisher import publish_batch_to_notion

        notion_results = await publish_batch_to_notion(batch, config)
        all_results.extend(notion_results)
        success = sum(1 for r in notion_results if r.success)
        log.info(f"  ?뱬 Notion: {success}/{len(notion_results)} 諛쒗뻾 ?깃났")
    else:
        log.info("  ?뱬 Notion 諛쒗뻾: 鍮꾪솢??(CIE_NOTION_PUBLISH=true ?꾩슂)")

    # X 諛쒗뻾
    if config.can_publish_x:
        from storage.x_publisher import publish_batch_to_x

        x_results = await publish_batch_to_x(batch, config)
        all_results.extend(x_results)
        success = sum(1 for r in x_results if r.success)
        log.info(f"  ?맔 X: {success}/{len(x_results)} 諛쒗뻾 ?깃났")
    else:
        log.info("  ?맔 X 諛쒗뻾: 鍮꾪솢??(CIE_X_PUBLISH=true ?꾩슂)")

    batch.publish_results = all_results
    return all_results


async def step_publish_only(config: CIEConfig):
    """誘몃컻??肄섑뀗痢좊? DB?먯꽌 ?쎌뼱 諛쒗뻾?쒕떎."""
    log.info("\n" + "?" * 40)
    log.info("?? 誘몃컻??肄섑뀗痢?諛쒗뻾")
    log.info("?" * 40)

    from storage.local_db import get_connection, load_unpublished_contents

    conn = get_connection(config)
    try:
        contents = load_unpublished_contents(conn, min_qa_score=config.qa_min_score)
        if not contents:
            log.info("  ?뱄툘 諛쒗뻾??誘몃컻??肄섑뀗痢좉? ?놁뒿?덈떎.")
            return

        log.info(f"  ?벀 誘몃컻??肄섑뀗痢?{len(contents)}嫄?諛쒓껄")

        from storage.models import ContentBatch

        batch = ContentBatch(contents=contents)
        await step_publish(config, batch)
    finally:
        conn.close()


# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧
#  Main Pipeline
# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧


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
            log.info(f"\n?뱥 泥댄겕由ъ뒪??\n{checklist.to_checklist_text()}")

        elif mode == "review":
            from review.monthly_review import run_monthly_review
            from storage.local_db import get_connection, save_review

            review = await run_monthly_review(config)
            conn = get_connection(config)
            try:
                save_review(conn, review)
            finally:
                conn.close()

            log.info("\n?뱤 ?붽컙 ?뚭퀬 寃곌낵:")
            for s in review.next_month_strategy:
                log.info(f"  ?뱦 {s}")
            for imp in review.system_improvements:
                log.info(f"  ?뵩 {imp}")

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

            # Step 2
            reports, checklist = await step_check_regulations(config)

            # Step 3
            batch = await step_generate_content(config, trend_report, checklist)

            # Step 3.5: PEE ?깃낵 ?덉륫 (optional)
            await _step_predict_engagement(batch, trend_report, config)

            # Step 4
            await step_save(config, trend_report, reports, batch)

            # Step 5 (諛쒗뻾 ??--publish ?뚮옒洹??꾩슂)
            if publish and trend_report.publish_blocked:
                log.warning(
                    f"[publish skipped] degraded trend collection; failed platforms: "
                    f"{', '.join(trend_report.failed_platforms) or 'unknown'}"
                )
            elif publish:
                await step_publish(config, batch)

            # 寃곌낵 ?붿빟
            log.info("\n" + "=" * 55)
            log.info("  ?벀 ?뚯씠?꾨씪??寃곌낵 ?붿빟")
            log.info("=" * 55)
            log.info(f"  {batch.summary()}")
            for c in batch.contents:
                qa_str = c.qa_report.to_emoji_report() if c.qa_report else "(誘멸?利?"
                pub_str = f" | 諛쒗뻾: {c.publish_target}" if c.is_published else ""
                pee_str = ""
                pee = getattr(c, "pee_prediction", None)
                if pee:
                    pee_str = f" | PEE: ER={pee['predicted_er']:.2%} 諛붿씠??{pee['viral_probability']:.0%}"
                log.info(f"  [{c.platform.upper()}/{c.content_type}] {qa_str}{pub_str}{pee_str}")
                if c.body:
                    preview = c.body[:100].replace("\n", " ") + "..."
                    log.info(f"    ?뱷 {preview}")

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


# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧
#  Entry Point
# ?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧?먥븧


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)
    config = CIEConfig()
    print_banner(config, args.mode, args.publish)

    if not args.dry_run:
        config.validate()

    if args.dry_run:
        log.info("?㎦ DRY RUN 紐⑤뱶 ??LLM ?몄텧 ?놁씠 援ъ“ 寃利앸쭔 ?섑뻾")
        log.info("  Config loaded: OK")
        log.info(f"  Platforms: {config.platforms}")
        log.info(f"  DB path: {config.sqlite_path}")
        log.info(f"  Notion configured: {bool(config.notion_database_id)}")
        log.info("  Notion publish: ON" if config.can_publish_notion else "  Notion publish: OFF")
        log.info("  X publish: ON" if config.can_publish_x else "  X publish: OFF")

        # GDT Bridge ?뺤씤
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
