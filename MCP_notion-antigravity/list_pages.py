import os
import asyncio
from dotenv import load_dotenv
from notion_client import AsyncClient

# 환경 변수 로드
load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")

async def list_all_pages():
    if not NOTION_API_KEY:
        print("API Key가 없습니다.")
        return

    notion = AsyncClient(auth=NOTION_API_KEY)
    
    try:
        # 빈 쿼리로 검색하면 최근 페이지들을 가져옵니다.
        response = await notion.search(query="", page_size=10)
        results = response.get("results", [])
        
        if not results:
            print("발견된 페이지가 없습니다. 봇이 초대가 되었는지 확인해주세요!")
            return

        print(f"총 {len(results)}개의 페이지/데이터베이스를 찾았습니다 (상위 10개):")
        for i, page in enumerate(results, 1):
            # 제목 찾기
            title = "제목 없음"
            if page["object"] == "page":
                if "properties" in page:
                    for prop in page["properties"].values():
                        if prop["type"] == "title":
                            t_list = prop.get("title", [])
                            if t_list:
                                title = t_list[0].get("plain_text", "제목 없음")
                            break
            elif page["object"] == "database":
                t_list = page.get("title", [])
                if t_list:
                    title = t_list[0].get("plain_text", "제목 없음")
                else:
                    title = "제목 없는 데이터베이스"

            print(f"{i}. [{page['object'].upper()}] {title} (ID: {page['id']})")
            
    except Exception as e:
        print(f"오류 발생: {str(e)}")

if __name__ == "__main__":
    asyncio.run(list_all_pages())
