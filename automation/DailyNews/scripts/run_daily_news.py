from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from dateutil import parser as date_parser
from notion_client import AsyncClient
from runtime import (
    AlreadyRunningError,
    JobLock,
    PipelineStateStore,
    configure_stdout_utf8,
    create_notion_page_with_retry,
    fetch_feed_entries,
    generate_run_id,
    get_logger,
    run_with_timeout,
)
from settings import NEWS_SOURCES_FILE, NOTION_API_KEY, NOTION_REPORTS_DATABASE_ID, OUTPUT_DIR


def _print_manifest(summary: dict, status: str, run_id: str | None) -> None:
    """Print a JSON manifest to stdout for workflow-level heartbeat integration."""
    manifest = {
        "pipeline": "DailyNews",
        "run_id": run_id or "unknown",
        "status": status,
        "published_categories": summary.get("categories_success", 0),
        "failed_categories": summary.get("categories_failed", 0),
        "skipped_categories": summary.get("categories_skipped", 0),
        "total_articles": summary.get("articles", 0),
        "window": summary.get("window", "unknown"),
        "target_db": NOTION_REPORTS_DATABASE_ID or "unset",
    }
    print(f"\n::manifest::{json.dumps(manifest, ensure_ascii=False)}")


def get_extraction_window(force: bool) -> tuple[datetime, datetime, str]:
    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST).replace(tzinfo=None)  # naive KST
    hour = now_kst.hour
    if force:
        return now_kst - timedelta(hours=24), now_kst, "test"
    # Widened to absorb GHA cron drift — schedules fire at 07/18 KST but can
    # queue up to several hours late. The 2026-04-13 evening run fired at
    # 19:49 KST (1h49m late) and was rejected as "outside extraction window",
    # so the whole brief was skipped. Accept anything up to ~6h after the
    # scheduled slot and still classify it correctly.
    if 6 <= hour < 13:
        start = now_kst.replace(hour=18, minute=0, second=0, microsecond=0) - timedelta(days=1)
        end = now_kst.replace(hour=7, minute=0, second=0, microsecond=0)
        return start, end, "morning"
    if 17 <= hour < 24:
        start = now_kst.replace(hour=7, minute=0, second=0, microsecond=0)
        end = now_kst.replace(hour=18, minute=0, second=0, microsecond=0)
        return start, end, "evening"
    raise RuntimeError("outside extraction window; use --force to override")


def is_within_window(published_time: Any, start: datetime, end: datetime) -> bool:
    if not published_time:
        return True
    try:
        if isinstance(published_time, str):
            published_dt = date_parser.parse(published_time)
        else:
            published_dt = datetime(*published_time[:6])
        if published_dt.tzinfo:
            published_dt = published_dt.replace(tzinfo=None)
        return start <= published_dt <= end
    except Exception:
        return True


def load_news_sources() -> dict[str, list[dict[str, str]]]:
    with NEWS_SOURCES_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


from antigravity_mcp.domain.category_filter import is_relevant_to_category as _is_relevant_to_category


def normalize_analysis(analysis: dict[str, Any]) -> tuple[list[str], str, list[str]]:
    summary = [str(item) for item in analysis.get("summary", []) if item]
    insights = analysis.get("insights") or []
    insight_lines = []
    for insight in insights[:3]:
        topic = insight.get("topic", "Topic")
        detail = insight.get("insight", "")
        importance = insight.get("importance", "")
        insight_lines.append(f"[{topic}] {detail}".strip() + (f" ({importance})" if importance else ""))

    if analysis.get("insight"):
        insight_text = str(analysis["insight"])
    else:
        insight_text = "\n".join(insight_lines)

    if analysis.get("x_post"):
        x_posts = [str(analysis["x_post"])]
    else:
        x_posts = [str(item) for item in analysis.get("x_thread", []) if item]

    return summary, insight_text, x_posts


