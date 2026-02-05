import os
import asyncio
from dotenv import load_dotenv
from notion_client import AsyncClient

load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
ANTIGRAVITY_DB_ID = "0c959762-2880-4dc4-8c06-69bbaa8be183"

async def test_simple_create():
    if not NOTION_API_KEY:
        print("API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    print("Testing simple page creation (no properties)...")
    
    try:
        # 속성 없이 생성 시도
        new_page = await notion.pages.create(
            parent={"database_id": ANTIGRAVITY_DB_ID},
            properties={}  # 빈 속성
        )
        print(f"[SUCCESS] Page created! URL: {new_page['url']}")
        
    except Exception as e:
        print(f"[FAIL] Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_simple_create())
