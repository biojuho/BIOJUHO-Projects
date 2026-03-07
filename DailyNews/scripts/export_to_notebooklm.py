from __future__ import annotations

import asyncio
from datetime import datetime, date
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from antigravity_mcp.integrations.notion_adapter import NotionAdapter
from settings import NOTION_REPORTS_DATA_SOURCE_ID, OUTPUT_DIR


async def fetch_todays_pages() -> list[dict]:
    if not NOTION_REPORTS_DATA_SOURCE_ID:
        print("[ERROR] NOTION_REPORTS_DATA_SOURCE_ID is missing.")
        return []

    adapter = NotionAdapter()
    if not adapter.is_configured():
        print("[ERROR] NOTION_API_KEY is missing.")
        return []

    today_str = date.today().isoformat()
    print(f"[INFO] Searching report pages for {today_str}", flush=True)
    results, _ = await adapter.query_data_source(
        data_source_id=NOTION_REPORTS_DATA_SOURCE_ID,
        filter_payload={"property": "Date", "date": {"equals": today_str}},
        limit=100,
    )
    return results


async def main() -> None:
    print("[INFO] Starting export to NotebookLM...", flush=True)
    pages = await fetch_todays_pages()
    if not pages:
        print("[INFO] No report pages found for today.", flush=True)
        return

    adapter = NotionAdapter()
    today_str = date.today().isoformat()
    full_md_content = f"# Antigravity Content Engine Briefing - {today_str}\n\n"
    full_md_content += f"**Source Count**: {len(pages)} reports\n"
    full_md_content += f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n"

    for page in pages:
        title_items = page.get("properties", {}).get("Name", {}).get("title", [])
        title = title_items[0].get("plain_text", "Untitled") if title_items else "Untitled"
        print(f"  - Processing: {title}", flush=True)
        payload = await adapter.get_page(page_id=page["id"], include_blocks=True, max_depth=1)
        full_md_content += f"\n# {title}\n"
        full_md_content += payload.get("markdown", "") + "\n\n---\n"

    output_dir = Path(OUTPUT_DIR) / "notebooklm_sources"
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{today_str}_News_Briefing.md"
    file_path.write_text(full_md_content, encoding="utf-8")
    print(f"[INFO] Export completed: {file_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
