"""One-shot Economy_KR uploader — bypasses LLM summarization."""
from __future__ import annotations
import asyncio, sys, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.chdir(os.path.dirname(__file__))

# Force UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from runtime import fetch_feed_entries
from settings import NOTION_API_KEY, ANTIGRAVITY_TASKS_DB_ID
from notion_client import AsyncClient
from news_bot import _is_relevant_to_category

SOURCES = [
    ("Maeil Economy", "https://www.mk.co.kr/rss/30100041/"),
    ("Seoul Economy", "https://www.sedaily.com/RSS/Economy"),
    ("Yonhap Economy", "https://www.yna.co.kr/rss/economy.xml"),
    ("MK Securities", "https://www.mk.co.kr/rss/30100228/"),
    ("MK Real Estate", "https://www.mk.co.kr/rss/30200030/"),
]

MAX_ARTICLES = 10


async def main() -> int:
    print("=== Economy_KR Direct Uploader ===", flush=True)
    notion = AsyncClient(auth=NOTION_API_KEY)
    articles: list[dict] = []
    seen: set[str] = set()

    for name, url in SOURCES:
        try:
            entries = await fetch_feed_entries(url)
            count = 0
            for e in entries:
                if len(articles) >= MAX_ARTICLES:
                    break
                title = getattr(e, "title", "")
                link = getattr(e, "link", "")
                desc = getattr(e, "summary", "") or getattr(e, "description", "") or ""
                if not link or link in seen:
                    continue
                if not _is_relevant_to_category(title, desc, "Economy_KR"):
                    continue
                articles.append({"title": title, "link": link, "source": name, "desc": desc[:300]})
                seen.add(link)
                count += 1
            print(f"  {name}: {count} articles passed filter", flush=True)
        except Exception as ex:
            print(f"  {name}: ERROR - {ex}", flush=True)

    print(f"\nTotal articles: {len(articles)}", flush=True)
    if not articles:
        print("No articles collected! Check RSS feeds.", flush=True)
        return 1

    now = datetime.now()
    children = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": "Economy_KR Manual Brief"}}]},
        }
    ]
    for a in articles:
        children.append(
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"text": {"content": f"[{a['source']}] {a['title'][:80]}", "link": {"url": a["link"]}}},
                    ]
                },
            }
        )

    page = await notion.pages.create(
        parent={"database_id": ANTIGRAVITY_TASKS_DB_ID},
        properties={
            "Name": {"title": [{"text": {"content": f"[Economy_KR] Manual Brief - {now.strftime('%Y-%m-%d %H:%M')}"}}]},
            "Date": {"date": {"start": now.isoformat()}},
            "Type": {"select": {"name": "News"}},
            "Priority": {"select": {"name": "High"}},
        },
        children=children,
    )
    print(f"\nSUCCESS! Notion page: {page['id']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