async def resolve_title_property(notion: AsyncClient, database_id: str) -> str:
    """Find the title-typed property name on a Notion DB.

    Why: The new Notion API routes schema through data sources, and the title
    column is no longer guaranteed to be called "Name". A previous outage
    burned six categories when DAILYNEWS_NOTION_REPORTS_DB_ID pointed to a DB
    whose title property had a different name.
    """
    try:
        db = await notion.databases.retrieve(database_id=database_id)
    except Exception:
        return "Name"
    props = db.get("properties") or {}
    for name, spec in props.items():
        if isinstance(spec, dict) and spec.get("type") == "title":
            return name
    for ds in db.get("data_sources") or []:
        ds_id = ds.get("id")
        if not ds_id:
            continue
        try:
            ds_obj = await notion.data_sources.retrieve(data_source_id=ds_id)
        except Exception:
            continue
        for name, spec in (ds_obj.get("properties") or {}).items():
            if isinstance(spec, dict) and spec.get("type") == "title":
                return name
    return "Name"


async def upload_to_notion(
    *,
    category: str,
    analysis: dict[str, Any],
    notion: AsyncClient,
    logger,
    today_str: str,
    title_property: str = "Name",
    canva_result: dict | None = None,
    nlm_result: dict | None = None,
) -> dict[str, Any]:
    summary, insight_text, x_posts = normalize_analysis(analysis)
    description = "[Summary]\n" + "\n".join(summary[:3])
    if insight_text:
        description += f"\n\n[Insight]\n{insight_text}"

    children: list[dict[str, Any]] = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": "3-Line Summary"}}]},
        }
    ]

    if canva_result and canva_result.get("edit_url"):
        children.insert(
            0,
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"emoji": "🎨"},
                    "color": "purple_background",
                    "rich_text": [
                        {"type": "text", "text": {"content": "Canva 인포그래픽: "}, "annotations": {"bold": True}},
                        {
                            "type": "text",
                            "text": {"content": "Canva에서 편집하기", "link": {"url": canva_result["edit_url"]}},
                        },
                    ],
                },
            },
        )

    for item in summary:
        children.append(
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"text": {"content": item}}]},
            }
        )

    children.extend(
        [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "Insight"}}]},
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": insight_text or "No insight available"}}]},
            },
        ]
    )

    if x_posts:
        children.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "X Draft"}}]},
            }
        )
        children.append(
            {
                "object": "block",
                "type": "code",
                "code": {
                    "language": "plain text",
                    "rich_text": [{"text": {"content": "\n\n".join(x_posts)}}],
                },
            }
        )

    # [v3.0] NotebookLM Deep Research section
    if nlm_result and nlm_result.get("notebook_id"):
        children.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "Deep Research (NotebookLM)"}}]},
            }
        )
        nlm_notebook_id = nlm_result["notebook_id"]
        nlm_url = f"https://notebooklm.google.com/notebook/{nlm_notebook_id}"
        children.append(
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"emoji": "\U0001f9e0"},
                    "color": "blue_background",
                    "rich_text": [
                        {"type": "text", "text": {"content": "NotebookLM: "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "Open Notebook", "link": {"url": nlm_url}}},
                        {"type": "text", "text": {"content": f" ({nlm_result.get('source_count', 0)} sources)"}},
                    ],
                },
            }
        )
        # Deep summary
        deep_summary = nlm_result.get("deep_summary", "")
        if deep_summary:
            children.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": deep_summary[:2000]}}]},
                }
            )
        # Research insights as toggle blocks
        for idx, ri in enumerate(nlm_result.get("research_insights", [])[:3], 1):
            children.append(
                {
                    "object": "block",
                    "type": "toggle",
                    "toggle": {
                        "rich_text": [{"text": {"content": f"Research Insight #{idx}"}}],
                        "children": [
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {"rich_text": [{"text": {"content": ri[:2000]}}]},
                            }
                        ],
                    },
                }
            )

    return await create_notion_page_with_retry(
        notion_client=notion,
        parent={"database_id": NOTION_REPORTS_DATABASE_ID},
        properties={
            title_property: {"title": [{"text": {"content": f"[{category}] Daily Report - {today_str}"}}]},
        },
        children=children,
        logger=logger,
        step=f"upload:{category}",
    )


