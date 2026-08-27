"""Tests for the federated community (Mastodon·Bluesky) normalizers.

전부 합성 fixture로 돌며 네트워크를 쓰지 않는다. 실물 GET 결과는 반환 문서에 기록한다.
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from federated_community_sources import (  # noqa: E402
    BLUESKY_FEED_URL,
    BLUESKY_TRENDING_TOPICS_URL,
    FEDERATED_COMMUNITY_SOURCES,
    LEMMY_HOT_POSTS_URL,
    MASTODON_TRENDS_URL,
    _bluesky_feed_uri,
    collect_federated_community_sources,
    dedupe_federated_items,
    parse_bluesky_feed,
    parse_lemmy_hot,
    parse_mastodon_trends,
)

NOW = datetime(2026, 8, 27, 3, 0, tzinfo=UTC)


def mastodon_status(**overrides):
    status = {
        "id": "117162740724901163",
        "uri": "https://framapiaf.org/users/davidrevoy/statuses/117162736923099956",
        "url": "https://framapiaf.org/@davidrevoy/117162736923099956",
        "created_at": "2026-08-26T16:24:00.000Z",
        "content": "<p>The Minions of <strong>Avian</strong> Intelligence</p>",
        "language": "en",
        "sensitive": False,
        "spoiler_text": "",
        "replies_count": 16,
        "reblogs_count": 500,
        "favourites_count": 641,
        "quotes_count": 7,
        "media_attachments": [],
    }
    status.update(overrides)
    return status


def test_federated_source_registry_keys():
    assert [source["key"] for source in FEDERATED_COMMUNITY_SOURCES] == [
        "mastodon_trends",
        "bluesky_trending",
        "lemmy_hot",
    ]


def test_parse_mastodon_maps_standard_schema_fields():
    items = parse_mastodon_trends([mastodon_status()], now=NOW)
    assert items == [
        {
            "id": "117162740724901163",
            "title": "The Minions of Avian Intelligence",
            "category": "Mastodon 트렌드",
            "community_source": "mastodon_trends",
            "community_label": "Mastodon 트렌드",
            "source_url": "https://framapiaf.org/@davidrevoy/117162736923099956",
            "link_kind": "publisher_original",
            "published_label": "2026-08-26T16:24:00.000Z",
            "age_minutes": 636,
            "views": 0,
            "votes": 500,
            "comments": 16,
            "source_position": 0,
            "signal_source": "글로벌 공개 커뮤니티",
            "attachment_kind": "text",
            "video_url": "",
            "dedupe_key": "https://framapiaf.org/users/davidrevoy/statuses/117162736923099956",
            "reposts": 500,
            "likes": 641,
            "quotes": 7,
            "language": "en",
            "region": None,
            "sensitive": False,
            "political": None,
            "spoiler_text": "",
            "media_kinds": [],
        }
    ]


def test_parse_mastodon_video_beats_image_and_keeps_raw_kinds():
    item = parse_mastodon_trends(
        [
            mastodon_status(
                media_attachments=[
                    {"type": "image", "url": "https://files.example/a.png"},
                    {"type": "gifv", "url": "https://files.example/b.mp4"},
                ]
            )
        ],
        now=NOW,
    )[0]
    assert item["attachment_kind"] == "video"
    assert item["media_kinds"] == ["image", "gifv"]
    assert item["video_url"] == ""


def test_parse_mastodon_unknown_kind_stays_unknown_but_raw_kept():
    item = parse_mastodon_trends([mastodon_status(media_attachments=[{"type": "audio"}])], now=NOW)[0]
    assert item["attachment_kind"] == "unknown"
    assert item["media_kinds"] == ["audio"]


def test_parse_mastodon_strips_html_and_caps_title():
    long_text = "가" * 300
    item = parse_mastodon_trends([mastodon_status(content=f"<p>{long_text}</p><p><a href='x'>링크</a></p>")], now=NOW)[
        0
    ]
    assert len(item["title"]) <= 160
    assert "<" not in item["title"]


def test_parse_mastodon_sensitive_and_spoiler_preserved():
    item = parse_mastodon_trends([mastodon_status(sensitive=True, spoiler_text="정치 이야기")], now=NOW)[0]
    assert item["sensitive"] is True
    assert item["spoiler_text"] == "정치 이야기"
    assert item["political"] is None


def test_parse_mastodon_unwraps_reblog_wrapper():
    inner = mastodon_status(id="inner-1")
    item = parse_mastodon_trends([{"reblog": inner, "id": "outer"}], now=NOW)[0]
    assert item["id"] == "inner-1"


def test_parse_mastodon_isolates_malformed_and_partial_entries():
    items = parse_mastodon_trends(
        [
            {"id": "no-uri"},
            "garbage",
            mastodon_status(
                id="ok-1",
                created_at="not-a-date",
                replies_count=None,
                reblogs_count="많음",
                favourites_count=True,
                language="",
            ),
        ],
        now=NOW,
    )
    assert len(items) == 1
    item = items[0]
    assert item["id"] == "ok-1"
    assert item["age_minutes"] is None
    assert item["published_label"] == "not-a-date"
    assert item["comments"] == 0
    assert item["reposts"] == 0
    assert item["likes"] == 0
    assert item["language"] is None
    assert item["sensitive"] is False


def test_parse_mastodon_rejects_non_list_payload():
    with pytest.raises(ValueError):
        parse_mastodon_trends({"unexpected": True}, now=NOW)


def bluesky_post(**overrides):
    record = {
        "$type": "app.bsky.feed.post",
        "text": "Big video update! Videos up to 10 minutes.",
        "createdAt": "2026-08-26T17:54:20.292Z",
        "langs": ["en"],
    }
    post = {
        "uri": "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.post/3mtwf7gxkwc2r",
        "cid": "bafyreibgcyus5ny5ndz4thticcdztgeqrz3zqo6p2vicuquueilrp23jqq",
        "author": {"did": "did:plc:z72i7hdynmk6r22z27h6tvur", "handle": "bsky.app"},
        "record": record,
        "labels": [],
        "replyCount": 224,
        "repostCount": 1186,
        "likeCount": 4845,
        "quoteCount": 499,
    }
    post.update(overrides)
    return {"post": post}


def test_parse_bluesky_maps_counts_langs_and_source_url():
    items = parse_bluesky_feed({"feed": [bluesky_post()]}, topic="AI video", now=NOW)
    item = items[0]
    assert item["comments"] == 224
    assert item["reposts"] == 1186
    assert item["votes"] == 1186
    assert item["likes"] == 4845
    assert item["quotes"] == 499
    assert item["language"] == "en"
    assert item["age_minutes"] == 546
    assert item["source_url"] == "https://bsky.app/profile/bsky.app/post/3mtwf7gxkwc2r"
    assert item["dedupe_key"] == item["id"]
    assert item["attachment_kind"] == "text"
    assert item["region"] is None
    assert item["community_source"] == "bluesky_trending"
    assert item["category"] == "Bluesky 트렌드 · AI video"


def test_parse_bluesky_video_embed_kind():
    entry = bluesky_post()
    entry["post"]["record"]["embed"] = {
        "$type": "app.bsky.embed.video",
        "ref": {"$link": "bafk"},
        "aspectRatio": {"width": 1280, "height": 720},
    }
    item = parse_bluesky_feed({"feed": [entry]}, now=NOW)[0]
    assert item["attachment_kind"] == "video"
    assert item["media_kinds"] == ["app.bsky.embed.video"]
    assert item["video_url"] == ""


def test_parse_bluesky_record_with_media_unwraps_images():
    entry = bluesky_post()
    entry["post"]["record"]["embed"] = {
        "$type": "app.bsky.embed.recordWithMedia",
        "record": {"record": {"uri": "at://x/y/z", "cid": "b"}},
        "media": {"$type": "app.bsky.embed.images", "images": [{"image": {"$link": "b"}}]},
    }
    item = parse_bluesky_feed({"feed": [entry]}, now=NOW)[0]
    assert item["attachment_kind"] == "image"


def test_parse_bluesky_quote_embed_stays_unknown():
    entry = bluesky_post()
    entry["post"]["record"]["embed"] = {
        "$type": "app.bsky.embed.record",
        "record": {"uri": "at://x/y/z", "cid": "b"},
    }
    item = parse_bluesky_feed({"feed": [entry]}, now=NOW)[0]
    assert item["attachment_kind"] == "unknown"


def test_parse_bluesky_sensitive_labels_true_and_absent_stays_unknown():
    flagged = bluesky_post()
    flagged["post"]["record"]["labels"] = {
        "$type": "com.atproto.label.defs#selfLabels",
        "values": [{"val": "graphic-media"}],
    }
    assert parse_bluesky_feed({"feed": [flagged]}, now=NOW)[0]["sensitive"] is True
    assert parse_bluesky_feed({"feed": [bluesky_post()]}, now=NOW)[0]["sensitive"] is None


def test_parse_bluesky_skips_reposts_and_invalid_entries():
    repost_entry = bluesky_post()
    repost_entry["reason"] = {"$type": "app.bsky.feed.defs#reasonRepost"}
    feed = {
        "feed": [
            repost_entry,
            {"post": {"uri": "at://a/b/c", "record": {"$type": "app.bsky.feed.like"}}},
            {"post": {"record": {"$type": "app.bsky.feed.post", "createdAt": None, "text": ""}}},
            bluesky_post(),
        ]
    }
    items = parse_bluesky_feed(feed, now=NOW)
    assert len(items) == 1
    assert items[0]["title"].startswith("Big video update")
    assert items[0]["source_position"] == 0


def test_parse_bluesky_rejects_bad_payload():
    with pytest.raises(ValueError):
        parse_bluesky_feed(["not", "a", "dict"], now=NOW)
    with pytest.raises(ValueError):
        parse_bluesky_feed({"cursor": "x"}, now=NOW)


def test_dedupe_uses_official_uri_exact_match_only():
    base = parse_mastodon_trends([mastodon_status()], now=NOW)[0]
    duplicate = dict(base)
    same_title_different_uri = dict(
        base,
        id="other-1",
        dedupe_key="https://other.example/statuses/1",
        source_url="https://other.example/@x/1",
    )
    result = dedupe_federated_items([base, duplicate, same_title_different_uri])
    assert len(result) == 2
    assert result[0] is base
    assert result[1]["id"] == "other-1"


def lemmy_post(**overrides):
    post = {
        "id": 42,
        "name": "Dashcam captures an unexpected roadside rescue",
        "published": "2026-08-27T02:35:00.000Z",
        "ap_id": "https://lemmy.world/post/42",
        "url": "https://video.example/rescue.mp4",
        "nsfw": False,
    }
    post.update(overrides)
    return {
        "post": post,
        "counts": {"comments": 18, "score": 72, "upvotes": 80},
        "community": {"name": "interestingasfuck", "title": "Interesting Things"},
    }


def test_parse_lemmy_hot_maps_reactions_time_and_external_video_metadata():
    item = parse_lemmy_hot({"posts": [lemmy_post()]}, now=NOW)[0]
    assert item["community_source"] == "lemmy_hot"
    assert item["source_url"] == "https://lemmy.world/post/42"
    assert item["age_minutes"] == 25
    assert item["votes"] == 72
    assert item["comments"] == 18
    assert item["likes"] == 80
    assert item["attachment_kind"] == "video"
    assert item["video_url"] == ""
    assert item["category"] == "Lemmy · Interesting Things"


def test_parse_lemmy_hot_rejects_bad_schema_and_keeps_nsfw_flag():
    with pytest.raises(ValueError):
        parse_lemmy_hot({"items": []}, now=NOW)
    item = parse_lemmy_hot({"posts": [lemmy_post(nsfw=True)]}, now=NOW)[0]
    assert item["sensitive"] is True


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.calls: list[str] = []

    async def get(self, url, **kwargs):
        self.calls.append(url)
        entry = self.routes.get(url)
        if entry is None:
            raise AssertionError(f"unexpected request: {url}")
        if isinstance(entry, BaseException):
            raise entry
        return entry


TOPICS_OK = FakeResponse(
    {
        "topics": [
            {
                "topic": "AI video",
                "displayName": "AI video",
                "link": "/profile/did:plc:aaa/feed/trend-a",
            },
            {
                "topic": "Dog Day",
                "displayName": "Dog Day",
                "link": "/profile/did:plc:bbb/feed/trend-b",
            },
        ]
    }
)

TREND_FEED_OK = FakeResponse({"feed": [bluesky_post()]})
LEMMY_EMPTY = FakeResponse({"posts": []})


def test_bluesky_topic_link_maps_to_public_feed_uri():
    assert _bluesky_feed_uri("/profile/did:plc:aaa/feed/trend-a") == "at://did:plc:aaa/app.bsky.feed.generator/trend-a"
    assert _bluesky_feed_uri("/search?q=trend") is None


async def test_collect_isolates_mastodon_failure_from_bluesky():
    session = FakeSession(
        {
            MASTODON_TRENDS_URL: RuntimeError("connection failed"),
            BLUESKY_TRENDING_TOPICS_URL: TOPICS_OK,
            BLUESKY_FEED_URL: TREND_FEED_OK,
            LEMMY_HOT_POSTS_URL: LEMMY_EMPTY,
        }
    )
    result = await collect_federated_community_sources(session, now=NOW)
    assert result["source_health"] == {
        "mastodon_trends": False,
        "bluesky_trending": True,
        "lemmy_hot": False,
    }
    assert all(item["community_source"] == "bluesky_trending" for item in result["items"])
    # 두 주제 피드가 같은 응답을 돌려줘도 공식 URI 중복 제거 후 1건만 남는다.
    assert len(result["items"]) == 1
    assert any("Mastodon" in error for error in result["errors"])


async def test_collect_isolates_bluesky_failure_from_mastodon():
    session = FakeSession(
        {
            MASTODON_TRENDS_URL: FakeResponse([mastodon_status()]),
            BLUESKY_TRENDING_TOPICS_URL: FakeResponse(status=500),
            LEMMY_HOT_POSTS_URL: LEMMY_EMPTY,
        }
    )
    result = await collect_federated_community_sources(session, now=NOW)
    assert result["source_health"] == {
        "mastodon_trends": True,
        "bluesky_trending": False,
        "lemmy_hot": False,
    }
    assert [item["community_source"] for item in result["items"]] == ["mastodon_trends"]
    assert any("Bluesky" in error for error in result["errors"])


async def test_collect_isolates_single_bluesky_topic_failure():
    flaky = FakeResponse({"feed": []}, status=503)
    session = FakeSession(
        {
            MASTODON_TRENDS_URL: FakeResponse([]),
            BLUESKY_TRENDING_TOPICS_URL: TOPICS_OK,
            BLUESKY_FEED_URL: TREND_FEED_OK,
            LEMMY_HOT_POSTS_URL: LEMMY_EMPTY,
        }
    )
    flaky_session = FakeSession(
        {
            MASTODON_TRENDS_URL: FakeResponse([]),
            BLUESKY_TRENDING_TOPICS_URL: TOPICS_OK,
            BLUESKY_FEED_URL: flaky,
            LEMMY_HOT_POSTS_URL: LEMMY_EMPTY,
        }
    )
    ok_result = await collect_federated_community_sources(session, now=NOW)
    assert ok_result["source_health"]["bluesky_trending"] is True
    bad_result = await collect_federated_community_sources(flaky_session, now=NOW)
    assert bad_result["source_health"]["bluesky_trending"] is False
    assert bad_result["items"] == []
    assert len(bad_result["errors"]) == 4


async def test_collect_keeps_unknown_age_as_none():
    stale = mastodon_status(created_at=None)
    session = FakeSession(
        {
            MASTODON_TRENDS_URL: FakeResponse([stale]),
            BLUESKY_TRENDING_TOPICS_URL: FakeResponse({"topics": []}),
            LEMMY_HOT_POSTS_URL: LEMMY_EMPTY,
        }
    )
    result = await collect_federated_community_sources(session, now=NOW)
    item = result["items"][0]
    assert item["age_minutes"] is None
    assert item["published_label"] == ""
    assert result["source_health"] == {
        "mastodon_trends": True,
        "bluesky_trending": False,
        "lemmy_hot": False,
    }


async def test_collect_dedupes_across_batch():
    session = FakeSession(
        {
            MASTODON_TRENDS_URL: FakeResponse([mastodon_status(), mastodon_status()]),
            BLUESKY_TRENDING_TOPICS_URL: FakeResponse({"topics": []}),
            LEMMY_HOT_POSTS_URL: LEMMY_EMPTY,
        }
    )
    result = await collect_federated_community_sources(session, now=NOW)
    assert len(result["items"]) == 1


async def test_collect_isolates_mastodon_and_bluesky_failure_from_lemmy():
    session = FakeSession(
        {
            MASTODON_TRENDS_URL: RuntimeError("mastodon down"),
            BLUESKY_TRENDING_TOPICS_URL: RuntimeError("bluesky down"),
            LEMMY_HOT_POSTS_URL: FakeResponse({"posts": [lemmy_post()]}),
        }
    )
    result = await collect_federated_community_sources(session, now=NOW)
    assert result["source_health"] == {
        "mastodon_trends": False,
        "bluesky_trending": False,
        "lemmy_hot": True,
    }
    assert [item["community_source"] for item in result["items"]] == ["lemmy_hot"]


def test_age_boundary_three_hours():
    edge = mastodon_status(created_at=(NOW - timedelta(hours=3)).isoformat().replace("+00:00", "Z"))
    item = parse_mastodon_trends([edge], now=NOW)[0]
    assert item["age_minutes"] == 180


def test_timezone_less_timestamp_stays_unknown():
    item = parse_mastodon_trends(
        [mastodon_status(created_at="2026-08-26T23:59:00")],
        now=NOW,
    )[0]
    assert item["age_minutes"] is None
