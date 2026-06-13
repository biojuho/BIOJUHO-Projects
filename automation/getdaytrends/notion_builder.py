"""
getdaytrends Notion body builder.

This module builds the child block payload used by the Notion publishing path.
Keep the public helpers stable because storage modules import them directly.
"""

from collections.abc import Iterable
from datetime import datetime

try:
    from .models import GeneratedTweet, ScoredTrend, TweetBatch
except ImportError:
    from models import GeneratedTweet, ScoredTrend, TweetBatch


def _notion_page_exists(
    notion,
    database_id: str,
    keyword: str,
    date_str: str,
) -> bool:
    """Return whether today's Notion page already exists for a keyword."""
    try:
        results = notion.databases.query(
            database_id=database_id,
            filter={
                "and": [
                    {"property": "주제", "rich_text": {"contains": keyword}},
                    {"property": "생성시각", "date": {"on_or_after": f"{date_str}T00:00:00"}},
                ]
            },
            page_size=1,
        )
        return bool(results.get("results"))
    except Exception:
        return False


def _rich_text(content: str, *, bold: bool = False) -> list[dict]:
    text: dict = {"type": "text", "text": {"content": content[:1900]}}
    if bold:
        text["annotations"] = {"bold": True}
    return [text]


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _heading(level: int, content: str) -> dict:
    block_type = f"heading_{level}"
    return {"object": "block", "type": block_type, block_type: {"rich_text": _rich_text(content)}}


def _paragraph(content: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich_text(content)}}


def _bulleted_item(content: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": _rich_text(content)}}


def _code_block(content: str) -> dict:
    return {
        "object": "block",
        "type": "code",
        "code": {"language": "plain text", "rich_text": _rich_text(content)},
    }


def _callout(content: str, emoji: str, color: str, *, bold: bool = False) -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": emoji},
            "rich_text": _rich_text(content, bold=bold),
            "color": color,
        },
    }


def _chunked_paragraphs(content: str, chunk_size: int = 1900) -> list[dict]:
    return [_paragraph(content[index : index + chunk_size]) for index in range(0, len(content), chunk_size) if content[index : index + chunk_size]]


def _posting_tip(now: datetime) -> str:
    hour = now.hour
    if 6 <= hour < 10:
        return "오전 질주 골든타임입니다. 지금 올리면 노출이 좋습니다."
    if 11 <= hour < 14:
        return "점심 골든타임입니다. 직장인 라이브 체크에 맞추세요."
    if 19 <= hour < 23:
        return "저녁 골든타임입니다. 퇴근 후 반응을 노리기 좋습니다."
    return "최적 포스팅 시간: 오전 7-9시 / 점심 12-13시 / 저녁 20-22시"


def _intro_blocks(batch: TweetBatch, trend: ScoredTrend, now: datetime) -> list[dict]:
    score_bar = "█" * (trend.viral_potential // 10) + "░" * (10 - trend.viral_potential // 10)
    return [
        _callout(
            f"오늘의 중연 포스팅 초안: {batch.topic}\n"
            f"{_posting_tip(now)}\n"
            "아래 초안에서 마음에 드는 것을 복사해서 X에 직접 올리세요.",
            "🚀",
            "green_background",
        ),
        _callout(
            f"바이럴 점수: {trend.viral_potential}/100  [{score_bar}]\n"
            f"가속도: {trend.trend_acceleration}  |  소스: {len(trend.sources)}개",
            "📊",
            "blue_background" if trend.viral_potential >= 80 else "gray_background",
        ),
    ]


def _image_blocks(image_url: str) -> list[dict]:
    if not image_url:
        return []
    return [
        {"object": "block", "type": "image", "image": {"type": "external", "external": {"url": image_url}}},
        _divider(),
    ]


def _prediction_blocks(metadata: dict) -> list[dict]:
    if metadata.get("predicted_er") is None:
        return []
    pred_er = metadata["predicted_er"]
    pred_imp = metadata.get("predicted_impressions", 0)
    viral_prob = metadata.get("viral_probability", 0)
    pee_risk = metadata.get("pee_risk", "unknown")
    opt_hours = metadata.get("optimal_hours", [])
    risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(pee_risk, "⚪")
    er_bar = "█" * min(int(pred_er * 200), 10) + "░" * max(10 - min(int(pred_er * 200), 10), 0)
    hours_str = ", ".join(f"{hour}시" for hour in opt_hours[:3]) if opt_hours else "N/A"
    return [
        _callout(
            "AI 성과 예측 (PEE)\n"
            f"예상 ER: {pred_er:.2%}  [{er_bar}]\n"
            f"예상 Impression: {pred_imp:,}  |  바이럴 확률: {viral_prob:.0%}\n"
            f"리스크: {risk_emoji} {pee_risk}  |  최적 발행: {hours_str}",
            "📈",
            "purple_background" if viral_prob > 0.3 else "gray_background",
        )
    ]


def _insight_blocks(trend: ScoredTrend) -> list[dict]:
    if not trend.top_insight:
        return []
    return [_callout(f"이 트렌드의 킥\n{trend.top_insight}", "💡", "yellow_background", bold=True)]


def _tweet_icon(tweet_type: str) -> str:
    tweet_icons = {
        "공감 유도형": "🟠",
        "꿀팁형": "🟢",
        "찬반 질문형": "⚖️",
        "팩트 관찰형": "🔎",
        "롱테이크형": "🧵",
        "가벼운 꿀팁형": "🟢",
        "동기부여형": "🧭",
        "동기부여 명언형": "🧭",
        "유머/반전형": "😄",
        "유머/밈 활용형": "😄",
    }
    return tweet_icons.get(tweet_type, "📝")


def _tweet_blocks(tweets: Iterable[GeneratedTweet]) -> list[dict]:
    blocks = [_divider(), _heading(2, "🐦 트윗 초안 (5종, 아래에서 선택 후 X에 복붙)")]
    for tweet in tweets:
        blocks.append(_heading(3, f"{_tweet_icon(tweet.tweet_type)} {tweet.tweet_type} ({tweet.char_count}자)"))
        blocks.append(_code_block(tweet.content))
    return blocks


def _thread_blocks(batch: TweetBatch) -> list[dict]:
    if not batch.thread or not batch.thread.tweets:
        return []
    blocks = [_divider(), _heading(2, f"🧵 스레드 ({len(batch.thread.tweets)}트윗)")]
    for index, text in enumerate(batch.thread.tweets):
        label = "🎣 Hook" if index == 0 else f"🧩 {index + 1}/{len(batch.thread.tweets)}"
        blocks.append(_code_block(f"{label}\n{text}"))
    return blocks


def _context_blocks(trend: ScoredTrend) -> list[dict]:
    if not trend.context:
        return []
    combined = trend.context.to_combined_text()
    if not combined:
        return []
    return [
        _divider(),
        {
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": _rich_text("📚 수집한 원본 데이터 (펼쳐보기)"),
                "children": [_paragraph(combined)],
            },
        },
    ]


