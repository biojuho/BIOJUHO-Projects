import os
import json
import asyncio
import sys
import io
print("Starting script...", flush=True)

# 윈도우 콘솔 인코딩 호환성 설정
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

import feedparser
import google.generativeai as genai
from datetime import datetime, timedelta, timezone
from dateutil import parser
from collections import Counter
from notion_client import AsyncClient
from dotenv import load_dotenv

# Import BrainModule
try:
    from brain_module import BrainModule
    HAS_BRAIN = True
except ImportError:
    HAS_BRAIN = False
    print("[WARN] BrainModule not found. Skipping AI Insights.")

# Load Environment Variables
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
load_dotenv(os.path.join(parent_dir, ".env"))

# Configurations
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = "bb5cf3c8-d2bb-4b8b-a866-ba9ea86f16b7" 
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Initialize Clients
if NOTION_API_KEY:
    notion = AsyncClient(auth=NOTION_API_KEY)
else:
    print("[WARN] Notion API Key missing!")
    notion = None

if GOOGLE_API_KEY:
    try:
        import google.genai as genai_new
        # Fallback or new usage if needed, but keeping compat for now
    except ImportError:
        pass
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    print("[WARN] Google API Key missing! Summarization will be disabled.")
    model = None

# Initialize Brain
brain = None
if HAS_BRAIN and ANTHROPIC_API_KEY:
    try:
        brain = BrainModule()
        print("[INFO] BrainModule initialized successfully.")
    except Exception as e:
        print(f"[WARN] Failed to init BrainModule: {e}")

# Load Sources
SOURCES_FILE = os.path.join(parent_dir, "config", "news_sources.json")

def load_sources():
    with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_time_window():
    """
    Determine the monitoring time window based on current execution time.
    Morning Run (around 07:00): Yesterday 18:00 ~ Today 07:00
    Evening Run (around 18:00): Today 07:00 ~ Today 18:00
    """
    now = datetime.now()
    
    # Morning Logic (Exec 06:00 ~ 08:00)
    if 6 <= now.hour < 10:
        end_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        start_time = (end_time - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        label = "아침 브리핑"
    # Evening Logic (Exec 17:00 ~ 19:00)
    elif 17 <= now.hour < 20: 
        end_time = now.replace(hour=18, minute=0, second=0, microsecond=0)
        start_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        label = "저녁 브리핑"
    # Default (Manual Run or other times) -> Past 12 hours
    else:
        end_time = now
        start_time = now - timedelta(hours=12)
        label = "속보"
        
    return start_time, end_time, label

def is_in_window(published_parsed, start, end):
    if not published_parsed:
        return True # 날짜 없으면 포함

    # ... (rest of function) ...

async def summarize_article(title, content):
    """Summarize article using Gemini"""
    if not model:
        return content[:300] + "..."
    
    prompt = f"""
    Summarize the following tech/economic news article in 3 bullet points (Korean).
    Focus on facts and impact.
    
    Title: {title}
    Content: {content[:2000]}
    """
    
    try:
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        print(f"[ERR] Summarization failed: {e}")
        return content[:300] + "..."

import market_data # [New] Market Data Module

async def upload_to_notion(category, articles, analysis=None, time_label="News"):
    """Upload summarized news and analysis to Notion"""
    if not notion:
        return

    current_time = datetime.now()
    time_str = current_time.strftime("%Y-%m-%d %H:%M")
    iso_time = current_time.isoformat()
    
    children = []
    
    # 1. Header
    children.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [{"text": {"content": f"📰 {category} {time_label}"}}]}
    })

    # [New] Market Snapshot Injection
    # Combine titles/descriptions to scan for keywords
    combined_text = " ".join([a['title'] for a in articles])
    if analysis and analysis.get("insights"):
        combined_text += " " + " ".join([i.get('topic','') + " " + i.get('insight','') for i in analysis['insights']])
    
    market_snapshot = market_data.get_market_summary(combined_text)
    if market_snapshot:
        children.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"emoji": "💰"},
                "color": "green_background",
                "rich_text": [{"text": {"content": market_snapshot}}]
            }
        })

    # 2. Insights (New Format)
    if analysis and analysis.get("insights"):
        children.append({
            "object": "block", "type": "heading_3", 
            "heading_3": {"rich_text": [{"text": {"content": "🧠 라프의 인사이트 (Raphael's Insights)"}}]}
        })
        
        for insight in analysis["insights"]:
            # Format: Topic | Insight | Importance
            children.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"emoji": "💡"},
                    "color": "gray_background",
                    "rich_text": [
                        {"type": "text", "text": {"content": f"[{insight.get('topic', 'Issue')}] "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": f"{insight.get('insight')} \n"}},
                        {"type": "text", "text": {"content": f"👉 {insight.get('importance')}"}, "annotations": {"italic": True, "color": "blue"}}
                    ]
                }
            })

    # 3. X Thread Draft
    if analysis and analysis.get("x_thread"):
        children.append({
            "object": "block", "type": "heading_3", 
            "heading_3": {"rich_text": [{"text": {"content": "🐦 X 스레드 초안"}}]}
        })
        
        thread_text = "\n\n".join(analysis["x_thread"])
        children.append({
            "object": "block",
            "type": "code",
            "code": {
                "language": "plain text",
                "rich_text": [{"text": {"content": thread_text}}]
            }
        })
        children.append({"object": "block", "type": "divider", "divider": {}})
    
    # 4. Source Distribution (Mermaid Chart)
    # Calculate source stats
    sources = [a.get('source', 'Unknown') for a in articles]
    source_counts = Counter(sources)
    
    # Generate Mermaid Pie Chart Syntax
    mermaid_code = "pie\n    title 뉴스 출처 분포\n"
    for source, count in source_counts.most_common(10):
        # Mermaid syntax clean up (remove quotes if possible, or keep simple)
        safe_source = source.replace('"', '').replace(':', '')
        mermaid_code += f'    "{safe_source}" : {count}\n'

    children.append({
        "object": "block", "type": "heading_3", 
        "heading_3": {"rich_text": [{"text": {"content": "📊 뉴스 출처 분석"}}]}
    })

    children.append({
        "object": "block",
        "type": "code",
        "code": {
            "language": "mermaid",
            "rich_text": [{"text": {"content": mermaid_code}}]
        }
    })

    # 5. Individual Articles
    children.append({
        "object": "block", "type": "heading_3", 
        "heading_3": {"rich_text": [{"text": {"content": "🗞️ 수집된 뉴스"}}]}
    })
    
    for article in articles:
        children.append({
            "object": "block", 
            "type": "toggle", 
            "toggle": {
                "rich_text": [{"text": {"content": article['title'][:100]}}],
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"text": {"content": "원문 링크", "link": {"url": article['link']}}}]}
                    },
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"text": {"content": article['summary'][:2000]}}]}
                    }
                ]
            }
        })

    # Create Page
    try:
        new_page = await notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties={
                "Name": {"title": [{"text": {"content": f"[{category}] {time_label} - {time_str}"}}]},
                "Date": {"date": {"start": iso_time}},
                "Type": {"select": {"name": "News"}},
                "Priority": {"select": {"name": "High" if time_label != "Breaking News" else "Medium"}}
            },
            children=children
        )
        print(f"[SUCCESS] Uploaded {category} news to Notion: {new_page['url']}")
    except Exception as e:
        print(f"[FAIL] Upload failed for {category}: {e}")

