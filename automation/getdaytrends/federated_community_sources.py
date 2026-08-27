"""Normalizers for public, credential-free federated community signals.

Mastodon의 공개 트렌드 API와 Bluesky 공개 AppView 경로를 기존 직접 커뮤니티
목록(`direct_community_sources.py`)과 같은 item 스키마로 정규화한다.

- 인증 없이 응답하는 공개 경로만 사용한다(2026-08-27 실측 기준).
- 미디어 몸체/blob는 내려받지 않는다. 종류 메타만 보존하고 `video_url`은 비운다.
- 정치·민감 메타는 공식 필드가 말할 수 있을 때만 표시하고, 모르면 `None`으로 둔다.
  `False`로 써서 "안전하다"고 단정하지 않는다.
- 소스 하나의 실패(네트워크·스키마·부분 필드)는 다른 소스를 막지 않는다.
- 중복 제거는 공식 URI/ID 정확 일치만 쓴다. 제목 유사도로 병합하지 않는다.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

MASTODON_TRENDS_URL = "https://mastodon.social/api/v1/trends/statuses"
BLUESKY_APPVIEW_BASE = "https://public.api.bsky.app/xrpc"
BLUESKY_TRENDING_TOPICS_URL = f"{BLUESKY_APPVIEW_BASE}/app.bsky.unspecced.getTrendingTopics"
BLUESKY_FEED_URL = f"{BLUESKY_APPVIEW_BASE}/app.bsky.feed.getFeed"
LEMMY_HOT_POSTS_URL = "https://lemmy.world/api/v3/post/list"

FEDERATED_COMMUNITY_SOURCES = (
    {
        "key": "mastodon_trends",
        "label": "Mastodon 트렌드",
        "url": MASTODON_TRENDS_URL,
    },
    {
        "key": "bluesky_trending",
        "label": "Bluesky 트렌드 피드",
        "url": BLUESKY_TRENDING_TOPICS_URL,
    },
    {
        "key": "lemmy_hot",
        "label": "Lemmy Hot",
        "url": LEMMY_HOT_POSTS_URL,
    },
)

_TITLE_MAX_CHARS = 160

_ATTACHMENT_VIDEO = "video"
_ATTACHMENT_IMAGE = "image"
_ATTACHMENT_TEXT = "text"
_ATTACHMENT_UNKNOWN = "unknown"

# Bluesky com.atproto.label defs의 자기 라벨 중 민감 계열 값. 이 목록에 없으면 모른다고 본다.
_SENSITIVE_LABEL_VALUES = frozenset(
    {
        "porn",
        "sexual",
        "nudity",
        "adult",
        "explicit-sexual",
        "suggestive",
        "graphic-media",
        "gore",
        "violence",
    }
)

_SOURCE_SIGNAL = "글로벌 공개 커뮤니티"


def _strip_html_to_text(markup: Any, *, limit: int = _TITLE_MAX_CHARS) -> str:
    if not isinstance(markup, str) or not markup.strip():
        return ""
    text = " ".join(BeautifulSoup(markup, "html.parser").get_text(" ", strip=True).split())
    return text[:limit].rstrip() if len(text) > limit else text


def _count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def _age_minutes_from_iso(value: Any, now: datetime) -> int | None:
    """게시 시각을 파싱 못 하면 0분이 아니라 None을 돌려준다(신선 단정 금지)."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        published = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if published.tzinfo is None:
        return None
    return max(0, round((now - published.astimezone(UTC)).total_seconds() / 60))