def _suggested_angle_blocks(trend: ScoredTrend) -> list[dict]:
    if not trend.suggested_angles:
        return []
    blocks = [_divider(), _heading(2, "🚀 추천 앵글 (다음 포스팅 아이디어)")]
    blocks.extend(_bulleted_item(angle) for angle in trend.suggested_angles)
    return blocks


def _long_post_blocks(posts: Iterable[GeneratedTweet]) -> list[dict]:
    posts = list(posts)
    if not posts:
        return []
    blocks = [_divider(), _heading(2, "📝 X Premium+ 장문 포스트")]
    for post in posts:
        blocks.append(_heading(3, f"📌 {post.tweet_type} ({post.char_count}자)"))
        blocks.extend(_chunked_paragraphs(post.content))
    return blocks


def _threads_post_blocks(posts: Iterable[GeneratedTweet]) -> list[dict]:
    posts = list(posts)
    if not posts:
        return []
    blocks = [_divider(), _heading(2, "🧵 Threads 콘텐츠")]
    blocks.extend(_code_block(f"[{post.tweet_type}]\n{post.content}") for post in posts)
    return blocks


def _markdown_line_block(stripped: str) -> list[dict]:
    if stripped.startswith("# "):
        return [_heading(1, stripped[2:])]
    if stripped.startswith("## "):
        return [_heading(2, stripped[3:])]
    if stripped.startswith("### "):
        return [_heading(3, stripped[4:])]
    if stripped.startswith("- "):
        return [_bulleted_item(stripped[2:])]
    if stripped.startswith("---"):
        return [_divider()]
    return _chunked_paragraphs(stripped)


def _blog_blocks(posts: Iterable[GeneratedTweet]) -> list[dict]:
    posts = list(posts)
    if not posts:
        return []
    blocks = [_divider(), _heading(2, "📝 네이버 블로그 글감")]
    for post in posts:
        seo_keywords = getattr(post, "seo_keywords", [])
        if seo_keywords:
            blocks.append(_callout(f"SEO 키워드: {', '.join(seo_keywords)}\n글자 수: {post.char_count:,}자", "🏷️", "purple_background"))
        for line in post.content.split("\n"):
            stripped = line.strip()
            if stripped:
                blocks.extend(_markdown_line_block(stripped))
    return blocks


def _build_notion_body(
    batch: TweetBatch,
    trend: ScoredTrend,
    image_url: str = "",
) -> list[dict]:
    """Build Notion child blocks for one generated content batch."""
    now = datetime.now()
    blocks: list[dict] = []
    blocks.extend(_intro_blocks(batch, trend, now))
    blocks.extend(_image_blocks(image_url))
    blocks.extend(_prediction_blocks(getattr(batch, "metadata", {}) or {}))
    blocks.extend(_insight_blocks(trend))
    blocks.extend(_tweet_blocks(batch.tweets))
    blocks.extend(_thread_blocks(batch))
    blocks.extend(_context_blocks(trend))
    blocks.extend(_suggested_angle_blocks(trend))
    blocks.extend(_long_post_blocks(batch.long_posts))
    blocks.extend(_threads_post_blocks(batch.threads_posts))
    blocks.extend(_blog_blocks(batch.blog_posts))
    return blocks
