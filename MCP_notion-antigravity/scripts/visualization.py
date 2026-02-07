import os
import io
import sys
import asyncio
from datetime import date
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
from dotenv import load_dotenv
from notion_client import AsyncClient
from collections import Counter
import re

# Windows encoding fix
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

# Environment Setup
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
load_dotenv(os.path.join(parent_dir, ".env"))

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NEWS_DB_ID = "9a372e84-8883-421f-8725-d90a494aca5a"
OUTPUT_DIR = os.path.join(parent_dir, "output")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

import httpx

async def fetch_todays_news():
    """Fetch news articles from Notion for today using direct API call."""
    if not NOTION_API_KEY:
        print("[FAIL] API Key missing")
        return []

    url = f"https://api.notion.com/v1/databases/{NEWS_DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    today_str = date.today().isoformat()
    
    print(f"🔍 Fetching news for {today_str}...")
    
    payload = {
        "filter": {
            "property": "Date",
            "date": {
                "equals": today_str
            }
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        
        articles = []
        for page in data.get("results", []):
            props = page["properties"]
            title_prop = props.get("Name", {}).get("title", [])
            title = title_prop[0]["text"]["content"] if title_prop else ""
            
            source_prop = props.get("Source", {}).get("select", {})
            source = source_prop.get("name") if source_prop else "Unknown"
            
            articles.append({"title": title, "source": source})
            
        print(f"✅ Fetched {len(articles)} articles.")
        return articles
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch news: {e}")
        import traceback
        traceback.print_exc()
        return []

def generate_visualizations(articles):
    """Generate charts and word clouds from articles."""
    if not articles:
        print("⚠️ No articles to visualize.")
        return

    df = pd.DataFrame(articles)
    
    # 1. Source Distribution Bar Chart
    plt.figure(figsize=(10, 6))
    sns.set_theme(style="whitegrid")
    source_counts = df['source'].value_counts()
    
    ax = sns.barplot(x=source_counts.index, y=source_counts.values, palette="viridis")
    ax.set_title(f"News Source Distribution ({date.today()})", fontsize=15)
    ax.set_ylabel("Count")
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    source_chart_path = os.path.join(OUTPUT_DIR, "source_distribution.png")
    plt.savefig(source_chart_path)
    print(f"📊 Saved source chart to {source_chart_path}")
    plt.close()

    # 2. Title Word Cloud
    text = " ".join(df['title'].tolist())
    
    # Simple Korean font support check (optional, falls back to default)
    # For Windows, usually 'Malgun Gothic'
    font_path = "C:/Windows/Fonts/malgun.ttf" if os.path.exists("C:/Windows/Fonts/malgun.ttf") else None
    
    wordcloud = WordCloud(
        width=800, 
        height=400, 
        background_color='white',
        font_path=font_path,
        colormap='magma'
    ).generate(text)
    
    plt.figure(figsize=(10, 5))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.title(f"News Keywords WordCloud ({date.today()})", fontsize=15)
    plt.tight_layout()
    
    wordcloud_path = os.path.join(OUTPUT_DIR, "wordcloud.png")
    plt.savefig(wordcloud_path)
    print(f"☁️ Saved wordcloud to {wordcloud_path}")
    plt.close()

async def main():
    print("🚀 Starting Visualization Process...")
    articles = await fetch_todays_news()
    
    if articles:
        # Run visualization in a separate thread/process if needed, 
        # but for simple scripts, sync execution is fine.
        generate_visualizations(articles)
        print("✨ Visualization complete.")
    else:
        print("⚠️ Skipping visualization due to no data.")

if __name__ == "__main__":
    asyncio.run(main())
