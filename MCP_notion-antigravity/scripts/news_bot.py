# =============================================================================
# PARTIAL LEGACY: news_bot.py
# =============================================================================
# The core collect -> analyze -> publish workflow has been migrated to
#   src/antigravity_mcp/pipelines/{collect,analyze,publish,dashboard}.py
#
# However, the following features in this script are STILL ACTIVE and have
# NOT yet been ported to the new pipeline architecture:
#   - load_sentiment_analyzer / per-article sentiment tagging
#   - load_market_data / market snapshot embedding in Notion pages
#   - load_proofreader / AI proofreading pass on summaries
#   - load_skill_integrator / auto-generated X opinion post drafts
#   - load_brain / BrainModule cross-article analysis with niche trends
#   - PIL infographic generation + Canva import/export (inline in process_category)
#
# Until these features are ported, this script remains the full-featured
# standalone entry point. Run it via:
#   python news_bot.py --max-items 5
# =============================================================================

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

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
    safe_gather,
)
from settings import (
    ANTIGRAVITY_TASKS_DB_ID,
    CANVA_ENABLED,
    NEWS_SOURCES_FILE,
    NOTION_API_KEY,
    OUTPUT_DIR,
    PIPELINE_MAX_CONCURRENCY,
    PROJECT_ROOT,
    SKILL_INTEGRATION_ENABLED,
)

# shared.llm 모듈
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
from shared.llm import TaskTier, get_client as _get_llm_client


