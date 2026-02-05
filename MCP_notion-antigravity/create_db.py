import os
import asyncio
from dotenv import load_dotenv
from notion_client import AsyncClient
import sys
import io

# 윈도우 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

# 환경 변수 로드
load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")

# Antigravity 이지 ID (이전에 확인한 ID)
PARENT_PAGE_ID = "2fe90544-c198-802a-92c2-f918fdc7a431"

async def create_database():
    if not NOTION_API_KEY:
        print("[ERROR] API Key not found.")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    try:
        print(f"Creating database under page: {PARENT_PAGE_ID}...")
        
        new_db = await notion.databases.create(
            parent={"type": "page_id", "page_id": PARENT_PAGE_ID},
            title=[
                {
                    "type": "text",
                    "text": {
                        "content": "Antigravity Tasks & Logs",
                        "link": None
                    }
                }
            ],
            properties={
                "Title": {"title": {}},
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
                "Status": {
                    "select": {
                        "options": [
                            {"name": "To Do", "color": "red"},
                            {"name": "In Progress", "color": "blue"},
                            {"name": "Done", "color": "green"}
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
        
        print(f"[SUCCESS] Database created successfully!")
        print(f"DB ID: {new_db['id']}")
        print(f"URL: {new_db['url']}")
        
        # 생성된 DB ID를 .env에 저장하면 좋겠지만, 일단 출력만
        return new_db['id']
            
    except Exception as e:
        print(f"[ERROR]: {str(e)}")

if __name__ == "__main__":
    asyncio.run(create_database())
