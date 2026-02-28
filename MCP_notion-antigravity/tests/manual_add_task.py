import os
import asyncio
from dotenv import load_dotenv
from notion_client import AsyncClient

# 환경 변수 로드
load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
ANTIGRAVITY_DB_ID = "0c959762-2880-4dc4-8c06-69bbaa8be183"

async def run_add_task():
    if not NOTION_API_KEY:
        print("[FAIL] API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    print("Testing add_task functionality...")
    
    try:
        new_page = await notion.pages.create(
            parent={"database_id": ANTIGRAVITY_DB_ID},
            properties={
                "Title": {
                    "title": [{"text": {"content": "MCP 연동 테스트 (자동 생성)"}}]
                },
                "Type": {"select": {"name": "Task"}},
                "Status": {"select": {"name": "In Progress"}},
                "Priority": {"select": {"name": "🔥 High"}}
            }
        )
        print(f"[SUCCESS] Test task created!")
        print(f"URL: {new_page['url']}")
        
    except Exception as e:
        print(f"[FAIL] Error creating task: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_add_task())
