import os
import asyncio
import sys
import io
from notion_client import AsyncClient
from dotenv import load_dotenv

# 윈도우 콘솔 인코딩 호환성 설정
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

# Load Environment Variables
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
load_dotenv(os.path.join(parent_dir, ".env"))

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = "bb5cf3c8-d2bb-4b8b-a866-ba9ea86f16b7"  # Same as news_bot.py

async def check_recent_pages():
    if not NOTION_API_KEY:
        print("Error: NOTION_API_KEY not found.")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    try:
        print(f"Searching for pages in Database ID: {DATABASE_ID}...")
        # Fallback to search if query fails, or maybe just verify the ID existence first
        response = await notion.search(
            query="",
            filter={"value": "page", "property": "object"},
            sort={"direction": "descending", "timestamp": "last_edited_time"},
            page_size=5
        )
        
        results = response.get("results", [])
        print(f"\nFound {len(results)} recent pages (global search):")
        
        for page in results:
            parent = page.get("parent", {})
            parent_type = parent.get("type")
            parent_id = parent.get(parent_type)
            
            title_prop = page["properties"].get("Name", {}).get("title", [])
            title = title_prop[0]["text"]["content"] if title_prop else "No Title"
            url = page["url"]
            print(f"- [{title}]({url}) (Parent: {parent_type} {parent_id})")
            
    except Exception as e:
        print(f"Error querying Notion: {e}")

if __name__ == "__main__":
    asyncio.run(check_recent_pages())
