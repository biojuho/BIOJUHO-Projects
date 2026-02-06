import os
import json
import asyncio
import feedparser
import google.generativeai as genai
from datetime import datetime, date
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
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Initialize Clients
if NOTION_API_KEY:
    notion = AsyncClient(auth=NOTION_API_KEY)
else:
    print("[WARN] Notion API Key missing!")
    notion = None

if GOOGLE_API_KEY:
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

async def upload_to_notion(category, articles, analysis=None):
    """Upload summarized news and analysis to Notion"""
    if not notion:
        return

    today_str = date.today().isoformat()
    children = []
    
    # 1. Header
    children.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [{"text": {"content": f"📰 {category} News Brief"}}]}
    })

    # 2. AI Insight (If available)
    if analysis:
        # Insight Callout
        children.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"emoji": "🧠"},
                "rich_text": [
                    {"text": {"content": "💡 Insight: ", "annotations": {"bold": True}}},
                    {"text": {"content": analysis.get('insight', 'No insight available.')}}
                ]
            }
        })
        
        # X Post Draft
        children.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"emoji": "🐦"},
                "color": "blue_background",
                "rich_text": [
                    {"text": {"content": "X Post Draft:\n", "annotations": {"bold": True}}},
                    {"text": {"content": analysis.get('x_post', '')}}
                ]
            }
        })
        
        children.append({"object": "block", "type": "divider", "divider": {}})
    
    # 3. Individual Articles
    for article in articles:
        children.append({
            "object": "block", 
            "type": "heading_3", 
            "heading_3": {"rich_text": [{"text": {"content": article['title'][:100]}}]}
        })
        
        # Link
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {"content": "Source Link", "link": {"url": article['link']}}}]}
        })
        
        # Summary bullets
        summary_lines = article['summary'].split('\n')
        for line in summary_lines:
            line = line.strip().lstrip('-').strip()
            if line:
                children.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": [{"text": {"content": line}}]}
                })
        
        children.append({"object": "block", "type": "divider", "divider": {}})

    # Create Page
    try:
        new_page = await notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties={
                "Name": {"title": [{"text": {"content": f"[{category}] Daily News - {today_str}"}}]},
                "Date": {"date": {"start": today_str}},
                "Type": {"select": {"name": "News"}},
                "Priority": {"select": {"name": "Medium"}}
            },
            children=children
        )
        print(f"[SUCCESS] Uploaded {category} news to Notion: {new_page['url']}")
    except Exception as e:
        print(f"[FAIL] Upload failed for {category}: {e}")

async def process_category(category, feeds):
    print(f"Processing {category}...")
    articles = []
    
    # 1. Fetch & Summarize Items
    for source in feeds:
        try:
            print(f"  Fetching {source['name']}...")
            feed = feedparser.parse(source['url'])
            
            for entry in feed.entries[:2]: # Top 2 per source
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
    if brain:
        print(f"  🧠 Analyzing {category} with BrainModule...")
        # Prepare lightweight list for Brain
        brain_input = [{"title": a["title"], "description": a["description"]} for a in articles]
        analysis = brain.analyze_news(category, brain_input)
    
    # 3. Upload
    await upload_to_notion(category, articles, analysis)

async def main():
    print("=== Starting Notion News Bot (with AI) ===")
    sources = load_sources()
    
    tasks = []
    for category, feeds in sources.items():
        tasks.append(process_category(category, feeds))
    
    await asyncio.gather(*tasks)
    print("=== Completed ===")

if __name__ == "__main__":
    asyncio.run(main())
