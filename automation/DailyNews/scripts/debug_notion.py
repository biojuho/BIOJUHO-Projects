import os
import asyncio
from dotenv import load_dotenv
from notion_client import AsyncClient

# Environment Setup
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
load_dotenv(os.path.join(parent_dir, ".env"))

NOTION_API_KEY = os.getenv("NOTION_API_KEY")

async def main():
    notion = AsyncClient(auth=NOTION_API_KEY)
    print("Notion Client:", notion)
    print("Notion Databases Endpoint:", notion.databases)
    print("Dir(notion.databases):", dir(notion.databases))
    
    # Try calling list (deprecated but maybe exists?)
    # Try calling query
    try:
        print("Function query:", notion.databases.query)
    except AttributeError as e:
        print("Error accessing query:", e)

if __name__ == "__main__":
    asyncio.run(main())
