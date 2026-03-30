"""Export today's reports to NotebookLM — file export + optional active API upload.

Usage:
    python -m scripts.export_to_notebooklm              # MD file export only
    python -m scripts.export_to_notebooklm --upload      # Also create NotebookLM notebook via API
    python -m scripts.export_to_notebooklm --content-types audio report  # Generate specific artifacts
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from settings import NOTION_API_KEY, OUTPUT_DIR


async def fetch_todays_pages() -> list[dict]:
    if not NOTION_API_KEY:
        print("[ERROR] NOTION_API_KEY is missing.")
        return []

    from notion_client import AsyncClient

    notion = AsyncClient(auth=NOTION_API_KEY)

    today_str = date.today().isoformat()
    print(f"[INFO] Searching report pages for {today_str}", flush=True)

    try:
        # Use search endpoint — queries by page title containing today's date
        response = await notion.search(
            query=f"Brief {today_str}",
            filter={"value": "page", "property": "object"},
            page_size=20,
        )
        all_results = response.get("results", [])

        # Filter to only News-type pages from today
        pages = []
        for p in all_results:
            props = p.get("properties", {})
            # Check Type property
            type_sel = props.get("Type", {}).get("select", {})
            if type_sel and type_sel.get("name") != "News":
                continue
            # Check Date property
            date_prop = props.get("Date", {}).get("date", {})
            if date_prop and date_prop.get("start", "").startswith(today_str):
                pages.append(p)

        print(f"[INFO] Found {len(pages)} report page(s)", flush=True)
        return pages
    except Exception as e:
        print(f"[ERROR] Notion search failed: {e}")
        return []


async def export_markdown(pages: list[dict]) -> Path | None:
    """Export reports to a combined Markdown file."""
    from notion_client import AsyncClient

    notion = AsyncClient(auth=NOTION_API_KEY)

    today_str = date.today().isoformat()
    full_md = f"# Antigravity Content Engine Briefing - {today_str}\n\n"
    full_md += f"**Source Count**: {len(pages)} reports\n"
    full_md += f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n"

    for page in pages:
        title_items = page.get("properties", {}).get("Name", {}).get("title", [])
        title = title_items[0].get("plain_text", "Untitled") if title_items else "Untitled"
        print(f"  - Processing: {title}", flush=True)

        # Fetch blocks (children) for each page
        blocks_resp = await notion.blocks.children.list(block_id=page["id"])
        blocks = blocks_resp.get("results", [])

        full_md += f"\n# {title}\n"
        for block in blocks:
            btype = block.get("type", "")
            if btype == "paragraph":
                texts = block.get("paragraph", {}).get("rich_text", [])
                full_md += "".join(t.get("plain_text", "") for t in texts) + "\n\n"
            elif btype in ("heading_2", "heading_3"):
                texts = block.get(btype, {}).get("rich_text", [])
                prefix = "## " if btype == "heading_2" else "### "
                full_md += prefix + "".join(t.get("plain_text", "") for t in texts) + "\n\n"
            elif btype == "callout":
                texts = block.get("callout", {}).get("rich_text", [])
                icon = block.get("callout", {}).get("icon", {}).get("emoji", "💡")
                full_md += f"> {icon} " + "".join(t.get("plain_text", "") for t in texts) + "\n\n"
            elif btype == "code":
                texts = block.get("code", {}).get("rich_text", [])
                lang = block.get("code", {}).get("language", "")
                full_md += f"```{lang}\n" + "".join(t.get("plain_text", "") for t in texts) + "\n```\n\n"
            elif btype == "divider":
                full_md += "---\n\n"
        full_md += "\n---\n"

    output_dir = Path(OUTPUT_DIR) / "notebooklm_sources"
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{today_str}_News_Briefing.md"
    file_path.write_text(full_md, encoding="utf-8")
    print(f"[INFO] Markdown export: {file_path}", flush=True)
    return file_path


async def upload_to_notebooklm(
    md_path: Path,
    pages: list[dict],
    content_types: list[str] | None = None,
) -> dict | None:
    """Create a NotebookLM notebook from today's export."""
    try:
        from antigravity_mcp.integrations.notebooklm_adapter import NOTEBOOKLM_AVAILABLE, NotebookLMAdapter
    except ImportError:
        print("[ERROR] notebooklm_adapter not found")
        return None

    if not NOTEBOOKLM_AVAILABLE:
        print("[ERROR] notebooklm-py is not installed (pip install notebooklm-py)")
        return None

    adapter = NotebookLMAdapter()
    if not await adapter.check_availability():
        print("[ERROR] NotebookLM authentication failed")
        return None

    from notebooklm import NotebookLMClient  # type: ignore

    today_str = date.today().isoformat()
    content_types = content_types or []

    async with await NotebookLMClient.from_storage() as client:
        # Create notebook
        title = f"[DailyNews] {today_str} Briefing"
        nb = await client.notebooks.create(title)
        print(f"[INFO] Notebook created: {nb.id[:12]}...", flush=True)

        # Add the markdown file as a text source
        md_content = md_path.read_text(encoding="utf-8")
        try:
            await client.notes.create(
                nb.id,
                title=f"Daily Briefing {today_str}",
                content=md_content[:50000],
            )
            print("[INFO] Briefing note added", flush=True)
        except Exception as e:
            print(f"[WARN] Note add failed: {e}", flush=True)

        # Add source URLs from Notion pages
        source_count = 0
        for page in pages:
            page_url = page.get("url", "")
            if page_url:
                try:
                    await client.sources.add_url(nb.id, page_url, wait=True)
                    source_count += 1
                except Exception:
                    pass

        # AI analysis
        summary = ""
        try:
            result = await client.chat.ask(
                nb.id,
                "오늘의 전체 뉴스를 종합 분석해줘. " "카테고리별 핵심 이슈와 카테고리 간 연결 패턴을 정리해줘.",
            )
            summary = result.answer if result else ""
            print(f"[INFO] AI summary: {len(summary)} chars", flush=True)
        except Exception as e:
            print(f"[WARN] AI analysis failed: {e}", flush=True)

        # Generate artifacts
        artifacts = {}
        for ctype in content_types:
            try:
                artifact_id = await adapter._generate_artifact(client, nb.id, ctype, today_str)
                if artifact_id:
                    artifacts[ctype] = artifact_id
                    print(f"[INFO] {ctype} artifact: {artifact_id[:12]}...", flush=True)
            except Exception as e:
                print(f"[WARN] {ctype} generation failed: {e}", flush=True)

        notebook_url = f"https://notebooklm.google.com/notebook/{nb.id}"
        print(f"\n[SUCCESS] NotebookLM notebook ready: {notebook_url}", flush=True)

        return {
            "notebook_id": nb.id,
            "notebook_url": notebook_url,
            "source_count": source_count,
            "summary": summary,
            "artifacts": artifacts,
        }


async def main(upload: bool = False, content_types: list[str] | None = None) -> None:
    print("[INFO] Starting export to NotebookLM...", flush=True)
    pages = await fetch_todays_pages()
    if not pages:
        print("[INFO] No report pages found for today.", flush=True)
        return

    # Always export markdown
    md_path = await export_markdown(pages)

    # Optionally upload to NotebookLM via API
    if upload and md_path:
        result = await upload_to_notebooklm(md_path, pages, content_types)
        if result:
            # Save result summary
            output_dir = Path(OUTPUT_DIR) / "notebooklm_sources"
            summary_file = output_dir / f"{date.today().isoformat()}_upload_result.json"
            import json

            summary_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[INFO] Upload result saved: {summary_file}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export today's reports to NotebookLM")
    parser.add_argument("--upload", action="store_true", help="Also upload to NotebookLM via API")
    parser.add_argument(
        "--content-types",
        nargs="+",
        default=None,
        help="Artifact types to generate when uploading (e.g., audio report mind-map)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(upload=args.upload, content_types=args.content_types))
