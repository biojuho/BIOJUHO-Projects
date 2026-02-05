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

async def add_idea():
    if not NOTION_API_KEY:
        print("[FAIL] API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    title = "AI 에이전트 디자인 개선"
    # 현재 Name 속성만 활성화되어 있으므로 제목에 태그를 함께 적어줍니다.
    full_title = f"[Idea] {title}"
    
    print(f"Adding idea: {full_title}...")
    
    try:
        new_page = await notion.pages.create(
            parent={"database_id": ANTIGRAVITY_DB_ID},
            properties={
                "Name": {
                    "title": [{"text": {"content": full_title}}]
                }
            }
        )
        print(f"[SUCCESS] Saved!")
        print(f"URL: {new_page['url']}")
        
    except Exception as e:
        print(f"[FAIL] Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(add_idea())