def load_sources() -> dict[str, list[dict[str, str]]]:
    with NEWS_SOURCES_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_time_window() -> tuple[datetime, datetime, str]:
    now = datetime.now()
    if 6 <= now.hour < 10:
        end_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        start_time = (end_time - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        label = "Morning Brief"
    elif 17 <= now.hour < 20:
        end_time = now.replace(hour=18, minute=0, second=0, microsecond=0)
        start_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        label = "Evening Brief"
    else:
        end_time = now
        start_time = now - timedelta(hours=12)
        label = "Manual Brief"
    return start_time, end_time, label


def in_time_window(entry: Any, start: datetime, end: datetime) -> bool:
    published = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not published:
        return True
    try:
        published_dt = datetime(*published[:6])
    except Exception:
        return True
    return start <= published_dt <= end


def load_summarizer():
    try:
        return _get_llm_client()
    except Exception:
        return None


def load_brain(logger):
    try:
        from brain_module import BrainModule

        brain = BrainModule()
        logger.info("bootstrap", "success", "brain module initialized")
        return brain
    except Exception as exc:
        logger.warning("bootstrap", "degraded", "brain module unavailable", error=str(exc))
        return None


def load_x_radar(logger):
    skill_path = PROJECT_ROOT / ".agent" / "skills" / "x_radar"
    if not skill_path.exists():
        return None
    if str(skill_path) not in sys.path:
        sys.path.append(str(skill_path))
    try:
        import scraper as x_radar

        logger.info("bootstrap", "success", "x_radar loaded")
        return x_radar
    except Exception as exc:
        logger.warning("bootstrap", "degraded", "x_radar unavailable", error=str(exc))
        return None


def load_market_data(logger):
    try:
        import market_data

        return market_data
    except Exception as exc:
        logger.warning("bootstrap", "degraded", "market_data unavailable", error=str(exc))
        return None


def load_canva(logger):
    if not CANVA_ENABLED:
        logger.info("bootstrap", "skipped", "canva disabled or not configured")
        return None
    try:
        import canva_generator

        canva_generator.get_access_token()
        logger.info("bootstrap", "success", "canva generator initialized")
        return canva_generator
    except Exception as exc:
        logger.warning("bootstrap", "degraded", "canva unavailable", error=str(exc))
        return None


def load_sentiment_analyzer(logger):
    try:
        from sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        logger.info("bootstrap", "success", "sentiment analyzer loaded")
        return analyzer
    except Exception as exc:
        logger.warning("bootstrap", "degraded", "sentiment analyzer unavailable", error=str(exc))
        return None


def load_skill_integrator(logger):
    if not SKILL_INTEGRATION_ENABLED:
        logger.info("bootstrap", "skipped", "skill integration disabled (set SKILL_INTEGRATION_ENABLED=true to enable)")
        return None
    try:
        import skill_integrator
        logger.info("bootstrap", "success", "skill integrator loaded")
        return skill_integrator
    except Exception as exc:
        logger.warning("bootstrap", "degraded", "skill integrator unavailable", error=str(exc))
        return None


def load_proofreader(logger):
    try:
        from proofreader import Proofreader
        proofreader = Proofreader()
        logger.info("bootstrap", "success", "proofreader loaded")
        return proofreader
    except Exception as exc:
        logger.warning("bootstrap", "degraded", "proofreader unavailable", error=str(exc))
        return None


async def summarize_article(title: str, content: str, client: Any, logger) -> str:
    if client is None:
        return (content or "")[:300] + ("..." if len(content or "") > 300 else "")

    has_content = bool(content and content.strip() and len(content.strip()) > 50)

    if has_content:
        prompt = (
            "Analyze the following tech/economic news article and provide a structured summary in Korean.\n"
            "Format your summary exactly as follows (use bullet points):\n"
            "- [핵심 사실]: (A concise 1-2 sentence summary of the main event/fact)\n"
            "- [시장 파급력]: (How this impacts the market, industry, or consumers)\n"
            "- [미래 전망]: (What to watch out for next or future implications)\n\n"
            f"Title: {title}\n"
            f"Content: {content[:2000]}"
        )
    else:
        prompt = (
            "Based ONLY on the following news headline, provide a brief structured summary in Korean.\n"
            "Do NOT say you lack information. Do NOT generate hypothetical content.\n"
            "Write a concise factual analysis based on what the headline tells you.\n"
            "Format (use bullet points):\n"
            "- [핵심 사실]: (1 sentence about the main fact from the headline)\n"
            "- [시장 파급력]: (1 sentence about potential market/industry impact)\n"
            "- [미래 전망]: (1 sentence about what to watch next)\n\n"
            f"Headline: {title}"
        )

    try:
        response = await run_with_timeout(
            client.acreate(
                tier=TaskTier.MEDIUM,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            ),
            30,
        )
        return response.text or (content or "")[:300]
    except Exception as exc:
        logger.warning("summary", "failed", "summarization failed; using fallback", error=str(exc), title=title[:80])
        return (content or "")[:300] + ("..." if len(content or "") > 300 else "")


def build_children(
    *,
    category: str,
    articles: list[dict[str, Any]],
    analysis: dict[str, Any] | None,
    time_label: str,
    market_snapshot: str | None,
    canva_result: dict | None = None,
) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": f"{category} {time_label}"}}]},
        }
    ]

    if canva_result and canva_result.get("edit_url"):
        children.append(
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"emoji": "🎨"},
                    "color": "purple_background",
                    "rich_text": [
                        {"type": "text", "text": {"content": "Canva 인포그래픽: "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "Canva에서 편집하기", "link": {"url": canva_result["edit_url"]}}},
                    ],
                },
            }
        )
        if canva_result.get("view_url"):
            children.append(
                {
                    "object": "block",
                    "type": "embed",
                    "embed": {
                        "url": canva_result["view_url"]
                    }
                }
            )

    if market_snapshot:
        children.append(
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"emoji": "📈"},
                    "color": "green_background",
                    "rich_text": [{"text": {"content": market_snapshot}}],
                },
            }
        )

    insights = (analysis or {}).get("insights") or []
    if insights:
        children.append(
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"text": {"content": "Insights"}}]},
            }
        )
        for insight in insights[:5]:
            children.append(
                {
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "icon": {"emoji": "💡"},
                        "color": "gray_background",
                        "rich_text": [
                            {"type": "text", "text": {"content": f"[{insight.get('topic', 'Issue')}] "}, "annotations": {"bold": True}},
                            {"type": "text", "text": {"content": str(insight.get('insight', ''))}},
                        ],
                    },
                }
            )

    x_thread = (analysis or {}).get("x_thread") or []
    if x_thread:
        children.append(
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"text": {"content": "X Thread Draft"}}]},
            }
        )
        children.append(
            {
                "object": "block",
                "type": "code",
                "code": {
                    "language": "plain text",
                    "rich_text": [{"text": {"content": "\n\n".join(str(item) for item in x_thread)}}],
                },
            }
        )
        children.append({"object": "block", "type": "divider", "divider": {}})

    sources = Counter(article.get("source", "Unknown") for article in articles)
    mermaid_code = "pie\n    title News Source Distribution\n"
    for source, count in sources.most_common(10):
        safe_source = source.replace('"', "").replace(":", "")
        mermaid_code += f'    "{safe_source}" : {count}\n'

    children.extend(
        [
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"text": {"content": "Source Distribution"}}]},
            },
            {
                "object": "block",
                "type": "code",
                "code": {
                    "language": "mermaid",
                    "rich_text": [{"text": {"content": mermaid_code}}],
                },
            },
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"text": {"content": "Collected News"}}]},
            },
        ]
    )

    for article in articles:
        children.append(
            {
                "object": "block",
                "type": "toggle",
                "toggle": {
                    "rich_text": [{"text": {"content": article["title"][:100]}}],
                    "children": [
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {"rich_text": [{"text": {"content": "Original Link", "link": {"url": article["link"]}}}]},
                        },
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": f"[{article.get('sentiment', 'NEUTRAL')}] Topics: {', '.join(article.get('topics', []))}"},
                                        "annotations": {"bold": True}
                                    }
                                ]
                            },
                        },
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {"rich_text": [{"text": {"content": article["summary"][:2000]}}]},
                        },
                    ],
                },
            }
        )

    return children


