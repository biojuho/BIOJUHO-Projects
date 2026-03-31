"""Weekly NotebookLM Digest — aggregate a week's reports into one comprehensive notebook.

Usage:
    python -m scripts.weekly_notebooklm_digest
    python -m scripts.weekly_notebooklm_digest --week 2026-W12
    python -m scripts.weekly_notebooklm_digest --days 7 --content-types report mind-map audio
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from notion_client import AsyncClient
from runtime import configure_stdout_utf8, generate_run_id, get_logger
from settings import NOTION_API_KEY, NOTION_DASHBOARD_PAGE_ID, NOTION_REPORTS_DATABASE_ID, OUTPUT_DIR


async def fetch_week_reports(
    notion: AsyncClient,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Fetch all report pages from Notion within the date range."""
    results = []
    has_more = True
    start_cursor = None

    while has_more:
        kwargs: dict = {
            "database_id": NOTION_REPORTS_DATABASE_ID,
            "filter": {
                "and": [
                    {"property": "Date", "date": {"on_or_after": start_date.isoformat()}},
                    {"property": "Date", "date": {"on_or_before": end_date.isoformat()}},
                ]
            },
            "sorts": [{"property": "Date", "direction": "ascending"}],
            "page_size": 100,
        }
        if start_cursor:
            kwargs["start_cursor"] = start_cursor

        response = await notion.databases.query(**kwargs)
        results.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    return results


def parse_notion_report(page: dict) -> dict:
    """Extract structured data from a Notion report page."""
    props = page.get("properties", {})

    # Category
    source_select = props.get("Source", {}).get("select")
    category = source_select.get("name", "Unknown") if source_select else "Unknown"

    # Title
    title_items = props.get("Name", {}).get("title", [])
    title = title_items[0].get("plain_text", "Untitled") if title_items else "Untitled"

    # Date
    date_prop = props.get("Date", {}).get("date")
    report_date = date_prop.get("start", "") if date_prop else ""

    # Description (contains summary + insights)
    desc_items = props.get("Description", {}).get("rich_text", [])
    description = desc_items[0].get("plain_text", "") if desc_items else ""

    # Parse summary and insights from description
    summary_lines = []
    insights = []
    current_section = None
    for line in description.split("\n"):
        line = line.strip()
        if line.startswith("[Summary]"):
            current_section = "summary"
            continue
        elif line.startswith("[Insight]"):
            current_section = "insight"
            continue
        if current_section == "summary" and line:
            summary_lines.append(line)
        elif current_section == "insight" and line:
            insights.append(line)

    return {
        "category": category,
        "title": title,
        "report_date": report_date,
        "summary_lines": summary_lines,
        "insights": insights,
        "source_links": [],  # URLs not stored in Notion properties; populated below
        "window_name": "daily",
        "window_start": report_date,
        "window_end": report_date,
    }


async def run_weekly_digest(
    *,
    week_label: str = "",
    days: int = 7,
    content_types: list[str] | None = None,
) -> int:
    configure_stdout_utf8()
    run_id = generate_run_id("weekly_digest")
    logger = get_logger("weekly_digest", run_id)

    if not NOTION_API_KEY or not NOTION_REPORTS_DATABASE_ID:
        logger.error("bootstrap", "failed", "NOTION_API_KEY or NOTION_REPORTS_DATABASE_ID missing")
        return 1

    # Date range
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    week_label = week_label or end_date.strftime("%Y-W%V")

    logger.info(
        "digest",
        "start",
        "weekly digest",
        week=week_label,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
    )

    # 1. Fetch reports from Notion
    notion = AsyncClient(auth=NOTION_API_KEY)
    pages = await fetch_week_reports(notion, start_date, end_date)
    if not pages:
        logger.warning("digest", "skipped", "no reports found for the week")
        return 0

    reports = [parse_notion_report(p) for p in pages]
    logger.info("digest", "fetched", f"{len(reports)} reports from Notion")

    # 2. Initialize NotebookLM adapter
    try:
        from antigravity_mcp.integrations.notebooklm_adapter import get_notebooklm_adapter

        adapter = get_notebooklm_adapter()
        if not adapter.is_available:
            logger.error("digest", "failed", "notebooklm-py not installed")
            return 1
        if not await adapter.check_availability():
            logger.error("digest", "failed", "NotebookLM auth failed")
            return 1
    except Exception as exc:
        logger.error("digest", "failed", "adapter init failed", error=str(exc))
        return 1

    # 3. Create weekly digest notebook
    try:
        result = await adapter.create_weekly_digest(
            reports=reports,
            week_label=week_label,
            content_types=content_types,
        )
    except Exception as exc:
        logger.error("digest", "failed", "weekly digest creation failed", error=str(exc))
        return 1

    # 4. Save result summary
    output_path = Path(OUTPUT_DIR) / "weekly_digests"
    output_path.mkdir(parents=True, exist_ok=True)

    summary_file = output_path / f"{week_label}_digest.md"
    notebook_url = f"https://notebooklm.google.com/notebook/{result['notebook_id']}"

    md_content = f"# Weekly Digest: {week_label}\n\n"
    md_content += f"- **Notebook**: [{result['notebook_id'][:12]}...]({notebook_url})\n"
    md_content += f"- **Sources**: {result['source_count']}\n"
    md_content += f"- **Reports**: {len(reports)}\n"
    md_content += f"- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"

    if result.get("weekly_analysis"):
        md_content += f"## Weekly Analysis\n\n{result['weekly_analysis']}\n\n"

    if result.get("topic_connections"):
        md_content += f"## Cross-Category Connections\n\n{result['topic_connections']}\n\n"

    if result.get("artifacts"):
        md_content += "## Artifacts\n\n"
        for atype, aid in result["artifacts"].items():
            md_content += f"- **{atype}**: {aid}\n"

    summary_file.write_text(md_content, encoding="utf-8")

    logger.info(
        "digest",
        "success",
        "weekly digest complete",
        week=week_label,
        notebook_id=result["notebook_id"][:8],
        sources=result["source_count"],
        artifacts=len(result.get("artifacts", {})),
        output=str(summary_file),
    )

    # 5. Upload digest link to Notion dashboard (optional)
    try:
        if NOTION_DASHBOARD_PAGE_ID:
            await notion.blocks.children.append(
                NOTION_DASHBOARD_PAGE_ID,
                children=[
                    {
                        "object": "block",
                        "type": "callout",
                        "callout": {
                            "icon": {"emoji": "\U0001f4da"},
                            "color": "green_background",
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {"content": f"Weekly Digest {week_label}: "},
                                    "annotations": {"bold": True},
                                },
                                {
                                    "type": "text",
                                    "text": {"content": "Open in NotebookLM", "link": {"url": notebook_url}},
                                },
                                {
                                    "type": "text",
                                    "text": {"content": f" ({result['source_count']} sources, {len(reports)} reports)"},
                                },
                            ],
                        },
                    }
                ],
            )
            logger.info("digest", "notion", "dashboard link added")
    except Exception as exc:
        logger.debug("digest", "skipped", "dashboard update failed", error=str(exc))

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate weekly NotebookLM digest")
    parser.add_argument("--week", default="", help="Week label (e.g., 2026-W12). Auto-detected if omitted.")
    parser.add_argument("--days", type=int, default=7, help="Number of days to include (default: 7)")
    parser.add_argument(
        "--content-types",
        nargs="+",
        default=None,
        help="Artifact types to generate (e.g., report mind-map audio)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(
        run_weekly_digest(
            week_label=args.week,
            days=args.days,
            content_types=args.content_types,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
