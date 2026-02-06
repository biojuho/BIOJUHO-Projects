import os
import asyncio
import sys
import io
from dotenv import load_dotenv
from notion_client import AsyncClient

# 윈도우 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

# 환경 변수 로드
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
load_dotenv(os.path.join(parent_dir, ".env"))

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
PARENT_PAGE_ID = "2fe90544-c198-802a-92c2-f918fdc7a431"

async def create_news_db_v3():
    if not NOTION_API_KEY:
        print("[FAIL] API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    # Emoji 제거 (인코딩 이슈 방지용)
    print("Creating 'Antigravity News Archive V3'...")

    try:
        new_db = await notion.databases.create(
            parent={"type": "page_id", "page_id": PARENT_PAGE_ID},
            title=[{
                "type": "text",
                "text": {"content": "Antigravity News Archive V3"}
            }],
            properties={
                "Name": {"title": {}},
                "Date": {"date": {}},
                "Description": {"rich_text": {}}, 
                "Link": {"url": {}}, 
                "Source": { 
                    "select": {
                        "options": [
                            {"name": "GeekNews", "color": "blue"},
                            {"name": "Hacker News", "color": "orange"},
                            {"name": "IT World Korea", "color": "green"},
                            {"name": "Mixed", "color": "gray"} 
                        ]
                    }
                }
            }
        )
        print(f"✅ [SUCCESS] New Database Created!")
        print(f"ID: {new_db['id']}")
        print(f"URL: {new_db['url']}")
        
    except Exception as e:
        print(f"❌ [FAIL] Creation Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(create_news_db_v3())
