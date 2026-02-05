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
DB_ID = "0c959762-2880-4dc4-8c06-69bbaa8be183"

async def update_schema():
    if not NOTION_API_KEY:
        print("API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    try:
        print(f"Updating schema for DB: {DB_ID}...")
        
        updated_db = await notion.databases.update(
            database_id=DB_ID,
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
        print("[SUCCESS] Schema updated!")
        
    except Exception as e:
        print(f"[FAIL] Error updating schema: {str(e)}")

if __name__ == "__main__":
    asyncio.run(update_schema())
