from __future__ import annotations

import asyncio
import json

from notion_client import AsyncClient
from settings import NOTION_API_KEY, NOTION_TASKS_DATABASE_ID


async def main() -> None:
    if not NOTION_API_KEY:
        print("Set NOTION_API_KEY")
        return
    if not NOTION_TASKS_DATABASE_ID:
        print("Set NOTION_TASKS_DATABASE_ID")
        return

    client = AsyncClient(auth=NOTION_API_KEY)
    try:
        response = await client.databases.update(
            database_id=NOTION_TASKS_DATABASE_ID,
            properties={
                "Sentiment": {"select": {}},
                "Entities": {"multi_select": {}},
            },
        )
        print("Response from Notion update:")
        print(json.dumps(response, indent=2, ensure_ascii=False)[:1000])
    except Exception as exc:
        print(f"Failed to update database schema: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
