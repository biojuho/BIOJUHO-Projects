#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity Daily News Runner
시간 기반 뉴스 추출: 07:00, 18:00 실행
"""

import os
import sys
import json
import asyncio
import time
import feedparser
from datetime import datetime, date, timedelta
from dateutil import parser as date_parser
from dotenv import load_dotenv

# Windows 터미널 UTF-8 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# 환경 변수 로드
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
load_dotenv(os.path.join(parent_dir, ".env"))

# 모듈 임포트
from brain_module import BrainModule
from generate_infographic import create_news_card
from notion_client import AsyncClient

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NEWS_DB_ID = "9a372e84-8883-421f-8725-d90a494aca5a"

def get_extraction_window():
    """현재 시간에 따른 추출 시간 범위 반환"""
    now = datetime.now()
    hour = now.hour
    
    if 6 <= hour < 8:  # 07:00 근처 (06:00-08:00)
        # 전날 18:00 ~ 오늘 07:00
        start = now.replace(hour=18, minute=0, second=0) - timedelta(days=1)
        end = now.replace(hour=7, minute=0, second=0)
        window_name = "morning"
    elif 17 <= hour < 19:  # 18:00 근처 (17:00-19:00)
        # 오늘 07:00 ~ 18:00
        start = now.replace(hour=7, minute=0, second=0)
        end = now.replace(hour=18, minute=0, second=0)
        window_name = "evening"
    else:
        return None, None, None
    
    return start, end, window_name

def is_within_window(published_time, start, end):
    """기사 발행 시간이 추출 범위 내인지 확인"""
    if not published_time:
        return True  # 시간 정보 없으면 포함
    
    try:
        if isinstance(published_time, str):
            pub_dt = date_parser.parse(published_time)
        else:
            pub_dt = datetime(*published_time[:6])
        
        # timezone naive 로 변환
        if pub_dt.tzinfo:
            pub_dt = pub_dt.replace(tzinfo=None)
        
        return start <= pub_dt <= end
    except:
        return True  # 파싱 실패시 포함

def load_news_sources():
    """뉴스 소스 설정 로드"""
    config_path = os.path.join(parent_dir, "config", "news_sources.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_news_from_feed(url: str, limit: int = 10, start=None, end=None) -> list:
    """RSS 피드에서 뉴스 가져오기 (시간 필터링 적용)"""
    try:
        feed = feedparser.parse(url)
        articles = []
        
        for entry in feed.entries:
            # 발행 시간 확인
            published = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
            
            # 시간 범위 필터링
            if start and end:
                if not is_within_window(published, start, end):
                    continue
            
            articles.append({
                "title": entry.title,
                "description": getattr(entry, 'description', '')[:300] if hasattr(entry, 'description') else '',
                "link": entry.link,
                "published": published
            })
            
            if len(articles) >= limit:
                break
        
        return articles
    except Exception as e:
        print(f"  [Error] Feed fetch failed: {e}")
        return []

def log_extraction(window_name, start, end, article_count):
    """추출 로그 기록"""
    log_dir = os.path.join(parent_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"extraction_{date.today()}.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {window_name.upper()} extraction\n")
        f.write(f"  Range: {start} ~ {end}\n")
        f.write(f"  Articles: {article_count}\n\n")

async def upload_to_notion(category: str, analysis: dict, notion: AsyncClient):
    """분석 결과를 Notion에 업로드"""
    today_str = date.today().isoformat()
    
    # Summary와 Insight를 Description으로 합침
    summary_text = "\n".join([f"• {p}" for p in analysis.get("summary", [])[:3]])
    insight_text = analysis.get("insight", "")
    description = f"[Summary]\n{summary_text}\n\n[Insight]\n{insight_text}"
    
    # Notion 페이지 생성
    try:
        await notion.pages.create(
            parent={"database_id": NEWS_DB_ID},
            properties={
                "Name": {"title": [{"text": {"content": f"{category} Daily Report - {today_str}"}}]},
                "Date": {"date": {"start": today_str}},
                "Description": {"rich_text": [{"text": {"content": description[:2000]}}]},
                "Source": {"select": {"name": "Mixed"}},
            }
        )
        print(f"  [Upload] Notion report saved for '{category}'")
    except Exception as e:
        print(f"  [Error] Notion upload failed: {e}")

async def run_daily_news(force=False):
    """메인 실행 함수"""
    # 시간 범위 확인
    start, end, window_name = get_extraction_window()
    
    # Force 모드: 시간 체크 무시, 최근 24시간 기사 수집
    if force or "--force" in sys.argv:
        now = datetime.now()
        start = now - timedelta(hours=24)
        end = now
        window_name = "test"
        print("[FORCE MODE] 시간 체크 무시, 최근 24시간 기사 수집")
    elif not window_name:
        print("추출 시간대가 아닙니다.")
        print(f"현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("추출 시간: 07:00 (06:00-08:00), 18:00 (17:00-19:00)")
        return
    
    print(f"===== Antigravity Daily News ({date.today()}) =====")
    print(f"[{window_name.upper()}] Range: {start.strftime('%m-%d %H:%M')} ~ {end.strftime('%m-%d %H:%M')}")
    print()
    
    news_sources = load_news_sources()
    brain = BrainModule()
    notion = AsyncClient(auth=NOTION_API_KEY)
    
    results = {}
    total_articles = 0
    x_posts = []
    
    for category, sources in news_sources.items():
        print(f"[{category}] Processing...")
        all_articles = []
        
        for source in sources:
            print(f"  - Fetching {source['name']}...")
            articles = fetch_news_from_feed(source["url"], limit=5, start=start, end=end)
            all_articles.extend(articles)
            print(f"    {len(articles)} articles found (in time range)")
        
        if not all_articles:
            print(f"  [Skip] No articles for '{category}' in time range")
            continue
        
        total_articles += len(all_articles)
        
        # 2. AI 분석
        print(f"  [AI] Analyzing with Claude...")
        analysis = brain.analyze_news(category, all_articles[:7])
        
        if analysis:
            results[category] = analysis
            print(f"  [Done] Analysis complete")
            
            # Rate limit 방지: 3초 대기
            time.sleep(3)
            
            # 3. 인포그래픽 생성
            img_path = os.path.join(parent_dir, "output", f"infographic_{category}_{date.today()}_{window_name}.png")
            try:
                create_news_card(
                    category=category,
                    summary=analysis.get("summary", []),
                    insight=analysis.get("insight", ""),
                    output_path=img_path
                )
                print(f"  [Image] Infographic saved: {img_path}")
            except Exception as e:
                print(f"  [Error] Infographic failed: {e}")
            
            # 4. Notion 업로드
            await upload_to_notion(category, analysis, notion)
            
            # X 포스트 수집
            if analysis.get("x_post"):
                x_posts.append(f"=== {category} ===\n{analysis['x_post']}")
    
    # 5. X 포스트 저장
    if x_posts:
        tweets_path = os.path.join(parent_dir, "output", f"daily_tweets_{date.today()}_{window_name}.txt")
        with open(tweets_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(x_posts))
        print(f"\n[Save] X posts saved: {tweets_path}")
    
    # 6. 로그 기록
    log_extraction(window_name, start, end, total_articles)
    
    print(f"[Save] {len(results)} categories processed, {total_articles} total articles")
    print("\n===== Complete =====")

if __name__ == "__main__":
    asyncio.run(run_daily_news())
