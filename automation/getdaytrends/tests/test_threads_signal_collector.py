"""Tests for the optional official Threads signal collector."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from threads_signal_collector import _normalize_posts  # noqa: E402


def test_normalize_threads_posts_keeps_recent_direct_permalinks():
    now = datetime.now(UTC)
    payload = {
        "data": [
            {
                "id": "1",
                "permalink": "https://www.threads.com/@creator/post/one",
                "username": "creator",
                "text": "실제 최근 게시물",
                "timestamp": (now - timedelta(minutes=20)).isoformat(),
                "is_verified": True,
                "has_replies": True,
            },
            {
                "id": "2",
                "permalink": "javascript:alert(1)",
                "username": "unsafe",
                "text": "안전하지 않은 링크",
                "timestamp": now.isoformat(),
            },
        ]
    }

    posts = _normalize_posts(payload, 5)

    assert posts == [
        {
            "id": "1",
            "permalink": "https://www.threads.com/@creator/post/one",
            "username": "creator",
            "text": "실제 최근 게시물",
            "timestamp": payload["data"][0]["timestamp"],
            "is_verified": True,
            "has_replies": True,
        }
    ]
