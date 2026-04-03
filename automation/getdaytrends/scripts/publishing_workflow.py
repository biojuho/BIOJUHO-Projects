"""Utilities for the getdaytrends V2.0 manual review workflow.

This script treats Notion as the canonical approval queue, while the local DB
stores lifecycle records, publish receipts, and feedback summaries.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()


CHECKLISTS = {
    "X": [
        "Check policy-sensitive claims before manual posting",
        "Keep the final post within platform character limits",
        "Confirm the first line is strong enough for manual publish",
        "Remove unsupported hashtags or risky automation markers",
        "Verify this post is being published manually, not by scheduler",
    ],
    "Threads": [
        "Confirm the draft still fits the audience voice",
        "Check that engagement prompt feels natural",
        "Verify manual publish ownership and timing",
    ],
    "NaverBlog": [
        "Verify title and headings before publish",
        "Check SEO keywords and CTA placement",
        "Confirm final formatting and links manually",
    ],
}


def _get_notion_client():
    try:
        from notion_client import Client as NotionClient
    except ImportError:
        print("notion-client is required: pip install notion-client")
        return None

    token = os.getenv("NOTION_TOKEN", "")
    if not token:
        print("NOTION_TOKEN is not configured")
        return None
    return NotionClient(auth=token)


def _get_hub_db_id() -> str:
    db_id = os.getenv("CONTENT_HUB_DATABASE_ID", "")
    if not db_id:
        print("CONTENT_HUB_DATABASE_ID is not configured")
    return db_id


def _property_title(props: dict) -> str:
    title_prop = props.get("Name", {})
    values = title_prop.get("title", [])
    if not values:
        return "Untitled"
    return values[0].get("plain_text") or values[0].get("text", {}).get("content", "Untitled")


def _rich_text_value(props: dict, name: str) -> str:
    values = props.get(name, {}).get("rich_text", [])
    if not values:
        return ""
    return "".join(item.get("plain_text") or item.get("text", {}).get("content", "") for item in values)


def _status_value(props: dict) -> str:
    return props.get("Status", {}).get("select", {}).get("name", "")


def _platform_names(props: dict) -> list[str]:
    return [item.get("name", "") for item in props.get("Platform", {}).get("multi_select", []) if item.get("name")]


def _published_property_updates(props: dict, published_url: str, published_at: str, receipt_id: str) -> dict:
    updates = {}
    if "Status" in props:
        updates["Status"] = {"select": {"name": "Published"}}
    if "Published URL" in props:
        updates["Published URL"] = {"url": published_url}
    elif "URL" in props:
        updates["URL"] = {"url": published_url}
    if "Published At" in props:
        updates["Published At"] = {"date": {"start": published_at}}
    if "Receipt ID" in props and receipt_id:
        updates["Receipt ID"] = {"rich_text": [{"text": {"content": receipt_id}}]}
    return updates


def add_checklists_to_ready_pages() -> None:
    notion = _get_notion_client()
    db_id = _get_hub_db_id()
    if not notion or not db_id:
        return

    results = notion.databases.query(
        database_id=db_id,
        filter={"property": "Status", "select": {"equals": "Ready"}},
        page_size=100,
    )
    pages = results.get("results", [])
    if not pages:
        print("No Ready pages found.")
        return

    for page in pages:
        props = page.get("properties", {})
        page_id = page["id"]
        title = _property_title(props)
        platforms = _platform_names(props) or ["X"]

        children = [
            {"object": "block", "type": "divider", "divider": {}},
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Manual Publish Checklist"}}]},
            },
        ]
        for platform in platforms:
            children.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": [{"type": "text", "text": {"content": platform}}]},
                }
            )
            for item in CHECKLISTS.get(platform, []):
                children.append(
                    {
                        "object": "block",
                        "type": "to_do",
                        "to_do": {"rich_text": [{"type": "text", "text": {"content": item}}], "checked": False},
                    }
                )
        notion.blocks.children.append(block_id=page_id, children=children)
        print(f"checklist added: {title}")


def promote_drafts_to_ready(min_viral_score: int = 60) -> None:
    notion = _get_notion_client()
    db_id = _get_hub_db_id()
    if not notion or not db_id:
        return

    results = notion.databases.query(
        database_id=db_id,
        filter={
            "and": [
                {"property": "Status", "select": {"equals": "Draft"}},
                {"property": "Score", "number": {"greater_than_or_equal_to": min_viral_score}},
            ]
        },
        page_size=100,
    )
    for page in results.get("results", []):
        title = _property_title(page.get("properties", {}))
        notion.pages.update(page_id=page["id"], properties={"Status": {"select": {"name": "Ready"}}})
        print(f"promoted: {title}")


async def _sync_review_decision(draft_id: str, decision: str, reviewed_by: str, review_note: str, db_path: str, database_url: str) -> None:
    from db import get_connection, init_db, save_review_decision

    conn = await get_connection(db_path, database_url=database_url)
    try:
        await init_db(conn)
        await save_review_decision(
            conn,
            draft_id=draft_id,
            decision=decision,
            reviewed_by=reviewed_by,
            review_note=review_note,
            source="notion",
        )
    finally:
        await conn.close()


def sync_approved_from_notion(db_path: str, database_url: str = "") -> None:
    notion = _get_notion_client()
    db_id = _get_hub_db_id()
    if not notion or not db_id:
        return

    results = notion.databases.query(
        database_id=db_id,
        filter={"property": "Status", "select": {"equals": "Approved"}},
        page_size=100,
    )
    synced = 0
    for page in results.get("results", []):
        props = page.get("properties", {})
        draft_id = _rich_text_value(props, "Draft ID")
        if not draft_id:
            continue
        title = _property_title(props)
        asyncio.run(_sync_review_decision(draft_id, "approved", "notion-manual", title, db_path, database_url))
        synced += 1
    print(f"approved sync complete: {synced}")


async def _record_publish_receipt_async(
    *,
    draft_id: str,
    platform: str,
    published_url: str,
    db_path: str,
    database_url: str,
) -> str:
    from db import get_connection, init_db, record_publish_receipt

    conn = await get_connection(db_path, database_url=database_url)
    try:
        await init_db(conn)
        return await record_publish_receipt(
            conn,
            draft_id=draft_id,
            platform=platform.lower(),
            success=True,
            published_url=published_url,
            published_at=datetime.now().isoformat(),
        )
    finally:
        await conn.close()


def mark_as_published(page_id: str, published_url: str, db_path: str, database_url: str = "") -> None:
    notion = _get_notion_client()
    if not notion:
        return

    page = notion.pages.retrieve(page_id=page_id)
    props = page.get("properties", {})
    draft_id = _rich_text_value(props, "Draft ID")
    platforms = _platform_names(props)
    platform = platforms[0] if platforms else "X"
    receipt_id = ""
    if draft_id:
        receipt_id = asyncio.run(
            _record_publish_receipt_async(
                draft_id=draft_id,
                platform=platform,
                published_url=published_url,
                db_path=db_path,
                database_url=database_url,
            )
        )

    updates = _published_property_updates(props, published_url, datetime.now().isoformat(), receipt_id)
    if updates:
        notion.pages.update(page_id=page_id, properties=updates)
    print(f"published marked: {page_id[:12]} receipt={receipt_id or '-'}")


async def _record_feedback_async(
    *,
    draft_id: str,
    receipt_id: str,
    metric_window: str,
    impressions: int,
    engagements: int,
    clicks: int,
    collector_status: str,
    strategy_notes: str,
    db_path: str,
    database_url: str,
) -> None:
    from db import get_connection, init_db, record_feedback_summary

    conn = await get_connection(db_path, database_url=database_url)
    try:
        await init_db(conn)
        await record_feedback_summary(
            conn,
            draft_id=draft_id,
            receipt_id=receipt_id,
            metric_window=metric_window,
            impressions=impressions,
            engagements=engagements,
            clicks=clicks,
            collector_status=collector_status,
            strategy_notes=strategy_notes,
        )
    finally:
        await conn.close()


def record_feedback(
    page_id: str,
    *,
    metric_window: str,
    impressions: int,
    engagements: int,
    clicks: int,
    collector_status: str,
    strategy_notes: str,
    db_path: str,
    database_url: str = "",
) -> None:
    notion = _get_notion_client()
    if not notion:
        return

    page = notion.pages.retrieve(page_id=page_id)
    props = page.get("properties", {})
    draft_id = _rich_text_value(props, "Draft ID")
    receipt_id = _rich_text_value(props, "Receipt ID")
    if not draft_id or not receipt_id:
        raise ValueError("Draft ID and Receipt ID must exist before recording feedback")

    asyncio.run(
        _record_feedback_async(
            draft_id=draft_id,
            receipt_id=receipt_id,
            metric_window=metric_window,
            impressions=impressions,
            engagements=engagements,
            clicks=clicks,
            collector_status=collector_status,
            strategy_notes=strategy_notes,
            db_path=db_path,
            database_url=database_url,
        )
    )
    print(f"feedback recorded: {draft_id}")


def show_dashboard() -> None:
    notion = _get_notion_client()
    db_id = _get_hub_db_id()
    if not notion or not db_id:
        return

    results = notion.databases.query(database_id=db_id, page_size=100)
    pages = results.get("results", [])
    counts: dict[str, int] = {}
    for page in pages:
        status = _status_value(page.get("properties", {})) or "Unknown"
        counts[status] = counts.get(status, 0) + 1

    print("Content Hub status summary")
    for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {name:10s} {count:3d}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="getdaytrends V2 manual review workflow")
    parser.add_argument("--add-checklists", action="store_true")
    parser.add_argument("--promote-ready", action="store_true")
    parser.add_argument("--sync-approved", action="store_true")
    parser.add_argument("--mark-published", type=str, metavar="PAGE_ID")
    parser.add_argument("--record-feedback", type=str, metavar="PAGE_ID")
    parser.add_argument("--url", type=str, default="")
    parser.add_argument("--metric-window", type=str, default="48h")
    parser.add_argument("--impressions", type=int, default=0)
    parser.add_argument("--engagements", type=int, default=0)
    parser.add_argument("--clicks", type=int, default=0)
    parser.add_argument("--collector-status", type=str, default="manual")
    parser.add_argument("--strategy-notes", type=str, default="")
    parser.add_argument("--min-score", type=int, default=60)
    parser.add_argument("--db-path", type=str, default=str((__import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "getdaytrends.db")))
    parser.add_argument("--database-url", type=str, default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--dashboard", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.add_checklists:
        add_checklists_to_ready_pages()
    elif args.promote_ready:
        promote_drafts_to_ready(min_viral_score=args.min_score)
    elif args.sync_approved:
        sync_approved_from_notion(args.db_path, database_url=args.database_url)
    elif args.mark_published:
        if not args.url:
            raise SystemExit("--url is required with --mark-published")
        mark_as_published(args.mark_published, args.url, args.db_path, database_url=args.database_url)
    elif args.record_feedback:
        record_feedback(
            args.record_feedback,
            metric_window=args.metric_window,
            impressions=args.impressions,
            engagements=args.engagements,
            clicks=args.clicks,
            collector_status=args.collector_status,
            strategy_notes=args.strategy_notes,
            db_path=args.db_path,
            database_url=args.database_url,
        )
    else:
        show_dashboard()


if __name__ == "__main__":
    main()
