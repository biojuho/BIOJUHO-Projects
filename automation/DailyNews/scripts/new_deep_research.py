import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

# 본 스크립트는 안티그래비티 에이전트의 "deep-research" 스킬 실전용 Entry Point 입니다.
# Google News RSS, Twitter API, YouTube Transcript API 를 연동하여 다면적 데이터를 리서치합니다.


def fetch_google_news(topic: str, max_results=10):
    encoded_topic = urllib.parse.quote(topic)
    url = f"https://news.google.com/rss/search?q={encoded_topic}&hl=ko&gl=KR&ceid=KR:ko"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        items = []
        for item in root.findall(".//item")[:max_results]:
            title = item.find("title").text if item.find("title") is not None else "No Title"
            link = item.find("link").text if item.find("link") is not None else "No Link"
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            items.append({"title": title, "link": link, "pubDate": pub_date})
        return items
    except Exception as e:
        print(f"[ERROR] Failed to fetch news for {topic}: {e}")
        return []


def fetch_twitter_trends(topic: str, api_key: str, max_results=20):
    """
    Call the twitter_search skill script to get social sentiment and recent tweets.
    """
    if not api_key:
        print("[WARNING] No Twitter API key provided. Skipping Twitter search.")
        return None

    script_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        ".agents",
        "skills",
        "twitter-search",
        "scripts",
        "twitter_search.py",
    )
    if not os.path.exists(script_path):
        print(f"[WARNING] Twitter script not found at {script_path}")
        return None

    try:
        cmd = [sys.executable, script_path, api_key, topic, "--max-results", str(max_results), "--format", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[ERROR] Failed to fetch Twitter trends: {e}")
        return None


def fetch_youtube_transcript(topic: str):
    """
    Search a video loosely matching the topic format (if URL provided) or skip.
    For MVP, we assume the user might provide a Youtube URL directly in the topic if they want it analyzed.
    """
    if "youtube.com" not in topic and "youtu.be" not in topic:
        return None  # Not a youtube url

    script_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        ".agents",
        "skills",
        "youtube-intelligence",
        "scripts",
        "transcript_fetcher.py",
    )
    if not os.path.exists(script_path):
        print(f"[WARNING] Youtube script not found at {script_path}")
        return None

    try:
        url = topic.split(" ")[-1]  # attempt to extract URL if appended
        cmd = [sys.executable, script_path, url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[ERROR] Failed to fetch Youtube Transcript: {e}")
        return None


def generate_deep_research_report(topic: str, output_dir: str):
    print(f"[INFO] Starting MULTI-MODAL deep research on topic: '{topic}'")

    # URL이 붙어있을 경우 뉴스 검색 질의어(Clean Topic) 분리
    clean_topic = topic
    if "http" in topic:
        clean_topic = " ".join([word for word in topic.split() if not word.startswith("http")])

    # 1. 실제 데이터 수집 (Google News RSS)
    print(f"[INFO] Collecting real-time news data for '{clean_topic}'...")
    news_items = fetch_google_news(clean_topic, max_results=10)

    # 2. 소셜 여론 수집 (Twitter API)
    print(f"[INFO] Collecting Twitter sentiment for '{topic}'...")
    twitter_data = fetch_twitter_trends(topic, os.getenv("TWITTER_API_KEY", ""))

    # 3. 유튜브 스크립트 수집 (If URL present)
    print(f"[INFO] Checking for YouTube links for '{topic}'...")
    youtube_data = fetch_youtube_transcript(topic)

    # 4. 결과 종합
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_title = f"{date_str} Deep Research Report: {topic.replace(' ', '_').replace('/', '_').replace(':', '_')}"

    content = f"# 🔍 Enhanced Deep Research: {topic}\n"
    content += f"*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"

    content += "## 1. Executive Summary\n"
    content += f"This report provides a multi-modal overview of **{topic}** integrating News, Social Sentiment, and Video Insights.\n\n"

    content += "## 2. Latest Headlines (Google News)\n"
    if not news_items:
        content += "- No recent news found or error occurred during fetching.\n"
    else:
        for idx, item in enumerate(news_items[:5], 1):
            content += f"- **[{item['pubDate']}]**: [{item['title']}]({item['link']})\n"

    content += "\n## 3. Social Media Sentiment & Trends (X/Twitter)\n"
    if twitter_data and "statistics" in twitter_data:
        stats = twitter_data["statistics"]
        content += f"- **Total analyzed tweets**: {stats.get('total_tweets', 0)}\n"
        content += f"- **Total Engagement**: {stats.get('total_engagement', {}).get('likes', 0)} likes, {stats.get('total_engagement', {}).get('retweets', 0)} retweets\n"
        content += "- **Top Hashtags**:\n"
        for tag, count in list(stats.get("top_hashtags", {}).items())[:5]:
            content += f"  - #{tag} ({count} mentions)\n"
        content += "- **Recent Voices**:\n"
        for t in twitter_data.get("tweets", [])[:3]:
            content += f"  - [@{t['author']['username']}]: {t['text'][:100]}...\n"
    else:
        content += "- No Twitter data fetched (API Key missing or error).\n"

    content += "\n## 4. Video Intelligence (YouTube)\n"
    if youtube_data and "transcript_text" in youtube_data:
        content += f"- **Video ID**: {youtube_data['video_id']}\n"
        content += f"- **Transcript Preview**: {youtube_data['transcript_text'][:500]}...\n"
    else:
        content += "- No valid YouTube URL detected or transcript unavailable.\n"

    content += "\n## 5. Sources\n"
    if not news_items:
        content += "- None\n"
    else:
        for idx, item in enumerate(news_items, 1):
            content += f"{idx}. [{item['title']}]({item['link']}) - *{item['pubDate']}*\n"

    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"{report_title}.md")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    latest_txt = os.path.join(output_dir, "latest_report.txt")
    with open(latest_txt, "w", encoding="utf-8") as f:
        f.write(file_path)

    print(f"[SUCCESS] Real-time deep research complete. Output saved to: {file_path}")
    return file_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Antigravity Deep Research Module (Real API)")
    parser.add_argument("--topic", type=str, required=True, help="The topic to research")
    parser.add_argument("--outd", type=str, default="output", help="Output directory")
    args = parser.parse_args()

    generate_deep_research_report(args.topic, args.outd)
