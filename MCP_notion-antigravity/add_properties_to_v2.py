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

async def add_properties():
    if not NOTION_API_KEY:
        print("API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    print(f"Adding 'Date' property to V2 DB: {ANTIGRAVITY_DB_ID}...")
    
    try:
        updated_db = await notion.databases.update(
            database_id=ANTIGRAVITY_DB_ID,
            properties={
                "Date": {"date": {}}
            }
        )
        print("[SUCCESS] Update called.")
        print("Response properties keys:")
        # Check if properties exist in response
        props = updated_db.get("properties", {})
        print(list(props.keys()))
        
        if "Date" in props:
            print("Verified: Date property exists!")
        else:
            print("Verified: Date property MISSING!")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(add_properties())
