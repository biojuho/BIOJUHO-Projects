import os
import asyncio
import feedparser
import sys
import io
from datetime import date
from dotenv import load_dotenv
from notion_client import AsyncClient

# 윈도우 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

# 환경 변수 로드
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
load_dotenv(os.path.join(parent_dir, ".env"))

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
# Antigravity News Archive ID (V3)
NEWS_DB_ID = "9a372e84-8883-421f-8725-d90a494aca5a"

RSS_FEEDS = {
    "GeekNews": "https://feeds.feedburner.com/geeknews-feed",
    "Hacker News (Top)": "https://news.ycombinator.com/rss",
    "IT World Korea": "https://www.itworld.co.kr/rss/feed/index.php"
}

async def collect_and_upload_news():
    if not NOTION_API_KEY:
        print("[FAIL] API Key missing")
        return

    print("🔍 뉴스를 수집하여 아카이브에 저장합니다...")
    
    today_str = date.today().isoformat()
    notion = AsyncClient(auth=NOTION_API_KEY)
    
    total_articles = 0
    
    for source_name, url in RSS_FEEDS.items():
        try:
            print(f"  - Fetching: {source_name}...")
            feed = feedparser.parse(url)
            
            # 상위 5개 기사만 추출
            for entry in feed.entries[:5]:
                title = entry.title
                link = entry.link
                description = getattr(entry, 'description', '')[:200]  # 요약 내용은 200자 제한
                
                # Link는 Notion에서 2000자 제한 등이 있을 수 있으므로 체크 가능하나, URL type은 보통 수용
                
                try:
                    properties = {
                        "Name": {"title": [{"text": {"content": title}}]},
                        "Date": {"date": {"start": today_str}},
                        "Source": {"select": {"name": source_name}},
                        "Link": {"url": link},
                        "Description": {"rich_text": [{"text": {"content": description}}]}
                    }
                    
                    await notion.pages.create(
                        parent={"database_id": NEWS_DB_ID},
                        properties=properties
                    )
                    print(f"    -> [Saved] {title[:30]}...")
                    total_articles += 1
                    
                except Exception as e:
                    print(f"    -> [Error] Upload failed: {e}")
            
        except Exception as e:
            print(f"  [ERROR] {source_name} 수집 실패: {e}")

    print(f"✅ 총 {total_articles}개의 기사를 'Antigravity News Archive'에 저장했습니다.")

if __name__ == "__main__":
    asyncio.run(collect_and_upload_news())
