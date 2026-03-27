from notion_client import Client, AsyncClient
import asyncio

async def check():
    notion = AsyncClient(auth="secret_dummy")
    print(f"AsyncClient.databases attributes: {dir(notion.databases)}")
    print(f"Client.databases attributes: {dir(Client(auth='dummy').databases)}")

if __name__ == "__main__":
    asyncio.run(check())
