"""Tests for the Reddit hot post collector and parser."""

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.reddit import (
    _ATTACHMENT_IMAGE,
    _ATTACHMENT_TEXT,
    _ATTACHMENT_UNKNOWN,
    _ATTACHMENT_VIDEO,
    _parse_reddit_listing,
    _reddit_attachment_info,
)


def test_reddit_attachment_info_detects_video():
    # 1. is_video=True + reddit_video fallback_url
    video_item = {
        "is_video": True,
        "media": {"reddit_video": {"fallback_url": "https://v.redd.it/test/DASH_720.mp4"}},
        "domain": "v.redd.it",
    }
    kind, url = _reddit_attachment_info(video_item)
    assert kind == _ATTACHMENT_VIDEO
    assert url == "https://v.redd.it/test/DASH_720.mp4"

    # 2. post_hint=hosted:video + preview
    preview_item = {
        "is_video": False,
        "post_hint": "hosted:video",
        "preview": {"reddit_video_preview": {"fallback_url": "https://v.redd.it/preview.mp4"}},
    }
    kind, url = _reddit_attachment_info(preview_item)
    assert kind == _ATTACHMENT_VIDEO
    assert url == "https://v.redd.it/preview.mp4"

    # 3. video domain (youtube)
    yt_item = {
        "domain": "youtube.com",
        "url": "https://www.youtube.com/watch?v=12345",
    }
    kind, url = _reddit_attachment_info(yt_item)
    assert kind == _ATTACHMENT_VIDEO
    assert url == "https://www.youtube.com/watch?v=12345"


def test_reddit_attachment_info_detects_image_and_text():
    # 1. post_hint=image
    img_item = {
        "post_hint": "image",
        "domain": "i.redd.it",
        "url": "https://i.redd.it/test.png",
    }
    kind, url = _reddit_attachment_info(img_item)
    assert kind == _ATTACHMENT_IMAGE
    assert url == ""

    # 2. is_self=True
    text_item = {
        "is_self": True,
        "domain": "self.mildlyinteresting",
    }
    kind, url = _reddit_attachment_info(text_item)
    assert kind == _ATTACHMENT_TEXT
    assert url == ""


def test_parse_reddit_listing_builds_canonical_dicts():
    raw_payload = {
        "kind": "Listing",
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "id": "post_1",
                        "title": "Shocking dashcam footage on highway",
                        "url": "https://v.redd.it/vid1/DASH_1080.mp4",
                        "permalink": "/r/videos/comments/post_1/dashcam/",
                        "subreddit": "videos",
                        "author": "driver1",
                        "score": 12000,
                        "ups": 12000,
                        "num_comments": 450,
                        "created_utc": 1787040000.0,
                        "is_video": True,
                        "media": {"reddit_video": {"fallback_url": "https://v.redd.it/vid1/DASH_1080.mp4"}},
                    },
                },
                {
                    "kind": "t3",
                    "data": {
                        "id": "post_2",
                        "title": "오늘자 한강 일몰 사진",
                        "url": "https://i.redd.it/sunset.jpg",
                        "permalink": "/r/korea/comments/post_2/sunset/",
                        "subreddit": "korea",
                        "author": "seoulite",
                        "score": 550,
                        "ups": 550,
                        "num_comments": 30,
                        "created_utc": 1787043600.0,
                        "post_hint": "image",
                    },
                },
            ]
        },
    }

    items = _parse_reddit_listing(raw_payload)
    assert len(items) == 2

    first = items[0]
    assert first["id"] == "post_1"
    assert first["title"] == "Shocking dashcam footage on highway"
    assert first["subreddit"] == "videos"
    assert first["source"] == "Reddit (r/videos)"
    assert first["publisher"] == "r/videos"
    assert first["attachment_kind"] == _ATTACHMENT_VIDEO
    assert first["video_url"] == "https://v.redd.it/vid1/DASH_1080.mp4"
    assert first["votes"] == 12000
    assert first["comments"] == 450
    assert first["language"] == "en"
    assert first["is_korean"] is False
    assert first["source_published_at"] is not None

    second = items[1]
    assert second["id"] == "post_2"
    assert second["title"] == "오늘자 한강 일몰 사진"
    assert second["attachment_kind"] == _ATTACHMENT_IMAGE
    assert second["video_url"] == ""
    assert second["language"] == "ko"
    assert second["is_korean"] is True
