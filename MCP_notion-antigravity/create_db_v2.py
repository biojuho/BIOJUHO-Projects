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
PARENT_PAGE_ID = "2fe90544-c198-802a-92c2-f918fdc7a431"

async def create_db_v2():
    if not NOTION_API_KEY:
        print("API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    print("Creating new database 'Antigravity Tasks & Logs V2'...")
    
    try:
        new_db = await notion.databases.create(
            parent={"type": "page_id", "page_id": PARENT_PAGE_ID},
            title=[
                {
                    "type": "text",
                    "text": {"content": "Antigravity Tasks & Logs V2 (Full Schema)"}
                }
            ],
            properties={
                "Name": {
                    "title": {}
                },
                "Date": {
                    "date": {}
                },
                "Goal": {
                    "rich_text": {}
                },
                "Achievement": {
                    "rich_text": {}
                },
                # 기본 옵션들도 미리 넣어둠
                "Type": {
                    "select": {
                        "options": [
                            {"name": "Task", "color": "blue"},
                            {"name": "Idea", "color": "yellow"},
                            {"name": "Log", "color": "gray"},
                            {"name": "Bug", "color": "red"}
                        ]
                    }
                },
                "Priority": {
                    "select": {
                        "options": [
                            {"name": "🔥 High", "color": "red"},
                            {"name": "⚡ Medium", "color": "yellow"},
                            {"name": "☕ Low", "color": "gray"}
                        ]
                    }
                }
            }
        )
        print(f"Database Created: {new_db['id']}")
        print(f"URL: {new_db['url']}")
        
    except Exception as e:
        print(f"Error creating DB: {e}")

if __name__ == "__main__":
    asyncio.run(create_db_v2())
