import os
import argparse
import asyncio
from datetime import datetime
from notion_client import AsyncClient
from dotenv import load_dotenv

# 환경변수 로드 (.env)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
load_dotenv(os.path.join(parent_dir, ".env"))

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
# Antigravity 뉴스/리서치 데이터베이스 ID
DATABASE_ID = "bb5cf3c8-d2bb-4b8b-a866-ba9ea86f16b7"

def chunk_text(text, limit=1900):
    return [text[i:i+limit] for i in range(0, len(text), limit)]

async def publish_to_notion(title: str, file_path: str):
    print(f"[INFO] Publishing '{title}' to Notion database...")
    if not NOTION_API_KEY:
        print("[ERROR] NOTION_API_KEY missing! Please check your .env file.")
        return
        
    notion = AsyncClient(auth=NOTION_API_KEY)
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"[ERROR] Failed to read report file: {e}")
        return

    # Create Blocks
    children = []
    
    # 텍스트가 너무 길 경우 block 제한에 걸릴 수 있으므로 청크 단위 분할
    chunks = chunk_text(content)
    for chunk in chunks:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": chunk}}]
            }
        })
        
    iso_time = datetime.now().isoformat()
    
    try:
        new_page = await notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties={
                "Name": {"title": [{"text": {"content": title}}]},
                "Date": {"date": {"start": iso_time}},
                # DB 스키마상 Type("Research")과 Priority("High")가 미리 생성되어 있거나 생성이 허용되어 있어야 함
                "Type": {"select": {"name": "News"}},  # News, Research 등 Schema에 등록된 값 사용 권장 (여기서는 News 로컬 환경 안전성 유지)
                "Priority": {"select": {"name": "High"}}
            },
            children=children[:100]  # Notion allows up to 100 blocks per request
        )
        print(f"[SUCCESS] Uploaded Deep Research report to Notion: {new_page['url']}")
    except Exception as e:
        print(f"[ERROR] Failed to upload to Notion: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload Markdown report to Notion")
    parser.add_argument("--title", required=True, help="Title of the research report")
    parser.add_argument("--file", required=True, help="Path to the markdown report file")
    args = parser.parse_args()
    
    asyncio.run(publish_to_notion(args.title, args.file))
