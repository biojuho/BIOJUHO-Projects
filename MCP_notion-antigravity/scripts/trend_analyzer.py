import os
import json
import asyncio
import requests
import feedparser
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Configuration
REGION = "KR" 
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "trends")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize Gemini
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    print("[ERR] GOOGLE_API_KEY missing. AI filtering disabled.")
    model = None

def fetch_google_trends_rss():
    """Fetch trending searches using Google Trends RSS (No pandas required)"""
    print("Fetching Google Trends (RSS)...")
    rss_url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=KR"
    fallback_keywords = ["AI Agent", "RWA Token", "DeepSeek", "Bitcoin", "Samsung Electronics", "Tesla", "Nvidia"]
    
    try:
        # User-Agent is often required for Google Feeds
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(rss_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            titles = [entry.title for entry in feed.entries]
            if titles:
                return titles
        
        print("[WARN] RSS Empty or blocked. Using fallback.")
        return fallback_keywords
        
    except Exception as e:
        print(f"[WARN] RSS Fetch failed: {e}")
        return fallback_keywords

async def filter_trends(keywords):
    """Filter out people/entertainment, keep only Business/Tech/Economy"""
    if not model or not keywords:
        return keywords

    print(f"AI Filtering {len(keywords)} trends...")
    prompt = f"""
    Analyze the following list of search terms. 
    Filter OUT any terms related to:
    - Specific Celebrities / Entertainers / K-Pop
    - Politicians / Scandals
    - Sports players
    - TV Shows / Movies / Games
    
    KEEP only terms related to:
    - Business / Corporate News
    - Economy / Finance / Crypto
    - Technology / IT / Science
    - Industry Trends / Policies
    
    Input List: {json.dumps(keywords)}
    
    Return ONLY a JSON array of kept keywords. Example: ["Bitcoin", "Samsung"]
    """
    
    try:
        response = await model.generate_content_async(prompt)
        text = response.text.strip()
        # Clean markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Find start and end of json
            start = -1
            end = -1
            for i, line in enumerate(lines):
                if "```" in line:
                    if start == -1: start = i
                    else: end = i
            if start != -1 and end != -1:
                text = "\n".join(lines[start+1:end])
            else:
                 # Fallback cleanup
                text = text.replace("```json", "").replace("```", "")
                
        return json.loads(text)
    except Exception as e:
        print(f"[ERR] AI Filtering failed: {e}")
        return keywords # Return original if fail

async def fetch_news_for_trend(trend):
    """Fetch 1-2 news articles for a specific trend via Google News RSS"""
    encoded_trend = trend.replace(" ", "%20")
    rss_url = f"https://news.google.com/rss/search?q={encoded_trend}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    articles = []
    
    for entry in feed.entries[:3]:
        articles.append({
            "title": entry.title,
            "link": entry.link,
            "pubDate": entry.get("published", "")
        })
    return articles

async def generate_markdown_report(filtered_trends):
    """Compile filtered trends and news into a Markdown report"""
    timestamp = datetime.now().strftime("%Y-%m-%d")
    report_content = f"# 📈 Business & Tech Trends Report ({timestamp})\n\n"
    report_content += "Use this document as a source for **NotebookLM** to analyze recent market shifts.\n\n"
    
    print(f"Compiling report for {len(filtered_trends)} keywords...")
    
    for trend in filtered_trends:
        print(f"  - Processing: {trend}")
        report_content += f"## {trend}\n"
        
        articles = await fetch_news_for_trend(trend)
        if articles:
            for article in articles:
                # Basic cleanup of Google News titles (Source removal)
                title = article['title'].rsplit(" - ", 1)[0]
                report_content += f"- [{title}]({article['link']})\n"
                report_content += f"  - *{article['pubDate']}*\n"
        else:
            report_content += "- No recent news found.\n"
        
        report_content += "\n---\n\n"
    
    # Save file
    filename = f"Trend_Report_{timestamp}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    return filepath

async def main():
    # 1. Fetch
    raw_keywords = fetch_google_trends_rss()
    print(f"Raw Keywords ({len(raw_keywords)}): {raw_keywords}")
    
    # 2. Filter
    business_trends = await filter_trends(raw_keywords)
    print(f"Filtered Business Trends ({len(business_trends)}): {business_trends}")
    
    # 3. Generate Report
    if business_trends:
        report_path = await generate_markdown_report(business_trends)
        print(f"Report generated: {report_path}")
    else:
        print("[WARN] No business trends found.")

if __name__ == "__main__":
    asyncio.run(main())
