"""Create the Notion Content Hub database used by getdaytrends."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv(_WORKSPACE_ROOT / ".env", override=True)

CONTENT_HUB_TITLE = "Content Hub - Multiplatform Content Management"
TARGET_PLATFORMS = "x,threads,naver_blog"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the Notion Content Hub database used by getdaytrends.")
    parser.add_argument(
        "--parent-page-id",
        default="",
        help="Parent Notion page ID. If omitted, the script tries NOTION_DATABASE_ID's parent or prompts.",
    )
    return parser.parse_args(argv)


def _content_hub_properties() -> dict[str, Any]:
    return {
        "Name": {"title": {}},
        "Status": _select_property(
            [
                ("Draft", "gray"),
                ("Ready", "yellow"),
                ("Approved", "blue"),
                ("Published", "green"),
                ("Rejected", "red"),
                ("Expired", "orange"),
                ("Archived", "brown"),
            ]
        ),
        "Feedback State": _select_property(
            [
                ("Need Review", "yellow"),
                ("Need Revision", "red"),
                ("Recheck", "blue"),
                ("Approved", "green"),
                ("Parked", "gray"),
            ]
        ),
        "Next Action": _select_property(
            [
                ("Review Copy", "blue"),
                ("Revise Draft", "orange"),
                ("Approve Publish", "green"),
                ("Wait Metrics", "gray"),
                ("Archive", "brown"),
            ]
        ),
        "Priority": _select_property([("High", "red"), ("Medium", "yellow"), ("Low", "gray")]),
        "Category": _select_property(
            [
                ("Tech", "blue"),
                ("AI", "purple"),
                ("Economy", "green"),
                ("Society", "orange"),
                ("Science", "pink"),
                ("Global", "red"),
                ("Other", "gray"),
            ]
        ),
        "Date": {"date": {}},
        "Due Date": {"date": {}},
        "Created Time": {"created_time": {}},
        "Tags": _multi_select_property(
            [
                ("Trend", "blue"),
                ("Breaking", "red"),
                ("Evergreen", "green"),
                ("Manual", "gray"),
                ("Revised", "orange"),
            ]
        ),
        "Score": {"number": {"format": "number"}},
        "Platform": _multi_select_property([("X", "blue"), ("Threads", "purple"), ("NaverBlog", "green")]),
        "Reviewer": {"people": {}},
        "Owner": {"people": {}},
        "Feedback Notes": {"rich_text": {}},
        "URL": {"url": {}},
        "Trend ID": {"rich_text": {}},
        "Draft ID": {"rich_text": {}},
        "Prompt Version": {"rich_text": {}},
        "QA Score": {"number": {"format": "number"}},
        "Blocking Reasons": {"rich_text": {}},
        "Published URL": {"url": {}},
        "Published At": {"date": {}},
        "Receipt ID": {"rich_text": {}},
    }


def _select_property(options: list[tuple[str, str]]) -> dict[str, Any]:
    return {"select": {"options": [_option(name, color) for name, color in options]}}


def _multi_select_property(options: list[tuple[str, str]]) -> dict[str, Any]:
    return {"multi_select": {"options": [_option(name, color) for name, color in options]}}


def _option(name: str, color: str) -> dict[str, str]:
    return {"name": name, "color": color}


def _valid_notion_token(token: str) -> bool:
    return bool(token and "your_" not in token)


def _parent_page_from_database(notion, existing_db_id: str) -> str | None:
    if not existing_db_id:
        return None
    try:
        db_info = notion.databases.retrieve(database_id=existing_db_id)
    except Exception as exc:
        print(f"Existing DB lookup failed: {exc}")
        print("Creating Content Hub from a manually supplied parent page.")
        return None

    parent = db_info.get("parent", {})
    if parent.get("type") == "page_id":
        return parent["page_id"]
    return None


def _prompt_parent_page_id() -> str | None:
    print("\nEnter a parent Notion page ID from a page URL:")
    print("  Example: https://notion.so/MyPage-abc123def456 -> abc123def456")
    parent_page_id = input("  Page ID: ").strip().replace("-", "")
    if not parent_page_id:
        print("Parent page ID is required.")
        return None
    return parent_page_id


def _create_content_hub_database(notion, parent_page_id: str) -> dict[str, Any]:
    return notion.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": CONTENT_HUB_TITLE}}],
        properties=_content_hub_properties(),
        is_inline=True,
    )


def _env_lines(new_db_id: str) -> list[str]:
    return [
        "",
        "",
        "# [v12.0] Multiplatform Content Hub (created by setup_content_hub.py)",
        "ENABLE_CONTENT_HUB=true",
        f"CONTENT_HUB_DATABASE_ID={new_db_id}",
        f"TARGET_PLATFORMS={TARGET_PLATFORMS}",
        "BLOG_MIN_SCORE=70",
    ]


def _append_env_settings(env_path: Path, new_db_id: str) -> bool:
    if not env_path.exists():
        return False
    with env_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(_env_lines(new_db_id)) + "\n")
    return True


def _sample_page_payload(new_db_id: str) -> dict[str, Any]:
    return {
        "parent": {"database_id": new_db_id},
        "properties": {
            "Name": {"title": [{"text": {"content": "[X] Content Hub smoke test"}}]},
            "Status": {"select": {"name": "Draft"}},
            "Feedback State": {"select": {"name": "Need Review"}},
            "Next Action": {"select": {"name": "Review Copy"}},
            "Priority": {"select": {"name": "High"}},
            "Category": {"select": {"name": "Tech"}},
            "Date": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
            "Score": {"number": 85},
            "Platform": {"multi_select": [{"name": "X"}]},
            "Tags": {"multi_select": [{"name": "Manual"}]},
        },
        "children": [
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "✅"},
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": (
                                    "Content Hub was created successfully.\n"
                                    "Remove this smoke-test page before running production pipelines."
                                )
                            },
                        }
                    ],
                    "color": "green_background",
                },
            }
        ],
    }


def _create_sample_page(notion, new_db_id: str) -> dict[str, Any]:
    return notion.pages.create(**_sample_page_payload(new_db_id))


def _print_env_instructions(new_db_id: str) -> None:
    print("\nAdd these settings to .env:")
    for line in _env_lines(new_db_id):
        if line:
            print(f"   {line}")


def _maybe_append_env(new_db_id: str, env_path: Path) -> None:
    if input("\nAppend these settings to .env automatically? (y/n): ").strip().lower() != "y":
        return
    if _append_env_settings(env_path, new_db_id):
        print("   .env updated.")
    else:
        print(f"   .env not found: {env_path}")
        print("   Add the settings manually.")


def _maybe_create_sample_page(notion, new_db_id: str) -> None:
    if input("\nCreate a sample test page? (y/n): ").strip().lower() != "y":
        return
    sample = _create_sample_page(notion, new_db_id)
    print(f"   Sample page created: {sample.get('url', '')}")


def _setup_content_hub(notion, parent_page_id: str, env_path: Path) -> dict[str, Any]:
    print("\nCreating Content Hub DB...")
    new_db = _create_content_hub_database(notion, parent_page_id)
    new_db_id = new_db["id"]
    print("\nContent Hub DB created.")
    print(f"   DB ID: {new_db_id}")
    print(f"   URL: {new_db.get('url', '')}")
    _print_env_instructions(new_db_id)
    _maybe_append_env(new_db_id, env_path)
    _maybe_create_sample_page(notion, new_db_id)
    print("\nSetup complete. Future pipeline runs can save to Content Hub.")
    return new_db


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    try:
        from notion_client import Client as NotionClient
    except ImportError:
        print("notion-client is required: pip install notion-client")
        return

    token = os.getenv("NOTION_TOKEN", "")
    if not _valid_notion_token(token):
        print("NOTION_TOKEN is not configured.")
        print("   Add NOTION_TOKEN=<notion-integration-token> to .env")
        return

    notion = NotionClient(auth=token)
    parent_page_id = args.parent_page_id.strip().replace("-", "")
    parent_page_id = parent_page_id or _parent_page_from_database(notion, os.getenv("NOTION_DATABASE_ID", ""))
    parent_page_id = parent_page_id or _prompt_parent_page_id()
    if not parent_page_id:
        return

    try:
        _setup_content_hub(notion, parent_page_id, _PROJECT_ROOT / ".env")
    except Exception as exc:
        print(f"\nDB creation failed: {exc}")
        print("Possible causes:")
        print("   - Notion integration is not connected to the parent page")
        print("   - Parent page ID is invalid")
        print("   - API permissions are insufficient")


if __name__ == "__main__":
    main()
