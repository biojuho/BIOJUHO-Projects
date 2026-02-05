import os
import asyncio
from dotenv import load_dotenv
from notion_client import AsyncClient
import sys
import io

# 윈도우 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
ANTIGRAVITY_DB_ID = "0c959762-2880-4dc4-8c06-69bbaa8be183"

async def update_schema_v2():
    if not NOTION_API_KEY:
        print("[FAIL] API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    print(f"Adding new properties to DB: {ANTIGRAVITY_DB_ID}...")
    
    try:
        updated_db = await notion.databases.update(
            database_id=ANTIGRAVITY_DB_ID,
            properties={
                "Date": {
                    "date": {}
                },
                "Goal": {
                    "rich_text": {}
                },
                "Achievement": {
                    "rich_text": {}
                }
            }
        )
        import json
        print("[SUCCESS] Schema update called.")
        print("Response from Notion:")
        print(json.dumps(updated_db, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"[FAIL] Error updating schema: {str(e)}")

if __name__ == "__main__":
    asyncio.run(update_schema_v2())
