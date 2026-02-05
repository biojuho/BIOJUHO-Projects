import os
import asyncio
from dotenv import load_dotenv
from notion_client import AsyncClient
import sys
import io
from datetime import date

# 윈도우 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
ANTIGRAVITY_DB_ID = "bb5cf3c8-d2bb-4b8b-a866-ba9ea86f16b7"

async def test_add_extended_log():
    if not NOTION_API_KEY:
        print("[FAIL] API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    title = "[Full System Check] V2 DB 테스트 ⚡"
    goal = "Notion MCP V2 데이터베이스의 전체 기능 검증"
    achievement = "모든 속성(Date, Goal, Achievement, Type, Priority) 정상 작동 확인!"
    today_str = date.today().isoformat()
    
    content = """
# V2 데이터베이스 검증
새로 생성된 V2 데이터베이스에 모든 속성이 올바르게 매핑되는지 확인합니다.

# 체크리스트
- [x] Name Check
- [x] Date Check (Today)
- [x] Type Check (Log)
- [x] Priority Check (High)
- [x] Goal & Achievement Check
    """
    
    # ... (본문 블록 변환 로직 동일)
    children_blocks = []
    for line in content.split('\n'):
        line = line.strip()
        if not line: continue
        if line.startswith("# "):
            children_blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": [{"text": {"content": line[2:]}}]}})
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
            "Type": {"select": {"name": "Log"}},
            "Priority": {"select": {"name": "🔥 High"}}
        }
        
        new_page = await notion.pages.create(
             parent={"database_id": ANTIGRAVITY_DB_ID},
             properties=properties,
             children=children_blocks
        )
        print(f"[SUCCESS] Extended Log saved to V2 DB!")
        print(f"URL: {new_page['url']}")
        
    except Exception as e:
        print(f"[FAIL] Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_add_extended_log())
