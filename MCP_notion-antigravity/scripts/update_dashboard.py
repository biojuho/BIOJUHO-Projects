
import os
import sys
import io
import asyncio
import json
from datetime import date
from notion_client import AsyncClient
from dotenv import load_dotenv

# Force UTF-8 for Windows Console
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Load Environment Variables
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
load_dotenv(os.path.join(parent_dir, ".env"))

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = "bb5cf3c8-d2bb-4b8b-a866-ba9ea86f16b7" 
CONFIG_FILE = os.path.join(parent_dir, "config", "dashboard_config.json")

# Ensure config directory exists
os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

if not NOTION_API_KEY:
    print("[ERROR] Notion API Key not found.")
    sys.exit(1)

notion = AsyncClient(auth=NOTION_API_KEY)

async def get_or_create_dashboard():
    """Find existing dashboard page or create a new one"""
    # 1. Check config file
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                page_id = config.get("dashboard_page_id")
                if page_id:
                    # Verify if it still exists
                    try:
                        await notion.pages.retrieve(page_id)
                        return page_id
                    except:
                        print("[WARN] Stored Dashboard ID invalid. Creating new one.")
        except:
            pass

    # 2. Search by Title
    response = await notion.search(query="Antigravity Newsroom", filter={"property": "object", "value": "page"})
    if response["results"]:
        page_id = response["results"][0]["id"]
        save_config(page_id)
        return page_id

    # 3. Create New Page (Notion API requires a parent. We will use the DATABASE parent? No, pages cannot be parent unless it's a page itself. 
    # Actually, we usually create pages under a parent page or just in a workspace.
    # But Notion API requires a specific parent (page_id or database_id).
    # Since we don't have a Root Page ID, maybe we create it as a child of the Database? No, that makes it a database item.
    # We must ask the user for a ROOT_PAGE_ID or just create it in the database but mark it differently?
    # Let's create it inside the News Database for now, but with a special "Dashboard" type/tag?
    # Actually, the user can move it later. Let's create it in the Database but pinned/styled differently.
    
    print("✨ Creating new Dashboard Page...")
    new_page = await notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties={
            "Name": {"title": [{"text": {"content": "Antigravity Newsroom"}}]},
            "Type": {"select": {"name": "Dashboard"}}, # Tag it
            "Date": {"date": {"start": date.today().isoformat()}}
        },
        icon={"emoji": "📰"},
        cover={"type": "external", "external": {"url": "https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=2070&auto=format&fit=crop"}}
    )
    
    page_id = new_page["id"]
    save_config(page_id)
    return page_id

def save_config(page_id):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"dashboard_page_id": page_id}, f)

async def update_dashboard(page_id):
    print(f"🔄 Updating Dashboard (ID: {page_id})...")
    
    # 1. Calculate Stats
    today_str = date.today().isoformat()
    # Need to query today's articles first
    # (Reusing query logic roughly)
    import httpx
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    payload = {
        "filter": {
            "and": [
                {"property": "Date", "date": {"equals": today_str}},
                {"property": "Type", "select": {"does_not_equal": "Dashboard"}} # Exclude itself
            ]
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        data = response.json()
        articles = data.get("results", [])
    count = len(articles)
    
    # Analyze categories
    categories = {}
    for p in articles:
        # Extract title to guess category or check properties if available
        # news_bot puts category in Title: [Tech] ...
        props = p["properties"]
        title = props.get("Name", {}).get("title", [])[0]["plain_text"]
        
        # Simple extraction
        import re
        match = re.search(r"\[(.*?)\]", title)
        cat = match.group(1) if match else "Uncategorized"
        categories[cat] = categories.get(cat, 0) + 1
        
    cat_summary = " | ".join([f"{k}: {v}" for k, v in categories.items()])
    
    # 2. Clear Page Content (Delete all blocks)
    # Be careful not to delete linked databases if we had them! 
    # For MVP, we rebuild the "Heads Up" section.
    # Actually, replacing children is better.
    
    # Let's append if empty, or just append a "Daily Update" block at the TOP?
    # Notion API allows 'append', but 'replace' requires deleting first.
    
    # Strategy: Just append a new "Daily Briefing" toggle block with the stats at the top.
    # Or overwrite the whole page content to look like a real dashboard.
    # Let's overwrite safely: listing children and deleting them is slow.
    # Instead, let's just Add a "fresh" status block at the top if possible?
    # Notion API inserts at bottom by default.
    # To insert at top, we need `after` parameter which requires a block ID.
    
    # For MVP: We will Append a new "Day Summary" block.
    
    children = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": f"📅 {today_str} Daily Status"}}]}
        },
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"emoji": "📊"},
                "color": "blue_background",
                "rich_text": [
                    {"text": {"content": f"Total Articles: {count}\n"}},
                    {"text": {"content": f"Breakdown: {cat_summary}"}}
                ]
            }
        },
        {
            "object": "block",
            "type": "divider",
            "divider": {}
        }
    ]
    
    await notion.blocks.children.append(block_id=page_id, children=children)
    print("✅ Dashboard updated.")

async def main():
    page_id = await get_or_create_dashboard()
    await update_dashboard(page_id)

if __name__ == "__main__":
    asyncio.run(main())
