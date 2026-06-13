from __future__ import annotations

import sys
from pathlib import Path

_GDT_ROOT = Path(__file__).resolve().parents[1]
if str(_GDT_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDT_ROOT))

from models import GeneratedThread, GeneratedTweet, MultiSourceContext, ScoredTrend, TweetBatch
from notion_builder import _build_notion_body, _notion_page_exists


def _tweet(content: str, tweet_type: str = "공감 유도형", platform: str = "x") -> GeneratedTweet:
    return GeneratedTweet(tweet_type=tweet_type, content=content, platform=platform, char_count=len(content))


def _block_types(blocks: list[dict]) -> list[str]:
    return [block["type"] for block in blocks]


def test_build_notion_body_includes_core_sections_and_optional_media():
    batch = TweetBatch(
        topic="AI regulation",
        tweets=[_tweet("short draft")],
        long_posts=[_tweet("long paragraph " * 180, tweet_type="long", platform="x")],
        threads_posts=[_tweet("thread draft", tweet_type="thread", platform="threads")],
        blog_posts=[
            _tweet(
                "# Blog title\n## Section\n- bullet\nbody",
                tweet_type="blog",
                platform="naver_blog",
            )
        ],
        thread=GeneratedThread(tweets=["hook", "body"]),
        metadata={
            "predicted_er": 0.04,
            "predicted_impressions": 1200,
            "viral_probability": 0.35,
            "pee_risk": "low",
            "optimal_hours": [8, 12, 20],
        },
    )
    trend = ScoredTrend(
        keyword="AI regulation",
        rank=1,
        viral_potential=85,
        trend_acceleration="+20%",
        top_insight="Policy changed today",
        suggested_angles=["operator angle"],
    )

    blocks = _build_notion_body(batch, trend, image_url="https://example.com/image.png")
    types = _block_types(blocks)

    assert types[0] == "callout"
    assert "image" in types
    assert "code" in types
    assert "toggle" not in types
    assert types.count("heading_2") >= 5
    assert any(block.get("heading_1", {}).get("rich_text", [{}])[0].get("text", {}).get("content") == "Blog title" for block in blocks)


def test_build_notion_body_adds_context_toggle_when_context_present():
    batch = TweetBatch(topic="context topic", tweets=[_tweet("draft")])
    trend = ScoredTrend(
        keyword="context topic",
        rank=1,
        viral_potential=50,
        context=MultiSourceContext(twitter_insight="source evidence"),
    )

    blocks = _build_notion_body(batch, trend)

    assert "toggle" in _block_types(blocks)


def test_notion_page_exists_returns_false_on_query_failure():
    class BrokenDatabases:
        def query(self, **kwargs):
            raise RuntimeError("notion unavailable")

    class BrokenNotion:
        databases = BrokenDatabases()

    assert _notion_page_exists(BrokenNotion(), "db", "keyword", "2026-05-20") is False
