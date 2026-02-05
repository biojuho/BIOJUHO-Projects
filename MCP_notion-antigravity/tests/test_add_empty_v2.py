import os
import asyncio
from dotenv import load_dotenv
from notion_client import AsyncClient
import sys
import io
import json

# 윈도우 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
ANTIGRAVITY_DB_ID = "bb5cf3c8-d2bb-4b8b-a866-ba9ea86f16b7"

async def test_add_empty_and_inspect():
    if not NOTION_API_KEY:
        print("API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    print("Creating empty page in V2 DB...")
    
    try:
        # 1. 빈 페이지 생성 (속성 없이)
        new_page = await notion.pages.create(
            parent={"database_id": ANTIGRAVITY_DB_ID},
            properties={} 
        )
        print(f"Empty page created: {new_page['id']}")
        
        # 2. 생성된 페이지 조회하여 속성 확인
        print("Retrieving page properties...")
        page_info = await notion.pages.retrieve(page_id=new_page['id'])
        
        print("Page Properties Structure:")
        print(json.dumps(page_info.get("properties", {}), indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_add_empty_and_inspect())