def _language(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _base_federated_item(
    *,
    source_key: str,
    source_label: str,
    item_id: str,
    dedupe_key: str,
    title: str,
    source_url: str,
    category: str,
    published_label: str,
    age_minutes: int | None,
    comments: int,
    reposts: int,
    likes: int,
    quotes: int,
    position: int,
    attachment_kind: str,
    media_kinds: list[str],
    language: str | None,
    sensitive: bool | None,
    spoiler_text: str,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "title": title,
        "category": category,
        "community_source": source_key,
        "community_label": source_label,
        "source_url": source_url,
        "link_kind": "publisher_original",
        "published_label": published_label,
        "age_minutes": age_minutes,
        # 이 API들은 조회수를 공개하지 않는다. 추정하지 않고 0을 명시한다.
        "views": 0,
        # 기존 스키마의 votes에는 확산 신호인 리포스트/부스트를 대응시킨다.
        "votes": reposts,
        "comments": comments,
        "source_position": position,
        "signal_source": _SOURCE_SIGNAL,
        "attachment_kind": attachment_kind,
        # 미디어 blob URL은 보관·다운로드하지 않는다. 종류 메타만 남긴다.
        "video_url": "",
        "dedupe_key": dedupe_key,
        "reposts": reposts,
        "likes": likes,
        "quotes": quotes,
        "language": language,
        # 공개 메타에 지역 정보가 없다. 추측 대신 None을 보존한다.
        "region": None,
        "sensitive": sensitive,
        # 공개 메타만으로 정치 여부를 알 수 없다.
        "political": None,
        "spoiler_text": spoiler_text,
        "media_kinds": media_kinds,
    }


def _mastodon_media_kinds(status: dict[str, Any]) -> tuple[str, list[str]]:
    attachments = status.get("media_attachments")
    kinds: list[str] = []
    if isinstance(attachments, list):
        for attachment in attachments:
            if isinstance(attachment, dict):
                kind = attachment.get("type")
                if isinstance(kind, str) and kind.strip():
                    kinds.append(kind.strip())
    if any(kind in {"video", "gifv"} for kind in kinds):
        return _ATTACHMENT_VIDEO, kinds
    if any(kind == "image" for kind in kinds):
        return _ATTACHMENT_IMAGE, kinds
    if not kinds:
        # media_attachments가 비어 있으면 글 전용이 확정이다.
        return _ATTACHMENT_TEXT, kinds
    # audio 등 기존 종류 단어장(video/image/text/unknown)에 없는 값은 모른다고 표시한다.
    return _ATTACHMENT_UNKNOWN, kinds


def parse_mastodon_status(
    status: Any,
    *,
    position: int,
    now: datetime,
) -> dict[str, Any] | None:
    if not isinstance(status, dict):
        return None
    if isinstance(status.get("reblog"), dict):
        status = status["reblog"]
    item_id = status.get("id")
    uri = status.get("uri")
    if not isinstance(item_id, str) or not item_id.strip():
        return None
    if not isinstance(uri, str) or not uri.strip():
        return None
    permalink = status.get("url")
    source_url = permalink if isinstance(permalink, str) and permalink.strip() else uri
    created_at = status.get("created_at")
    published_label = created_at if isinstance(created_at, str) and created_at.strip() else ""
    spoiler_text = status.get("spoiler_text")
    spoiler_text = spoiler_text if isinstance(spoiler_text, str) else ""
    sensitive = status.get("sensitive")
    attachment_kind, media_kinds = _mastodon_media_kinds(status)
    title = _strip_html_to_text(status.get("content"))
    if not title:
        return None
    return _base_federated_item(
        source_key="mastodon_trends",
        source_label="Mastodon 트렌드",
        item_id=item_id.strip(),
        dedupe_key=uri.strip(),
        title=title,
        source_url=source_url,
        category="Mastodon 트렌드",
        published_label=published_label,
        age_minutes=_age_minutes_from_iso(created_at, now),
        comments=_count(status.get("replies_count")),
        reposts=_count(status.get("reblogs_count")),
        likes=_count(status.get("favourites_count")),
        quotes=_count(status.get("quotes_count")),
        position=position,
        attachment_kind=attachment_kind,
        media_kinds=media_kinds,
        language=_language(status.get("language")),
        sensitive=sensitive if isinstance(sensitive, bool) else None,
        spoiler_text=spoiler_text,
    )


def parse_mastodon_trends(payload: Any, *, now: datetime | None = None) -> list[dict[str, Any]]:
    reference = now or datetime.now(UTC)
    if not isinstance(payload, list):
        raise ValueError("Mastodon 트렌드 응답이 목록이 아님")
    items: list[dict[str, Any]] = []
    for status in payload:
        try:
            item = parse_mastodon_status(status, position=len(items), now=reference)
        except Exception:
            continue
        if item is not None:
            items.append(item)
    return items


def _lemmy_attachment_kind(post: dict[str, Any]) -> tuple[str, list[str]]:
    target = str(post.get("url") or "").casefold()
    if any(marker in target for marker in ("youtube.com/", "youtu.be/", "vimeo.com/", "/videos/watch/")):
        return _ATTACHMENT_VIDEO, ["external_video"]
    if target.split("?", 1)[0].endswith((".mp4", ".webm", ".mov")):
        return _ATTACHMENT_VIDEO, ["external_video"]
    if target.split("?", 1)[0].endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        return _ATTACHMENT_IMAGE, ["external_image"]
    return _ATTACHMENT_TEXT, []


def parse_lemmy_hot(payload: Any, *, now: datetime | None = None) -> list[dict[str, Any]]:
    reference = now or datetime.now(UTC)
    if not isinstance(payload, dict) or not isinstance(payload.get("posts"), list):
        raise ValueError("Lemmy hot 응답 스키마가 맞지 않음")
    items: list[dict[str, Any]] = []
    for entry in payload["posts"]:
        if not isinstance(entry, dict):
            continue
        post = entry.get("post")
        counts = entry.get("counts")
        community = entry.get("community")
        if not isinstance(post, dict) or not isinstance(counts, dict):
            continue
        item_id = post.get("id")
        title = _strip_html_to_text(post.get("name"))
        ap_id = str(post.get("ap_id") or "").strip()
        if isinstance(item_id, bool) or not isinstance(item_id, int) or not title:
            continue
        source_url = ap_id if ap_id.startswith(("http://", "https://")) else f"https://lemmy.world/post/{item_id}"
        published = post.get("published")
        published_label = published if isinstance(published, str) and published.strip() else ""
        community_label = "Lemmy Hot"
        if isinstance(community, dict):
            community_name = _strip_html_to_text(
                community.get("title") or community.get("name"),
                limit=60,
            )
            if community_name:
                community_label = f"Lemmy · {community_name}"
        attachment_kind, media_kinds = _lemmy_attachment_kind(post)
        items.append(
            _base_federated_item(
                source_key="lemmy_hot",
                source_label="Lemmy Hot",
                item_id=str(item_id),
                dedupe_key=ap_id or f"lemmy.world:{item_id}",
                title=title,
                source_url=source_url,
                category=community_label,
                published_label=published_label,
                age_minutes=_age_minutes_from_iso(published, reference),
                comments=_count(counts.get("comments")),
                reposts=_count(counts.get("score")),
                likes=_count(counts.get("upvotes")),
                quotes=0,
                position=len(items),
                attachment_kind=attachment_kind,
                media_kinds=media_kinds,
                language=None,
                sensitive=post.get("nsfw") if isinstance(post.get("nsfw"), bool) else None,
                spoiler_text="",
            )
        )
    return items


def _bluesky_self_label_values(post: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for holder in (post.get("labels"), (post.get("record") or {}).get("labels")):
        if isinstance(holder, dict):
            holder = holder.get("values")
        if not isinstance(holder, list):
            continue
        for label in holder:
            if isinstance(label, dict):
                val = label.get("val")
                if isinstance(val, str) and val.strip():
                    values.append(val.strip())
    return values


def _bluesky_embed_kind(post: dict[str, Any]) -> tuple[str, list[str]]:
    record_raw = post.get("record")
    record = record_raw if isinstance(record_raw, dict) else {}
    kinds: list[str] = []

    def scan(embed: Any) -> str | None:
        if not isinstance(embed, dict):
            return None
        embed_type = str(embed.get("$type") or "")
        kinds.append(embed_type)
        if embed_type == "app.bsky.embed.video" or embed_type.startswith("app.bsky.embed.video#"):
            return _ATTACHMENT_VIDEO
        if embed_type == "app.bsky.embed.images" or embed_type.startswith("app.bsky.embed.images#"):
            return _ATTACHMENT_IMAGE
        if embed_type == "app.bsky.embed.recordWithMedia":
            return scan(embed.get("media"))
        if embed_type == "app.bsky.embed.external" or embed_type.startswith("app.bsky.embed.external#"):
            return _ATTACHMENT_TEXT
        if embed_type == "app.bsky.embed.record" or embed_type.startswith("app.bsky.embed.record#"):
            # 인용 포스트 안의 미디어는 여기서 판정하지 않는다.
            return _ATTACHMENT_UNKNOWN
        return None

    kind = scan(record.get("embed")) or scan(post.get("embed"))
    if kind is not None:
        return kind, kinds
    return _ATTACHMENT_TEXT, kinds


def parse_bluesky_post(
    entry: Any,
    *,
    position: int,
    now: datetime,
    topic: str = "",
) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    post = entry.get("post")
    if not isinstance(post, dict):
        return None
    record_raw = post.get("record")
    record = record_raw if isinstance(record_raw, dict) else {}
    if record.get("$type") != "app.bsky.feed.post":
        return None
    uri = post.get("uri")
    if not isinstance(uri, str) or not uri.strip():
        return None
    uri = uri.strip()
    rkey = uri.rsplit("/", 1)[-1]
    handle = str((post.get("author") or {}).get("handle") or "")
    source_url = f"https://bsky.app/profile/{handle}/post/{rkey}" if handle else uri
    created_at = record.get("createdAt")
    langs = record.get("langs")
    language = None
    if isinstance(langs, list):
        language = next((_language(value) for value in langs if _language(value)), None)
    label_values = _bluesky_self_label_values(post)
    sensitive = True if any(value in _SENSITIVE_LABEL_VALUES for value in label_values) else None
    attachment_kind, media_kinds = _bluesky_embed_kind(post)
    title = _strip_html_to_text(record.get("text"))
    if not title:
        return None
    topic_label = _strip_html_to_text(topic, limit=80)
    return _base_federated_item(
        source_key="bluesky_trending",
        source_label="Bluesky 트렌드 피드",
        item_id=uri,
        dedupe_key=uri,
        title=title,
        source_url=source_url,
        category=f"Bluesky 트렌드 · {topic_label}" if topic_label else "Bluesky 트렌드",
        published_label=created_at if isinstance(created_at, str) and created_at.strip() else "",
        age_minutes=_age_minutes_from_iso(created_at, now),
        comments=_count(post.get("replyCount")),
        reposts=_count(post.get("repostCount")),
        likes=_count(post.get("likeCount")),
        quotes=_count(post.get("quoteCount")),
        position=position,
        attachment_kind=attachment_kind,
        media_kinds=media_kinds,
        language=language,
        sensitive=sensitive,
        spoiler_text="",
    )


def parse_bluesky_feed(
    payload: Any,
    *,
    topic: str = "",
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    reference = now or datetime.now(UTC)
    if not isinstance(payload, dict) or not isinstance(payload.get("feed"), list):
        raise ValueError("Bluesky trend feed 응답 스키마가 맞지 않음")
    items: list[dict[str, Any]] = []
    for entry in payload["feed"]:
        reason = entry.get("reason") if isinstance(entry, dict) else None
        if isinstance(reason, dict) and str(reason.get("$type") or "").endswith("#reasonRepost"):
            continue
        try:
            item = parse_bluesky_post(entry, position=len(items), now=reference, topic=topic)
        except Exception:
            continue
        if item is not None:
            items.append(item)
    return items


def _bluesky_feed_uri(link: Any) -> str | None:
    """Convert a public topic link into the AT URI accepted by getFeed."""
    if not isinstance(link, str):
        return None
    parts = [part for part in link.strip().split("/") if part]
    if len(parts) != 4 or parts[0] != "profile" or parts[2] != "feed":
        return None
    actor, rkey = parts[1], parts[3]
    if not actor.startswith("did:") or not rkey:
        return None
    return f"at://{actor}/app.bsky.feed.generator/{rkey}"


def dedupe_federated_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """공식 URI/ID 정확 일치로만 중복을 제거한다. 첫 관찰을 남긴다."""
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get("dedupe_key") or f"{item.get('community_source')}:{item.get('id')}")
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


async def collect_federated_community_sources(
    session: httpx.AsyncClient,
    *,
    now: datetime | None = None,
    mastodon_limit: int = 20,
    bluesky_topic_limit: int = 10,
    bluesky_topic_feed_limit: int = 5,
    bluesky_posts_per_topic: int = 8,
    lemmy_limit: int = 20,
    timeout: float = 12.0,
) -> dict[str, Any]:
    """세 계열 소스를 서로 격리한 채 수집해 표준 item 목록을 돌려준다.

    반환: {"items": [...], "source_health": {key: bool}, "errors": [str, ...]}
    """
    reference = now or datetime.now(UTC)
    request_timeout = httpx.Timeout(timeout, connect=5.0)
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    source_health = {str(source["key"]): False for source in FEDERATED_COMMUNITY_SOURCES}

    async def fetch_lemmy() -> list[dict[str, Any]]:
        response = await session.get(
            LEMMY_HOT_POSTS_URL,
            params={"sort": "Hot", "limit": lemmy_limit},
            timeout=request_timeout,
        )
        response.raise_for_status()
        return parse_lemmy_hot(response.json(), now=reference)

    lemmy_task = asyncio.create_task(fetch_lemmy())

    try:
        response = await session.get(
            MASTODON_TRENDS_URL,
            params={"limit": mastodon_limit},
            timeout=request_timeout,
        )
        response.raise_for_status()
        parsed = parse_mastodon_trends(response.json(), now=reference)
        items.extend(parsed)
        source_health["mastodon_trends"] = bool(parsed)
        if not parsed:
            errors.append("Mastodon 트렌드: 응답은 왔으나 정규화 항목 0건")
    except Exception as exc:
        errors.append(f"Mastodon 트렌드 수집 실패: {exc.__class__.__name__}")

    bluesky_items: list[dict[str, Any]] = []
    try:
        response = await session.get(
            BLUESKY_TRENDING_TOPICS_URL,
            params={"limit": bluesky_topic_limit},
            timeout=request_timeout,
        )
        response.raise_for_status()
        topics_payload = response.json()
        if not isinstance(topics_payload, dict) or not isinstance(topics_payload.get("topics"), list):
            raise ValueError("getTrendingTopics 응답 스키마가 맞지 않음")
        topics: list[tuple[str, str]] = []
        for entry in topics_payload["topics"]:
            if not isinstance(entry, dict):
                continue
            feed_uri = _bluesky_feed_uri(entry.get("link"))
            topic = str(entry.get("displayName") or entry.get("topic") or "").strip()
            if feed_uri and topic:
                topics.append((topic, feed_uri))
            if len(topics) >= bluesky_topic_feed_limit:
                break
        if not topics:
            errors.append("Bluesky 트렌드: 수화 가능한 주제 피드가 없음")

        async def fetch_topic(topic: str, feed_uri: str) -> tuple[str, list[dict[str, Any]]]:
            feed_response = await session.get(
                BLUESKY_FEED_URL,
                params={"feed": feed_uri, "limit": bluesky_posts_per_topic},
                timeout=request_timeout,
            )
            feed_response.raise_for_status()
            return topic, parse_bluesky_feed(feed_response.json(), topic=topic, now=reference)

        topic_results = await asyncio.gather(
            *(fetch_topic(topic, feed_uri) for topic, feed_uri in topics),
            return_exceptions=True,
        )
        for (topic, _), result in zip(topics, topic_results, strict=True):
            if isinstance(result, BaseException):
                exc = result
                errors.append(f"Bluesky 주제 피드 실패({topic[:32]}…): {exc.__class__.__name__}")
                continue
            _, parsed = result
            bluesky_items.extend(parsed)
    except Exception as exc:
        errors.append(f"Bluesky 트렌드 수집 실패: {exc.__class__.__name__}")

    items.extend(bluesky_items)
    source_health["bluesky_trending"] = bool(bluesky_items)
    try:
        lemmy_items = await lemmy_task
        items.extend(lemmy_items)
        source_health["lemmy_hot"] = bool(lemmy_items)
        if not lemmy_items:
            errors.append("Lemmy Hot: 응답은 왔으나 정규화 항목 0건")
    except Exception as exc:
        errors.append(f"Lemmy Hot 수집 실패: {exc.__class__.__name__}")
    return {"items": dedupe_federated_items(items), "source_health": source_health, "errors": errors}
