import os
import asyncio
import sys
import io
import argparse
from datetime import date
from dotenv import load_dotenv
from notion_client import AsyncClient

# 윈도우 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

# 환경 변수 로드 (상위 디렉토리의 .env 파일 참조)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
load_dotenv(os.path.join(parent_dir, ".env"))

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
ANTIGRAVITY_DB_ID = "bb5cf3c8-d2bb-4b8b-a866-ba9ea86f16b7"

async def log_update(title, goal, achievement, content, type_val, priority):
    if not NOTION_API_KEY:
        print("[FAIL] API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    today_str = date.today().isoformat()
    
    # 본문 내용을 블록으로 변환
    children_blocks = []
    for line in content.split('\\n'): # 줄바꿈 문자 처리
        line = line.strip()
        if not line: continue
        if line.startswith("# "):
            children_blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": [{"text": {"content": line[2:]}}]}})
        elif line.startswith("## "):
            children_blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": line[3:]}}]}})
        elif line.startswith("- "):
             children_blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"text": {"content": line[2:]}}]}})
        else:
            children_blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": line}}]}})

    try:
        properties = {
            "Name": {"title": [{"text": {"content": title}}]},
            "Date": {"date": {"start": today_str}},
            "Goal": {"rich_text": [{"text": {"content": goal}}]},
            "Achievement": {"rich_text": [{"text": {"content": achievement}}]},
            "Type": {"select": {"name": type_val}},
            "Priority": {"select": {"name": priority}}
        }
        
        new_page = await notion.pages.create(
             parent={"database_id": ANTIGRAVITY_DB_ID},
             properties=properties,
             children=children_blocks
        )
        print(f"[SUCCESS] Log saved to Notion!")
        print(f"URL: {new_page['url']}")
        
    except Exception as e:
        print(f"[FAIL] Error: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Log daily update to Notion")
    parser.add_argument("--title", required=True, help="Log Title")
    parser.add_argument("--goal", required=True, help="Main Goal")
    parser.add_argument("--achievement", required=True, help="Key Achievement")
    parser.add_argument("--content", required=True, help="Detailed Content (use \\n for newlines)")
    parser.add_argument("--type", default="Log", help="Log Type (Log, Idea, Bug, etc.)")
    parser.add_argument("--priority", default="Medium", help="Priority (High, Medium, Low)")

    args = parser.parse_args()
    
    asyncio.run(log_update(
        args.title, 
        args.goal, 
        args.achievement, 
        args.content, 
        args.type, 
        args.priority
    ))