async def process_category(category, feeds):
    print(f"Processing {category}...")
    
    start_time, end_time, label = get_time_window()
    window_str = f"{start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}"
    print(f"  🕒 Time Window: {window_str} ({label})")
    
    articles = []
    
    # 1. Fetch & Summarize Items
    for source in feeds:
        try:
            print(f"  Fetching {source['name']}...")
            feed = feedparser.parse(source['url'])
            
            # Filter top 5 (increased from 2 since we filter by relevance/time conceptually, 
            # though strict time filter is disabled for MVP reliability)
            for entry in feed.entries[:5]: 
                content = ""
                if 'summary' in entry:
                    content = entry.summary
                elif 'description' in entry:
                    content = entry.description
                
                summary = await summarize_article(entry.title, content)
                
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "description": content[:200], # For BrainModule
                    "summary": summary # For Notion Display
                })
        except Exception as e:
            print(f"  Error fetching {source['name']}: {e}")

    if not articles:
        print(f"  No articles found for {category}")
        return

    # 2. Analyze with BrainModule (if enabled)
    analysis = None
    analysis = None
    if brain:
        try:
            print(f"  🧠 Analyzing {category} with BrainModule (Raphael)...")
            brain_input = [{"title": a["title"], "description": a["description"]} for a in articles]
            analysis = brain.analyze_news(category, brain_input, time_window=window_str)
        except Exception as e:
            print(f"  [WARN] BrainModule analysis failed for {category}: {e}")
            analysis = None
    
    # 3. Upload
    await upload_to_notion(category, articles, analysis, time_label=label)

async def main():
    print("=== Starting Notion News Bot (Raphael Edition) ===")
    sources = load_sources()
    
    tasks = []
    for category, feeds in sources.items():
        tasks.append(process_category(category, feeds))
    
    await asyncio.gather(*tasks)
    print("=== Completed ===")

if __name__ == "__main__":
    asyncio.run(main())
