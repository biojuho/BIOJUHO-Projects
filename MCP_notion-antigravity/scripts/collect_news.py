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

import httpx

async def get_existing_urls(notion_client_unused):
    """Fetch all existing URLs from the database to prevent duplicates."""
    existing_urls = set()
    has_more = True
    next_cursor = None
    
    # Direct API Endpoint
    url = f"https://api.notion.com/v1/databases/{NEWS_DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    print("🔍 Checking existing articles for deduplication (via httpx)...")
    
    async with httpx.AsyncClient() as client:
        while has_more:
            try:
                payload = {
                    "page_size": 100,
                    "sorts": [{"property": "Date", "direction": "descending"}]
                }
                if next_cursor:
                    payload["start_cursor"] = next_cursor

                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    print(f"[WARN] API Error: {response.text}")
                    break

                data = response.json()
                
                for page in data.get("results", []):
                    # Handle potential missing properties strictly
                    state = page.get("properties", {}).get("Link", {})
                    url_val = state.get("url")
                    if url_val:
                        existing_urls.add(url_val)
                
                has_more = data.get("has_more", False)
                next_cursor = data.get("next_cursor")
                
                # print(f"DEBUG: Fetched {len(data.get('results', []))} items. Total urls: {len(existing_urls)}")
                
            except Exception as e:
                print(f"[WARN] Failed to fetch existing URLs: {e}")
                break
            
    print(f"📋 Found {len(existing_urls)} existing articles.")
    return existing_urls

async def collect_and_upload_news():
    if not NOTION_API_KEY:
        print("[FAIL] API Key missing")
        return

    print("🔍 뉴스를 수집하여 아카이브에 저장합니다...")
    
    today_str = date.today().isoformat()
    notion = AsyncClient(auth=NOTION_API_KEY)
    
    # 1. Get Existing URLs
    existing_urls = await get_existing_urls(notion)
    
    total_articles = 0
    skipped_articles = 0
    
    for source_name, url in RSS_FEEDS.items():
        try:
            print(f"  - Fetching: {source_name}...")
            feed = feedparser.parse(url)
            
            # 상위 10개 기사만 추출 (범위 확대)
            for entry in feed.entries[:10]:
                title = entry.title
                link = entry.link
                description = getattr(entry, 'description', '')[:200]  # 요약 내용은 200자 제한
                
                # Deduplication Check
                if link in existing_urls:
                    print(f"    -> [Skip] Duplicate: {title[:30]}...")
                    skipped_articles += 1
                    continue
                
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
                    existing_urls.add(link) # Add to set to prevent dups within same run
                    total_articles += 1
                    
                except Exception as e:
                    print(f"    -> [Error] Upload failed: {e}")
            
        except Exception as e:
            print(f"  [ERROR] {source_name} 수집 실패: {e}")

    print(f"✅ 총 {total_articles}개 저장, {skipped_articles}개 중복 제외.")

if __name__ == "__main__":
    asyncio.run(collect_and_upload_news())