async def process_category(
    *,
    category: str,
    sources: list[dict[str, str]],
    start: datetime,
    end: datetime,
    max_items: int,
    notion: AsyncClient,
    brain: Any,
    canva: Any = None,
    notebooklm: Any = None,
    logger,
    today_str: str,
    window_name: str,
    title_property: str = "Name",
) -> dict[str, Any]:
    all_articles: list[dict[str, Any]] = []
    seen_links: set[str] = set()

    for source in sources:
        source_name = source["name"]
        source_url = source["url"]
        logger.info("fetch", "start", "fetching source", category=category, source=source_name, url=source_url)
        try:
            entries = await fetch_feed_entries(source_url)
        except Exception as exc:
            logger.error(
                "fetch", "failed", "source fetch failed", category=category, source=source_name, error=str(exc)
            )
            continue

        for entry in entries:
            published = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            if not is_within_window(published, start, end):
                continue

            link = getattr(entry, "link", "")
            if not link or link in seen_links:
                continue

            entry_title = getattr(entry, "title", "Untitled")
            entry_desc = (getattr(entry, "description", "") or getattr(entry, "summary", ""))[:300]
            if not _is_relevant_to_category(entry_title, entry_desc, category):
                continue

            article = {
                "title": entry_title,
                "description": entry_desc,
                "link": link,
                "published": published,
            }
            seen_links.add(link)
            all_articles.append(article)
            if len(all_articles) >= max_items:
                break

        logger.info(
            "fetch",
            "success",
            "source processed",
            category=category,
            source=source_name,
            found=len(all_articles),
        )

    if not all_articles:
        logger.warning("category", "skipped", "no articles in time window", category=category)
        return {"category": category, "status": "skipped", "articles": 0}

    # [v2.0] Gemini Embedding 2 기반 의미적 중복 제거
    if len(all_articles) > 1:
        try:
            from shared.embeddings import deduplicate_texts

            titles = [a["title"] for a in all_articles]
            unique_indices = deduplicate_texts(titles, threshold=0.82)
            removed = len(all_articles) - len(unique_indices)
            if removed:
                all_articles = [all_articles[i] for i in unique_indices]
                logger.info(
                    "dedup",
                    "success",
                    "semantic dedup applied",
                    category=category,
                    removed=removed,
                    remaining=len(all_articles),
                )
        except Exception as exc:
            logger.debug("dedup", "skipped", "embedding dedup unavailable", error=str(exc))

    if brain is None:
        logger.warning("analysis", "skipped", "brain module unavailable", category=category)
        return {"category": category, "status": "skipped", "articles": len(all_articles)}

    try:
        # Prefer native async path so the shared LLM client stays bound to the
        # main event loop across categories. Fall back to the sync bridge only
        # for legacy BrainModule implementations without analyze_news_async.
        _brain_async = getattr(brain, "analyze_news_async", None)
        if _brain_async is not None:
            analysis_coro = _brain_async(category, all_articles[:max_items])
        else:
            analysis_coro = asyncio.to_thread(
                brain.analyze_news, category, all_articles[:max_items]
            )
        analysis = await run_with_timeout(analysis_coro, 60)
    except Exception as exc:
        logger.error("analysis", "failed", "analysis failed", category=category, error=str(exc))
        return {"category": category, "status": "failed", "articles": len(all_articles), "error": str(exc)}

    if not analysis:
        logger.warning("analysis", "skipped", "analysis returned no result", category=category)
        return {"category": category, "status": "skipped", "articles": len(all_articles)}

    # [v3.0] NotebookLM deep research — enrich analysis with cross-source insights
    nlm_result = None
    if notebooklm is not None and all_articles:
        try:
            articles_for_nlm = [
                {"title": a["title"], "description": a.get("description", ""), "link": a["link"]}
                for a in all_articles[:max_items]
            ]
            extra_ctx = ""
            if analysis:
                _, insight_text, _ = normalize_analysis(analysis)
                extra_ctx = insight_text
            nlm_result = await run_with_timeout(
                notebooklm.research_category(
                    category=category,
                    articles=articles_for_nlm,
                    extra_context=extra_ctx,
                ),
                120,
            )
            if nlm_result:
                logger.info(
                    "notebooklm",
                    "success",
                    "deep research complete",
                    category=category,
                    notebook_id=nlm_result.get("notebook_id", "")[:8],
                    insights=len(nlm_result.get("research_insights", [])),
                )
                # Merge deep insights into analysis
                if analysis and nlm_result.get("research_insights"):
                    existing_insights = analysis.get("insights") or []
                    for ri in nlm_result["research_insights"][:2]:
                        existing_insights.append(
                            {
                                "topic": "Deep Research",
                                "insight": ri[:300],
                                "importance": "NotebookLM",
                            }
                        )
                    analysis["insights"] = existing_insights
        except Exception as exc:
            logger.warning("notebooklm", "failed", "deep research failed", category=category, error=str(exc))

    await asyncio.sleep(3)

    image_path = OUTPUT_DIR / f"infographic_{category}_{date.today()}_{window_name}.png"
    try:
        from generate_infographic import create_news_card

        summary, insight_text, _ = normalize_analysis(analysis)
        await run_with_timeout(
            asyncio.to_thread(
                create_news_card,
                category=category,
                summary=summary,
                insight=insight_text,
                output_path=str(image_path),
            ),
            30,
        )
        logger.info("image", "success", "infographic created", category=category, path=image_path)
    except Exception as exc:
        logger.warning("image", "failed", "infographic generation failed", category=category, error=str(exc))
        image_path = None

    # Canva: import the infographic as an editable Canva design
    canva_result = None
    if canva is not None and image_path and image_path.exists():
        try:
            title = f"[{category}] News {today_str}"
            canva_result = await run_with_timeout(
                canva.async_import_and_export(image_path=image_path, title=title),
                90,
            )
            if canva_result:
                logger.info(
                    "canva", "success", "design imported", category=category, design_id=canva_result.get("design_id")
                )
            else:
                logger.warning("canva", "skipped", "import returned no result", category=category)
        except Exception as exc:
            logger.warning("canva", "failed", "canva import failed", category=category, error=str(exc))

    try:
        await upload_to_notion(
            category=category,
            analysis=analysis,
            notion=notion,
            logger=logger,
            today_str=today_str,
            title_property=title_property,
            canva_result=canva_result,
            nlm_result=nlm_result,
        )
    except Exception as exc:
        return {"category": category, "status": "failed", "articles": len(all_articles), "error": str(exc)}

    _, _, x_posts = normalize_analysis(analysis)
    if x_posts:
        tweets_path = OUTPUT_DIR / f"daily_tweets_{date.today()}_{window_name}.txt"
        with tweets_path.open("a", encoding="utf-8") as handle:
            handle.write(f"=== {category} ===\n")
            handle.write("\n\n".join(x_posts))
            handle.write("\n\n")

    logger.info("category", "success", "category processed", category=category, articles=len(all_articles))
    return {"category": category, "status": "success", "articles": len(all_articles)}


