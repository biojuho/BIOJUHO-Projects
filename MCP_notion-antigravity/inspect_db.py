import os
import asyncio
from dotenv import load_dotenv
from notion_client import AsyncClient
import json

# 환경 변수 로드
load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")

async def find_database_schema():
    if not NOTION_API_KEY:
        print("API Key가 없습니다.")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    try:
        # 윈도우 콘솔 인코딩 문제 해결을 위해 sys.stdout 재설정
        import sys
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

        print("Searching for 'Antigravity' database...")
        # 필터 없이 검색 후 로직에서 처리
        response = await notion.search(query="Antigravity")
        
        # 데이터베이스 타입만 필터링
        all_results = response.get("results", [])
        results = [item for item in all_results if item["object"] == "database"]

        
        if not results:
            print("[INFO] 'Antigravity' database not found.")
            print("       (Note: Must be a database, not a page.)")
            return

        print(f"[INFO] Found {len(results)} databases.\n")

        for db in results:
            title_list = db.get("title", [])
            title = title_list[0].get("plain_text", "제목 없음") if title_list else "제목 없음"
            db_id = db["id"]
            
            print(f"DB Name: {title}")
            print(f"ID: {db_id}")
            print(f"URL: {db.get('url')}")
            print("Properties:")
            
            properties = db.get("properties", {})
            for prop_name, prop_data in properties.items():
                prop_type = prop_data["type"]
                print(f"    - {prop_name} ({prop_type})")
            print("-" * 40)
            
    except Exception as e:
        print(f"[ERROR]: {str(e)}")

if __name__ == "__main__":
    asyncio.run(find_database_schema())
