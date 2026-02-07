
import os
import sys
import io
import asyncio
from datetime import datetime, date
from notion_client import AsyncClient
from dotenv import load_dotenv

# Force UTF-8 for Windows Console (Python 3.7+)
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Load Environment Variables
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
load_dotenv(os.path.join(parent_dir, ".env"))

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = "bb5cf3c8-d2bb-4b8b-a866-ba9ea86f16b7" # Same as news_bot.py
OUTPUT_DIR = os.path.join(parent_dir, "output", "notebooklm_sources")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

if not NOTION_API_KEY:
    print("[ERROR] Notion API Key not found.")
    sys.exit(1)

notion = AsyncClient(auth=NOTION_API_KEY)

async def get_block_children(block_id):
    """Fetch all children blocks of a block (recursive for basic nesting)"""
    results = []
    try:
        response = await notion.blocks.children.list(block_id=block_id)
        results.extend(response.get("results", []))
        
        # Handle pagination if needed (usually 100 blocks limit, unlikely to exceed for single digest)
        while response.get("has_more"):
            response = await notion.blocks.children.list(block_id=block_id, start_cursor=response["next_cursor"])
            results.extend(response.get("results", []))
            
    except Exception as e:
        print(f"[WARN] Failed to fetch children for {block_id}: {e}")
    return results

def rich_text_to_md(rich_text_list):
    """Convert Notion rich text to Markdown"""
    text = ""
    for rt in rich_text_list:
        content = rt.get("plain_text", "")
        annotations = rt.get("annotations", {})
        href = rt.get("href")
        
        if annotations.get("bold"):
            content = f"**{content}**"
        if annotations.get("italic"):
            content = f"*{content}*"
        if annotations.get("code"):
            content = f"`{content}`"
        if annotations.get("strikethrough"):
            content = f"~~{content}~~"
            
        if href:
            content = f"[{content}]({href})"
            
        text += content
    return text

async def blocks_to_markdown(blocks, level=0):
    """Convert Notion blocks to Markdown string"""
    md_output = ""
    indent = "  " * level
    
    for block in blocks:
        btype = block["type"]
        
        if btype == "paragraph":
            text = rich_text_to_md(block["paragraph"]["rich_text"])
            md_output += f"\n{indent}{text}\n"
            
        elif btype.startswith("heading_"):
            size = int(btype.split("_")[1])
            # Notion H1 is MD #, H2 is ##
            # Adjust mapping slightly for document hierarchy
            hashes = "#" * (size + 1) 
            text = rich_text_to_md(block[btype]["rich_text"])
            md_output += f"\n{indent}{hashes} {text}\n"
            
        elif btype == "callout":
            text = rich_text_to_md(block["callout"]["rich_text"])
            icon = block["callout"].get("icon", {}).get("emoji", "💡")
            md_output += f"\n{indent}> {icon} {text}\n"
            
        elif btype == "code":
            text = rich_text_to_md(block["code"]["rich_text"])
            lang = block["code"]["language"]
            md_output += f"\n{indent}```\n{text}\n{indent}```\n"

        elif btype == "toggle":
            text = rich_text_to_md(block["toggle"]["rich_text"])
            md_output += f"\n{indent}- ▶️ {text}"
            # Fetch children
            if block["has_children"]:
                children = await get_block_children(block["id"])
                child_md = await blocks_to_markdown(children, level + 1)
                md_output += child_md
                
        elif btype == "bulleted_list_item":
            text = rich_text_to_md(block["bulleted_list_item"]["rich_text"])
            md_output += f"\n{indent}- {text}"
            
        elif btype == "numbered_list_item":
            text = rich_text_to_md(block["numbered_list_item"]["rich_text"])
            md_output += f"\n{indent}1. {text}"
            
        elif btype == "divider":
            md_output += f"\n{indent}---\n"

    return md_output

import httpx

async def fetch_todays_pages():
    """Fetch pages from Notion DB created/dated today using direct HTTP"""
    today_str = date.today().isoformat()
    
    print(f"🔍 Searching for pages with Date: {today_str}", flush=True)
    
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    payload = {
        "filter": {
            "property": "Date",
            "date": {
                "equals": today_str
            }
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"[ERR] Query failed: {response.text}", flush=True)
            return []
        data = response.json()
        return data.get("results", [])

async def main():
    print(f"🚀 Starting Export to NotebookLM...", flush=True)
    
    pages = await fetch_todays_pages()
    if not pages:
        print("⚠️ No news pages found for today.", flush=True)
        return

    today_str = date.today().isoformat()
    full_md_content = f"# 🗞️ Raphael's Tech News Briefing - {today_str}\n\n"
    full_md_content += f"**Source Count**: {len(pages)} reports\n"
    full_md_content += f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n"
    
    for page in pages:
        # Get Title
        props = page["properties"]
        title_prop = props.get("Name", {}).get("title", [])
        title = title_prop[0]["plain_text"] if title_prop else "Untitled"
        
        print(f"  - Processing: {title}", flush=True)
        
        full_md_content += f"\n# {title}\n"
        
        # Get content blocks
        blocks = await get_block_children(page["id"])
        page_md = await blocks_to_markdown(blocks)
        
        full_md_content += page_md
        full_md_content += "\n\n---\n"

    # Save to file
    filename = f"{today_str}_News_Briefing.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(full_md_content)
        
    print(f"✅ Export completed: {filepath}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
