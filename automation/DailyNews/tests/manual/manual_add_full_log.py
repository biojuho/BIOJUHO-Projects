import asyncio
import os
import sys

from dotenv import load_dotenv
from notion_client import AsyncClient

# 윈도우 인코딩 설정
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
ANTIGRAVITY_DB_ID = "0c959762-2880-4dc4-8c06-69bbaa8be183"


async def run_add_full_log():
    if not NOTION_API_KEY:
        print("[FAIL] API Key missing")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)

    title = "[Log] Notion MCP 프로젝트 회고 및 향후 계획 🚀"
    content = """
# 1. 오늘 달성한 성과 ✅
- Notion MCP 서버 환경 설정 (`.env`, `venv`)
- 데이터베이스 생성 (`Antigravity Tasks & Logs`)
- 쓰기 기능 구현 및 `Name` 속성 테스트 완료

# 2. 프로젝트 계획 📅
- 단기: Notion MCP 기능 안정화 및 본문 쓰기 기능 테스트
- 중기: X (Twitter) 트렌드 분석 시스템 구축
- 장기: AI 에이전트와 Notion의 완벽한 협업 시스템 구축

# 3. 향후 방향성 및 제안 🧭
- 단순 기록을 넘어, AI가 스스로 판단하여 중요한 정보를 요약/저장하는 시스템으로 발전
- X 트렌드 분석 결과를 매일 자동으로 이곳에 리포팅하도록 설정
- "친구야, 오늘 뭐 했어?"라고 물으면 이 로그를 기반으로 대답하도록 구현

이 기록은 Antigravity MCP에 의해 자동으로 생성되었습니다.
    """

    print(f"Adding full log: {title}...")

    # 서버 내부 로직을 흉내내어 블록 변환 테스트 (클라이언트 입장에서 직접 호출하는 것이므로)
    children_blocks = []
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.startswith("# "):
            children_blocks.append(
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]},
                }
            )
        elif line.startswith("- "):
            children_blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]},
                }
            )
        else:
            children_blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": line}}]},
                }
            )

    try:
        new_page = await notion.pages.create(
            parent={"database_id": ANTIGRAVITY_DB_ID},
            properties={"Name": {"title": [{"text": {"content": title}}]}},
            children=children_blocks,
        )
        print("[SUCCESS] Full Log saved!")
        print(f"URL: {new_page['url']}")

    except Exception as e:
        print(f"[FAIL] Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(run_add_full_log())
