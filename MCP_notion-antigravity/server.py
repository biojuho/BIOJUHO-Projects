import os
import asyncio
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from notion_client import Client, AsyncClient

# 1. 환경 변수 로드 (.env 파일에서 API 키 가져오기)
# 현재 파일(server.py)의 위치를 기준으로 .env 파일 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, ".env")
load_dotenv(env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")

# Antigravity Tasks & Logs DB ID
ANTIGRAVITY_DB_ID = "0c959762-2880-4dc4-8c06-69bbaa8be183"

# 2. Notion 클라이언트 초기화
if not NOTION_API_KEY:
    raise ValueError("NOTION_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")

notion = AsyncClient(auth=NOTION_API_KEY)

# 3. MCP 서버 생성
mcp = FastMCP("Notion MCP Server")

@mcp.tool()
async def search_notion(query: str) -> str:
    """
    Notion에서 페이지를 검색합니다.
    
    Args:
        query: 검색할 키워드
        
    Returns:
        검색된 페이지들의 제목과 ID 목록 (텍스트 형식)
    """
    try:
        response = await notion.search(query=query, page_size=5)
        results = []
        for page in response.get("results", []):
            # 페이지 제목 추출 (Notion 데이터 구조가 복잡하여 안전하게 처리)
            title = "제목 없음"
            if "properties" in page:
                for prop in page["properties"].values():
                    if prop["type"] == "title":
                        title_list = prop.get("title", [])
                        if title_list:
                            title = title_list[0].get("plain_text", "제목 없음")
                        break
            
            page_id = page["id"]
            url = page.get("url", "")
            results.append(f"- 제목: {title}\n  ID: {page_id}\n  URL: {url}")
            
        if not results:
            return "검색 결과가 없습니다."
            
        return "\n\n".join(results)
        
    except Exception as e:
        return f"검색 중 오류 발생: {str(e)}"

@mcp.tool()
async def read_page(page_id: str) -> str:
    """
    Notion 페이지의 내용을 읽어옵니다.
    
    Args:
        page_id: 읽을 페이지의 ID (search_notion으로 얻은 ID)
        
    Returns:
        페이지의 텍스트 내용
    """
    try:
        # 페이지의 블록(내용)들을 가져옴
        blocks = await notion.blocks.children.list(block_id=page_id)
        
        content = []
        for block in blocks.get("results", []):
            block_type = block["type"]
            
            # 텍스트가 있는 블록만 처리 (Paragraph, Heading, Bulleted List 등)
            if block_type in block and "rich_text" in block[block_type]:
                text_list = block[block_type].get("rich_text", [])
                if text_list:
                    plain_text = "".join([t.get("plain_text", "") for t in text_list])
                    
                    # 블록 타입에 따른 간단한 포맷팅
                    if block_type == "heading_1":
                        content.append(f"# {plain_text}")
                    elif block_type == "heading_2":
                        content.append(f"## {plain_text}")
                    elif block_type == "heading_3":
                        content.append(f"### {plain_text}")
                    elif block_type == "bulleted_list_item":
                        content.append(f"- {plain_text}")
                    elif block_type == "numbered_list_item":
                        content.append(f"1. {plain_text}")
                    else:
                        content.append(plain_text)
            
        if not content:
            return "페이지 내용이 비어있거나 텍스트를 추출할 수 없습니다."
            
        return "\n\n".join(content)
        
    except Exception as e:
        return f"페이지 읽기 중 오류 발생: {str(e)}"
# ANTIGRAVITY_DB_ID = "0c959762-2880-4dc4-8c06-69bbaa8be183" # Old V1
ANTIGRAVITY_DB_ID = "bb5cf3c8-d2bb-4b8b-a866-ba9ea86f16b7" # New V2 (Full Schema)

@mcp.tool()
async def add_task(title: str, content: str = "", type: str = "Task", priority: str = "⚡ Medium",
                   goal: str = "", achievement: str = "") -> str:
    """
    Antigravity 데이터베이스에 새로운 작업, 아이디어, 로그를 추가합니다.

    Args:
        title: 작업 또는 기록의 제목
        content: 상세 내용 (마크다운 지원)
        type: 항목 유형 (Task, Idea, Log, Bug). 기본값 Task.
        priority: 중요도 (🔥 High, ⚡ Medium, ☕ Low). 기본값 ⚡ Medium.
        goal: 목표 (한 줄 요약)
        achievement: 달성 성과 (한 줄 요약)

    Returns:
        추가된 항목의 URL과 결과 메시지
    """
    if not ANTIGRAVITY_DB_ID:
        return "오류: 데이터베이스 ID가 설정되지 않았습니다."
    
    # 1. 날짜는 자동으로 오늘 날짜 사용
    from datetime import datetime, date
    today_str = date.today().isoformat()

    # 입력값 정규화
    type_map = {
        "task": "Task", "할일": "Task",
        "idea": "Idea", "아이디어": "Idea",
        "log": "Log", "기록": "Log", "로그": "Log",
        "bug": "Bug", "버그": "Bug"
    }
    
    priority_map = {
        "high": "🔥 High", "높음": "🔥 High", "상": "🔥 High",
        "medium": "⚡ Medium", "중간": "⚡ Medium", "중": "⚡ Medium",
        "low": "☕ Low", "낮음": "☕ Low", "하": "☕ Low"
    }

    clean_type = type_map.get(type.lower(), type)
    clean_priority = priority_map.get(priority.lower(), priority)

    # 본문(Content) -> Block 변환 로직
    children_blocks = []
    if content:
        for line in content.split('\n'):
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
    try:
        properties = {
            "Name": {"title": [{"text": {"content": title}}]},
            "Date": {"date": {"start": today_str}},
            "Type": {"select": {"name": clean_type}},
            "Priority": {"select": {"name": clean_priority}}
        }

        if goal:
            properties["Goal"] = {"rich_text": [{"text": {"content": goal}}]}
        if achievement:
            properties["Achievement"] = {"rich_text": [{"text": {"content": achievement}}]}
        
        # 페이지 생성 (본문 블록 포함)
        new_page = await notion.pages.create(
            parent={"database_id": ANTIGRAVITY_DB_ID},
            properties=properties,
            children=children_blocks
        )
        
        return f"✅ 성공적으로 추가되었습니다!\n- 제목: {title}\n- 유형: {clean_type}\n- 중요도: {clean_priority}\n- 날짜: {today_str}\n- 목표: {goal}\n- 성과: {achievement}\n- 링크: {new_page['url']}"

    except Exception as e:
        return f"추가 중 오류 발생: {str(e)}"
    
if __name__ == "__main__":
    mcp.run()
