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
# 방금 생성된 페이지 ID (URL에서 추출 및 하이픈 삽입)
PAGE_ID = "2fe90544-c198-814c-b16d-d2435d3c17be"

async def inspect_page():
    if not NOTION_API_KEY:
        print("API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    try:
        print(f"Retrieving Page ID: {PAGE_ID}...")
        page = await notion.pages.retrieve(page_id=PAGE_ID)
        
        print("Page Properties:")
        # 한글 출력을 위해 ensure_ascii=False
        print(json.dumps(page.get('properties', {}), indent=2, ensure_ascii=False))
             
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_page())
