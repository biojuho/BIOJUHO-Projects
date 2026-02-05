import os
import asyncio
from dotenv import load_dotenv
from notion_client import AsyncClient

# 환경 변수 로드
load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")

async def test_connection():
    print(f"Testing with API Key: {NOTION_API_KEY[:4]}...{NOTION_API_KEY[-4:] if NOTION_API_KEY else 'None'}")
    
    if not NOTION_API_KEY:
        print("[FAIL] NOTION_API_KEY not found in .env")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    try:
        # 사용자 정보 조회 (가장 기본적인 권한 테스트)
        users = await notion.users.list()
        print("[SUCCESS] Successfully connected to Notion API!")
        print(f"Found {len(users.get('results', []))} users visible to this integration.")
        
        # 검색 테스트
        print("Testing search capability...")
        response = await notion.search(page_size=1)
        results = response.get("results", [])
        if results:
            first_page = results[0]
            print(f"[SUCCESS] Search works! Found page/db ID: {first_page['id']}")
        else:
            print("[WARNING] Search returned no results. Make sure the integration is invited to at least one page.")
            
    except Exception as e:
        print(f"[FAIL] Connection failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_connection())
