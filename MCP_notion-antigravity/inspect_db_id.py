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
# DB_ID = "0c959762-2880-4dc4-8c06-69bbaa8be183" # Old V1
DB_ID = "bb5cf3c8-d2bb-4b8b-a866-ba9ea86f16b7" # New V2

async def inspect_db():
    if not NOTION_API_KEY:
        print("API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    try:
        print(f"Retrieving Database ID: {DB_ID}...")
        db = await notion.databases.retrieve(database_id=DB_ID)
        
        import json
        # print(json.dumps(db, indent=2)) # 전체 출력은 너무 길 수 있으니 properties만 확인
        # 하지만 지금 properties가 안 나오니 전체를 봐야 함
        print(json.dumps(db, indent=2, ensure_ascii=False))
             
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_db())