async def process_category(
    *,
    category: str,
    feeds: list[dict[str, str]],
    notion: AsyncClient,
    llm_client: Any,
    brain: Any,
    x_radar: Any,
    market_data: Any,
    canva: Any,
    sentiment_analyzer: Any,
    skill_integrator: Any,
    proofreader: Any,
    state: PipelineStateStore,
    logger,
    run_id: str,
    max_items: int,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    async with semaphore:
        start_time, end_time, label = get_time_window()
        window_str = f"{start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}"
        logger.info("category", "start", "processing category", category=category, window=window_str)

        articles: list[dict[str, Any]] = []
        seen_links: set[str] = set()

        for source in feeds:
            source_name = source["name"]
            source_url = source["url"]
            try:
                entries = await fetch_feed_entries(source_url)
            except Exception as exc:
                logger.error("fetch", "failed", "feed fetch failed", category=category, source=source_name, error=str(exc))
                continue

            for entry in entries:
                if not in_time_window(entry, start_time, end_time):
                    continue

                link = getattr(entry, "link", "")
                if not link or link in seen_links or state.has_article(link):
                    continue

                content = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
                summary = await summarize_article(getattr(entry, "title", "Untitled"), content, llm_client, logger)
                
                if proofreader:
                    try:
                        logger.info("category", "in_progress", "proofreading summary", category=category)
                        summary = await proofreader.proofread_text_async(summary)
                        summary = "✓ [Corrected by AI Editor]\n" + summary
                    except Exception as exc:
                        logger.warning("proofread", "failed", "proofreading failed; using original", error=str(exc))

                sentiment_label = "NEUTRAL"
                topics = []
                if sentiment_analyzer:
                    try:
                        sentiment_res = await asyncio.to_thread(sentiment_analyzer.analyze_texts, [getattr(entry, "title", "Untitled")])
                        if sentiment_res:
                            sentiment_label = sentiment_res[0].get("sentiment", "NEUTRAL")
                            topics = sentiment_res[0].get("topics", [])
                    except Exception as exc:
                        logger.warning("sentiment", "failed", "sentiment analysis failed", error=str(exc))

                articles.append(
                    {
                        "title": getattr(entry, "title", "Untitled"),
                        "link": link,
                        "description": content[:200],
                        "summary": summary,
                        "source": source_name,
                        "sentiment": sentiment_label,
                        "topics": topics,
                    }
                )
                seen_links.add(link)
                if len(articles) >= max_items:
                    break

        if not articles:
            logger.warning("category", "skipped", "no articles collected", category=category)
            return {"category": category, "status": "skipped", "articles": 0}

        niche_trends = None
        if x_radar is not None:
            try:
                trend_json = await run_with_timeout(asyncio.to_thread(x_radar.fetch_niche_trends, [category]), 20)
                niche_trends = json.loads(trend_json)
            except Exception as exc:
                logger.warning("trends", "failed", "x_radar fetch failed", category=category, error=str(exc))

        analysis = None
        if brain is not None:
            try:
                brain_input = [{"title": item["title"], "description": item["description"]} for item in articles]
                analysis = await run_with_timeout(
                    asyncio.to_thread(brain.analyze_news, category, brain_input, window_str, niche_trends),
                    60,
                )
            except Exception as exc:
                logger.warning("analysis", "failed", "brain analysis failed", category=category, error=str(exc))

        market_snapshot = None
        if market_data is not None:
            combined_text = " ".join(article["title"] for article in articles)
            try:
                market_snapshot = await run_with_timeout(
                    asyncio.to_thread(market_data.get_market_summary, combined_text),
                    15,
                )
            except Exception as exc:
                logger.warning("market", "failed", "market snapshot failed", category=category, error=str(exc))

        # Canva infographic: PIL -> PDF import -> Canva design + PNG export
        canva_result = None
        if canva is not None:
            try:
                from PIL import Image, ImageDraw, ImageFont
                ts = datetime.now().strftime("%Y%m%d_%H%M")
                infographic_path = OUTPUT_DIR / f"infographic_{category}_{ts}.png"
                infographic_path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    font_title = ImageFont.truetype("malgunbd.ttf", 60)
                    font_date = ImageFont.truetype("malgun.ttf", 30)
                    font_body_bold = ImageFont.truetype("malgunbd.ttf", 35)
                    font_body = ImageFont.truetype("malgun.ttf", 28)
                except Exception:
                    font_title = ImageFont.load_default()
                    font_date = ImageFont.load_default()
                    font_body_bold = ImageFont.load_default()
                    font_body = ImageFont.load_default()

                # Generate simple infographic with PIL
                img = Image.new("RGB", (1080, 1080), "#1a1a2e")
                draw = ImageDraw.Draw(img)
                draw.rectangle([(0, 0), (1080, 180)], fill="#16213e")
                draw.text((60, 45), f"{category.upper()} NEWS", font=font_title, fill="#e94560")
                draw.text((60, 125), datetime.now().strftime("%Y-%m-%d"), font=font_date, fill="#aaaaaa")
                
                y_pos = 220
                for idx, a in enumerate(articles[:5]):
                    draw.rectangle([(40, y_pos), (1040, y_pos + 140)], fill="#0f3460", outline="#e94560")
                    title_text = a['title'][:40] + "..." if len(a['title']) > 40 else a['title']
                    draw.text((70, y_pos + 30), f"{idx+1}. {title_text}", font=font_body_bold, fill="white")
                    draw.text((70, y_pos + 90), f"    출처: {a.get('source', 'Unknown')} | 감성: {a.get('sentiment', 'NEUTRAL')}", font=font_body, fill="#b5b5c3")
                    y_pos += 160
                    
                img.save(infographic_path)

                # Import to Canva
                title = f"[{category}] News {datetime.now().strftime('%Y-%m-%d')}"
                canva_result = await run_with_timeout(
                    canva.async_import_and_export(
                        image_path=infographic_path,
                        title=title,
                    ),
                    90,
                )
                if canva_result:
                    logger.info("canva", "success", "design imported", category=category, design_id=canva_result.get("design_id"))
                else:
                    logger.warning("canva", "skipped", "import failed", category=category)
            except Exception as exc:
                logger.warning("canva", "failed", "canva pipeline failed", category=category, error=str(exc))

        children = build_children(
            category=category,
            articles=articles,
            analysis=analysis,
            time_label=label,
            market_snapshot=market_snapshot,
            canva_result=canva_result,
        )

        # Aggregate sentiments and topics across the collected articles
        # This will be stored at the Notion Page level metadata.
        all_topics = []
        sentiments = []
        for article in articles:
            all_topics.extend(article.get("topics", []))
            sent_val = article.get("sentiment", "NEUTRAL")
            if sent_val not in ["NEUTRAL", "Unknown"]:
                sentiments.append(sent_val)

        # Basic majority vote for overall page sentiment
        overall_sentiment = "NEUTRAL"
        if sentiments:
            from collections import Counter
            overall_sentiment = Counter(sentiments).most_common(1)[0][0]

        # Deduplicate entities (top 5 max for Notion multi-select limit)
        top_entities = list(set([t for t in all_topics if t != "Unknown"]))[:5]

        page = await create_notion_page_with_retry(
            notion_client=notion,
            parent={"database_id": ANTIGRAVITY_TASKS_DB_ID},
            properties={
                "Name": {"title": [{"text": {"content": f"[{category}] {label} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"}}]},
                "Date": {"date": {"start": datetime.now().isoformat()}},
                "Type": {"select": {"name": "News"}},
                "Priority": {"select": {"name": "High"}},
                "Sentiment": {"select": {"name": overall_sentiment}},
                "Entities": {"multi_select": [{"name": entity} for entity in top_entities]},
            },
            children=children,
            logger=logger,
            step=f"upload:{category}",
        )

        page_id = page.get("id")
        for article in articles:
            state.record_article(link=article["link"], source=article["source"], notion_page_id=page_id, run_id=run_id)

        # --- Skill Integration: auto-generate X post drafts ---
        if skill_integrator is not None and page_id and analysis:
            try:
                opinion_result = await run_with_timeout(
                    skill_integrator.generate_opinion_post(analysis, category),
                    60,
                )
                x_draft_blocks = skill_integrator.build_x_draft_blocks(opinion_result)
                if x_draft_blocks:
                    await run_with_timeout(
                        notion.blocks.children.append(block_id=page_id, children=x_draft_blocks),
                        15,
                    )
                    logger.info("skills", "success", "x post draft appended to notion page", category=category)
                else:
                    logger.info("skills", "skipped", "opinion generator returned no usable content", category=category)
            except Exception as exc:
                logger.warning("skills", "failed", "x post draft generation failed (non-blocking)", category=category, error=str(exc))

        logger.info("category", "success", "category uploaded", category=category, articles=len(articles), page_id=page_id)
        result: dict[str, Any] = {"category": category, "status": "success", "articles": len(articles)}
        if canva_result:
            result["canva_design_id"] = canva_result.get("design_id")
            result["canva_edit_url"] = canva_result.get("edit_url")
            if canva_result.get("png_path"):
                result["canva_image"] = str(canva_result["png_path"])
        return result


async def run_news_bot(*, max_items: int, run_id: str | None = None) -> int:
    configure_stdout_utf8()
    run_id = run_id or generate_run_id("news_bot")
    logger = get_logger("news_bot", run_id)
    state = PipelineStateStore()
    state.record_job_start(run_id, "news_bot")

    if not NOTION_API_KEY:
        logger.error("bootstrap", "failed", "NOTION_API_KEY missing")
        state.record_job_finish(run_id, status="failed", error_text="NOTION_API_KEY missing")
        return 1
    if not ANTIGRAVITY_TASKS_DB_ID:
        logger.error("bootstrap", "failed", "ANTIGRAVITY_TASKS_DB_ID missing")
        state.record_job_finish(run_id, status="failed", error_text="ANTIGRAVITY_TASKS_DB_ID missing")
        return 1

    notion = AsyncClient(auth=NOTION_API_KEY)
    llm_client = load_summarizer()
    brain = load_brain(logger)
    x_radar = load_x_radar(logger)
    market_data = load_market_data(logger)
    canva = load_canva(logger)
    sentiment_analyzer = load_sentiment_analyzer(logger)
    skill_integrator_mod = load_skill_integrator(logger)
    proofreader = load_proofreader(logger)
    summary = {"categories_success": 0, "categories_failed": 0, "categories_skipped": 0, "articles": 0}

    try:
        with JobLock("news_bot", run_id):
            sources = load_sources()
            semaphore = asyncio.Semaphore(max(1, PIPELINE_MAX_CONCURRENCY))
            tasks = [
                process_category(
                    category=category,
                    feeds=feeds,
                    notion=notion,
                    llm_client=llm_client,
                    brain=brain,
                    x_radar=x_radar,
                    market_data=market_data,
                    canva=canva,
                    sentiment_analyzer=sentiment_analyzer,
                    skill_integrator=skill_integrator_mod,
                    proofreader=proofreader,
                    state=state,
                    logger=logger,
                    run_id=run_id,
                    max_items=max_items,
                    semaphore=semaphore,
                )
                for category, feeds in sources.items()
            ]

            results = await safe_gather(tasks)
            for result in results:
                if isinstance(result, Exception):
                    summary["categories_failed"] += 1
                    logger.error("category", "failed", "unhandled category task failure", error=str(result))
                    continue

                summary["articles"] += int(result.get("articles", 0))
                status = result.get("status")
                if status == "success":
                    summary["categories_success"] += 1
                elif status == "failed":
                    summary["categories_failed"] += 1
                else:
                    summary["categories_skipped"] += 1

            state.record_job_finish(run_id, status="success", summary=summary)
            logger.info("complete", "success", "news_bot finished", **summary)
            return 0
    except AlreadyRunningError:
        logger.warning("lock", "skipped", "job already running")
        state.record_job_finish(run_id, status="skipped", error_text="already running")
        return 2
    except Exception as exc:
        logger.error("complete", "failed", "news_bot failed", error=str(exc))
        state.record_job_finish(run_id, status="failed", summary=summary, error_text=str(exc))
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Notion news bot pipeline.")
    parser.add_argument("--max-items", type=int, default=5, help="Maximum articles to summarize per category")
    parser.add_argument("--run-id", help="Optional run identifier for logs and state tracking")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(run_news_bot(max_items=args.max_items, run_id=args.run_id))

if __name__ == "__main__":
    import os
    os._exit(main())
