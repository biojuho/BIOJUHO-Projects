from __future__ import annotations

import asyncio
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from wordcloud import WordCloud

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from antigravity_mcp.integrations.notion_adapter import NotionAdapter
from antigravity_mcp.state.events import json_dumps
from settings import NOTION_REPORTS_DATABASE_ID, OUTPUT_DIR


async def fetch_todays_news() -> list[dict[str, str]]:
    if not NOTION_REPORTS_DATABASE_ID:
        print("[FAIL] NOTION_REPORTS_DATABASE_ID is missing.")
        return []

    adapter = NotionAdapter()
    if not adapter.is_configured():
        print("[FAIL] NOTION_API_KEY is missing.")
        return []

    today_str = date.today().isoformat()
    print(f"[INFO] Fetching report records for {today_str}...")

    results, _ = await adapter.query_database(
        database_id=NOTION_REPORTS_DATABASE_ID,
        filter_payload={"property": "Date", "date": {"equals": today_str}},
        limit=100,
    )

    articles: list[dict[str, str]] = []
    for page in results:
        properties = page.get("properties", {})
        title_items = properties.get("Name", {}).get("title", [])
        title = title_items[0].get("plain_text", "") if title_items else ""
        source_name = properties.get("Source", {}).get("select", {}).get("name", "Unknown")
        articles.append({"title": title, "source": source_name})

    print(f"[INFO] Loaded {len(articles)} records.")
    return articles


def generate_visualizations(articles: list[dict[str, str]]) -> dict[str, str]:
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not articles:
        print("[INFO] No articles to visualize.")
        return {}

    df = pd.DataFrame(articles)
    source_counts = Counter(df["source"])

    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(10, 6))
    chart_df = pd.DataFrame({"source": list(source_counts.keys()), "count": list(source_counts.values())})
    ax = sns.barplot(data=chart_df, x="source", y="count", hue="source", dodge=False, palette="rocket")
    ax.set_title(f"Report Source Distribution ({date.today()})", fontsize=15)
    ax.set_ylabel("Count")
    ax.legend_.remove()
    plt.xticks(rotation=35, ha="right")
    plt.tight_layout()
    source_chart_path = output_dir / "source_distribution.png"
    plt.savefig(source_chart_path)
    plt.close()

    wordcloud_text = " ".join(df["title"].tolist()) or "Antigravity"
    font_path = "C:/Windows/Fonts/malgun.ttf" if Path("C:/Windows/Fonts/malgun.ttf").exists() else None
    wordcloud = WordCloud(
        width=960,
        height=480,
        background_color="white",
        font_path=font_path,
        colormap="magma",
    ).generate(wordcloud_text)
    plt.figure(figsize=(11, 5.5))
    plt.imshow(wordcloud, interpolation="bilinear")
    plt.axis("off")
    plt.title(f"Report Keywords ({date.today()})", fontsize=15)
    plt.tight_layout()
    wordcloud_path = output_dir / "wordcloud.png"
    plt.savefig(wordcloud_path)
    plt.close()

    artifacts = {"source_distribution": str(source_chart_path), "wordcloud": str(wordcloud_path)}
    print(json_dumps({"status": "ok", "artifacts": artifacts}))
    return artifacts


async def main() -> None:
    print("[INFO] Starting visualization pipeline...")
    articles = await fetch_todays_news()
    generate_visualizations(articles)


if __name__ == "__main__":
    asyncio.run(main())