async def run_daily_news(*, force: bool, max_items: int, run_id: str | None = None) -> int:
    configure_stdout_utf8()
    run_id = run_id or generate_run_id("run_daily_news")
    logger = get_logger("run_daily_news", run_id)
    state = PipelineStateStore()
    state.record_job_start(run_id, "run_daily_news")

    if not NOTION_API_KEY:
        logger.error("bootstrap", "failed", "NOTION_API_KEY missing")
        state.record_job_finish(run_id, status="failed", error_text="NOTION_API_KEY missing")
        return 1
    if not NOTION_REPORTS_DATABASE_ID:
        logger.error("bootstrap", "failed", "NOTION_REPORTS_DATABASE_ID missing")
        state.record_job_finish(run_id, status="failed", error_text="NOTION_REPORTS_DATABASE_ID missing")
        return 1

    try:
        start, end, window_name = get_extraction_window(force)
    except RuntimeError as exc:
        logger.warning("window", "skipped", str(exc))
        state.record_job_finish(run_id, status="skipped", error_text=str(exc))
        return 1

    try:
        from brain_module import BrainModule

        brain = BrainModule()
    except Exception as exc:
        brain = None
        logger.warning("bootstrap", "degraded", "brain module unavailable", error=str(exc))

    try:
        from settings import CANVA_CLIENT_ID, CANVA_REFRESH_TOKEN

        if CANVA_CLIENT_ID and CANVA_REFRESH_TOKEN:
            import canva_generator

            canva_generator.get_access_token()
            canva = canva_generator
            logger.info("bootstrap", "success", "canva generator initialized")
        else:
            canva = None
            logger.info("bootstrap", "skipped", "canva not configured")
    except Exception as exc:
        canva = None
        logger.warning("bootstrap", "degraded", "canva unavailable", error=str(exc))

    # [v3.0] NotebookLM deep research adapter
    notebooklm = None
    try:
        from antigravity_mcp.integrations.notebooklm_adapter import get_notebooklm_adapter

        _nlm = get_notebooklm_adapter()
        if _nlm.is_available:
            nlm_ok = await _nlm.check_availability()
            if nlm_ok:
                notebooklm = _nlm
                logger.info("bootstrap", "success", "notebooklm adapter initialized")
            else:
                logger.info("bootstrap", "skipped", "notebooklm auth failed")
        else:
            logger.info("bootstrap", "skipped", "notebooklm-py not installed")
    except Exception as exc:
        logger.warning("bootstrap", "degraded", "notebooklm unavailable", error=str(exc))

    notion = AsyncClient(auth=NOTION_API_KEY)
    # Use the END of the extraction window as the report date so the morning
    # brief that runs at 22:32 UTC (07:32 KST next day) is labeled with the
    # KST date the user actually sees, not the UTC server's calendar date.
    today_str = end.date().isoformat()
    title_property = await resolve_title_property(notion, NOTION_REPORTS_DATABASE_ID)
    if title_property != "Name":
        logger.info("bootstrap", "success", "resolved title property", title_property=title_property)
    summary: dict[str, Any] = {
        "window": window_name,
        "categories_success": 0,
        "categories_failed": 0,
        "categories_skipped": 0,
        "articles": 0,
    }

    try:
        with JobLock("run_daily_news", run_id):
            news_sources = load_news_sources()
            logger.info(
                "window",
                "start",
                "processing extraction window",
                start=start.isoformat(),
                end=end.isoformat(),
                window=window_name,
            )

            for category, sources in news_sources.items():
                try:
                    result = await process_category(
                        category=category,
                        sources=sources,
                        start=start,
                        end=end,
                        max_items=max_items,
                        notion=notion,
                        brain=brain,
                        canva=canva,
                        notebooklm=notebooklm,
                        logger=logger,
                        today_str=today_str,
                        window_name=window_name,
                        title_property=title_property,
                    )
                except Exception as exc:
                    logger.error("category", "failed", "unhandled category error", category=category, error=str(exc))
                    summary["categories_failed"] += 1
                    continue

                summary["articles"] += int(result.get("articles", 0))
                status = result.get("status")
                if status == "success":
                    summary["categories_success"] += 1
                elif status == "failed":
                    summary["categories_failed"] += 1
                else:
                    summary["categories_skipped"] += 1

            succ = summary["categories_success"]
            fail = summary["categories_failed"]
            skip = summary["categories_skipped"]
            total = succ + fail + skip

            # 어떤 카테고리라도 업로드 실패하면 명시적 failure로 마감한다.
            if fail > 0:
                status_name = "failed" if succ == 0 else "partial_failed"
                prefix = "[TOTAL-FAIL]" if succ == 0 else "[PARTIAL]"
                error_msg = (
                    f"{fail}/{total} categories failed to publish "
                    f"(success={succ}, skipped={skip})"
                )
                state.record_job_finish(
                    run_id, status=status_name, summary=summary, error_text=error_msg
                )
                logger.error(
                    "complete", "failed", "run_daily_news categories failed",
                    **summary,
                )
                _print_manifest(summary, status_name, run_id)
                try:
                    from shared.notifications import Notifier

                    _notifier = Notifier.from_env()
                    if _notifier.has_channels:
                        _notifier.send_error(
                            f"{prefix} DailyNews: "
                            f"성공 {succ} / 실패 {fail} / 스킵 {skip} "
                            f"(window={summary['window']}, 기사={summary['articles']})",
                            source="DailyNews",
                        )
                except Exception:
                    pass
                return 1

            # 0 success + 0 failed + N skipped는 success가 아니라 degraded.
            # 수집 단계가 모든 카테고리에서 0건을 반환한 경우 (피드 장애·필터 너무
            # 빡빡함·소스 URL 일괄 만료 등) 알림 없이 success heartbeat가 가면
            # 며칠씩 묵음 장애가 누적된다.
            if total > 0 and succ == 0 and skip == total:
                error_msg = (
                    f"{skip}/{total} categories skipped — zero articles "
                    f"in window {summary['window']}"
                )
                state.record_job_finish(
                    run_id, status="degraded", summary=summary, error_text=error_msg
                )
                logger.error(
                    "complete", "degraded",
                    "run_daily_news collected zero articles across all categories",
                    **summary,
                )
                _print_manifest(summary, "degraded", run_id)
                try:
                    from shared.notifications import Notifier

                    _notifier = Notifier.from_env()
                    if _notifier.has_channels:
                        _notifier.send_error(
                            f"[PRE-FAIL] DailyNews degraded: 전 카테고리({skip}) 수집 0건 "
                            f"(window={summary['window']})",
                            source="DailyNews",
                        )
                        _notifier.send_heartbeat(
                            "DailyNews",
                            status="degraded",
                            details=(
                                f"window={summary['window']} "
                                f"성공={succ} 실패={fail} 스킵={skip} 기사=0"
                            ),
                        )
                except Exception:
                    pass
                return 1

            state.record_job_finish(run_id, status="success", summary=summary)
            logger.info("complete", "success", "run_daily_news finished", **summary)
            _print_manifest(summary, "success", run_id)

            # [v2.0] Heartbeat: 파이프라인 성공 시 Discord/Telegram 알림
            try:
                from shared.notifications import Notifier

                _notifier = Notifier.from_env()
                if _notifier.has_channels:
                    _notifier.send_heartbeat(
                        "DailyNews",
                        status="alive",
                        details=(
                            f"window={summary['window']} "
                            f"성공={summary['categories_success']} "
                            f"실패={summary['categories_failed']} "
                            f"기사={summary['articles']}"
                        ),
                    )
            except Exception:
                pass

            return 0
    except AlreadyRunningError:
        logger.warning("lock", "skipped", "job already running")
        state.record_job_finish(run_id, status="skipped", error_text="already running")
        return 2
    except Exception as exc:
        logger.error("complete", "failed", "run_daily_news failed", error=str(exc))
        state.record_job_finish(run_id, status="failed", summary=summary, error_text=str(exc))
        _print_manifest(summary, "failed", run_id)

        # [v2.0] 에러 알림: 파이프라인 실패 시 즉시 Discord/Telegram 전송
        try:
            from shared.notifications import Notifier

            _notifier = Notifier.from_env()
            if _notifier.has_channels:
                _notifier.send_error(
                    f"[TOTAL-FAIL] DailyNews 파이프라인 실패: {exc}",
                    error=exc,
                    source="DailyNews",
                )
        except Exception:
            pass

        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the daily news extraction and analysis pipeline.")
    parser.add_argument("--force", action="store_true", help="Ignore schedule window and use the last 24 hours")
    parser.add_argument("--max-items", type=int, default=5, help="Maximum articles to analyze per category")
    parser.add_argument("--run-id", help="Optional run identifier for logs and state tracking")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(run_daily_news(force=args.force, max_items=args.max_items, run_id=args.run_id))


if __name__ == "__main__":
    raise SystemExit(main())
