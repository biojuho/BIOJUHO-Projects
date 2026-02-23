import os
from datetime import date

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from notion_client import AsyncClient

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, ".env")
load_dotenv(env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
ANTIGRAVITY_DB_ID = os.getenv("ANTIGRAVITY_DB_ID")

if not ANTIGRAVITY_DB_ID:
    print("[WARNING] ANTIGRAVITY_DB_ID not found in .env, using default.")
    ANTIGRAVITY_DB_ID = "bb5cf3c8-d2bb-4b8b-a866-ba9ea86f16b7"

if not NOTION_API_KEY:
    raise ValueError("NOTION_API_KEY is not configured. Please check MCP_notion-antigravity/.env")

notion = AsyncClient(auth=NOTION_API_KEY)
mcp = FastMCP("Notion MCP Server")


def _extract_page_title(page: dict) -> str:
    title = "Untitled"
    properties = page.get("properties", {})
    for prop in properties.values():
        if prop.get("type") != "title":
            continue
        title_list = prop.get("title", [])
        if title_list:
            title = title_list[0].get("plain_text", "Untitled")
        break
    return title


def _line_to_block(line: str) -> dict:
    if line.startswith("## "):
        return {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": line[3:]}}]},
        }
    if line.startswith("# "):
        return {
            "object": "block",
            "type": "heading_1",
            "heading_1": {"rich_text": [{"text": {"content": line[2:]}}]},
        }
    if line.startswith("- "):
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"text": {"content": line[2:]}}]},
        }
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"text": {"content": line}}]},
    }


@mcp.tool()
async def search_notion(query: str) -> str:
    """Search pages in Notion and return compact text output."""
    try:
        response = await notion.search(query=query, page_size=5)
        results = []
        for page in response.get("results", []):
            page_id = page.get("id", "")
            url = page.get("url", "")
            title = _extract_page_title(page)
            results.append(f"- Title: {title}\n  ID: {page_id}\n  URL: {url}")

        if not results:
            return "No matching pages found."

        return "\n\n".join(results)
    except Exception as e:
        return f"Search failed: {str(e)}"


@mcp.tool()
async def read_page(page_id: str) -> str:
    """Read a Notion page and return plain text/markdown-like output."""
    try:
        blocks = await notion.blocks.children.list(block_id=page_id)
        content = []

        for block in blocks.get("results", []):
            block_type = block.get("type")
            if not block_type:
                continue

            payload = block.get(block_type, {})
            rich_text = payload.get("rich_text", [])
            if not rich_text:
                continue

            plain_text = "".join(part.get("plain_text", "") for part in rich_text)
            if block_type == "heading_1":
                content.append(f"# {plain_text}")
            elif block_type == "heading_2":
                content.append(f"## {plain_text}")
            elif block_type == "heading_3":
                content.append(f"### {plain_text}")
            elif block_type == "bulleted_list_item":
                content.append(f"- {plain_text}")
            elif block_type == "numbered_list_item":
                content.append(f"1. {plain_text}")
            else:
                content.append(plain_text)

        if not content:
            return "Page is empty or contains no readable text blocks."

        return "\n\n".join(content)
    except Exception as e:
        return f"Read failed: {str(e)}"


@mcp.tool()
async def add_task(
    title: str,
    content: str = "",
    type: str = "Task",
    priority: str = "medium",
    goal: str = "",
    achievement: str = "",
) -> str:
    """Create a task/log page in the Antigravity Notion database."""
    if not ANTIGRAVITY_DB_ID:
        return "Database ID is not configured."

    type_map = {
        "task": "Task",
        "idea": "Idea",
        "log": "Log",
        "bug": "Bug",
    }
    priority_map = {
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    }

    clean_type = type_map.get((type or "").lower(), type or "Task")
    clean_priority = priority_map.get((priority or "").lower(), priority or "Medium")

    children_blocks = []
    if content:
        for raw_line in content.split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            children_blocks.append(_line_to_block(line))

    properties = {
        "Name": {"title": [{"text": {"content": title}}]},
        "Date": {"date": {"start": date.today().isoformat()}},
        "Type": {"select": {"name": clean_type}},
        "Priority": {"select": {"name": clean_priority}},
    }
    if goal:
        properties["Goal"] = {"rich_text": [{"text": {"content": goal}}]}
    if achievement:
        properties["Achievement"] = {"rich_text": [{"text": {"content": achievement}}]}

    try:
        new_page = await notion.pages.create(
            parent={"database_id": ANTIGRAVITY_DB_ID},
            properties=properties,
            children=children_blocks,
        )
        return (
            "Task added successfully.\n"
            f"- Title: {title}\n"
            f"- Type: {clean_type}\n"
            f"- Priority: {clean_priority}\n"
            f"- URL: {new_page.get('url', '')}"
        )
    except Exception as e:
        return f"Create task failed: {str(e)}"


if __name__ == "__main__":
    mcp.run()