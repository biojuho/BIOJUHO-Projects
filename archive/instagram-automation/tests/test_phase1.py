"""Tests for rate limiter, trend bridge, and image generator."""

import asyncio
import sys
from pathlib import Path

import pytest

# Ensure project root is available
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---- Rate Limiter Tests ----


class TestMetaRateLimiter:
    """Tests for MetaRateLimiter."""

    def test_basic_acquire(self):
        from services.rate_limiter import MetaRateLimiter

        limiter = MetaRateLimiter(max_calls=10, window=60)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(limiter.acquire())
        assert limiter.remaining == 8  # 10 * 0.9 = 9, -1 = 8
        loop.close()

    def test_remaining_count(self):
        from services.rate_limiter import MetaRateLimiter

        limiter = MetaRateLimiter(max_calls=10, window=60)
        loop = asyncio.new_event_loop()
        for _ in range(5):
            loop.run_until_complete(limiter.acquire())
        assert limiter.remaining == 4  # 9 effective - 5 used = 4
        loop.close()

    def test_usage_pct(self):
        from services.rate_limiter import MetaRateLimiter

        limiter = MetaRateLimiter(max_calls=10, window=60)
        loop = asyncio.new_event_loop()
        for _ in range(3):
            loop.run_until_complete(limiter.acquire())
        assert 30 < limiter.usage_pct < 40  # ~33%
        loop.close()

    def test_rate_limit_exceeded_no_block(self):
        from services.rate_limiter import MetaRateLimiter, RateLimitExceeded

        # Very small limit for testing
        limiter = MetaRateLimiter(max_calls=2, window=3600, block=False, safety_margin=1.0)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(limiter.acquire())
        loop.run_until_complete(limiter.acquire())
        with pytest.raises(RateLimitExceeded):
            loop.run_until_complete(limiter.acquire())
        loop.close()

    def test_stats(self):
        from services.rate_limiter import MetaRateLimiter

        limiter = MetaRateLimiter(max_calls=100, window=60)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(limiter.acquire())
        stats = limiter.get_stats()
        assert stats["calls_in_window"] == 1
        assert stats["total_blocked"] == 0
        assert stats["remaining"] > 0
        loop.close()


# ---- Trend Bridge Tests ----


class TestTrendBridge:
    """Tests for TrendBridge."""

    def test_default_fallback_topics(self):
        from services.trend_bridge import TrendBridge

        bridge = TrendBridge(db_path="/nonexistent/path.db")
        topics = bridge.get_default_fallback_topics()
        assert len(topics) == 4
        assert all(isinstance(t, str) for t in topics)

    def test_get_trending_topics_missing_db(self):
        from services.trend_bridge import TrendBridge

        bridge = TrendBridge(db_path="/nonexistent/path.db")
        topics = bridge.get_trending_topics()
        assert topics == []

    def test_topics_to_instagram_format(self):
        from services.trend_bridge import TrendBridge

        bridge = TrendBridge(db_path="/nonexistent/path.db")
        mock_trends = [
            {
                "keyword": "AI 혁명",
                "category": "테크",
                "why_trending": "OpenAI 신모델 발표",
                "viral_potential": 85,
            },
            {
                "keyword": "봄날씨",
                "category": "생활",
                "why_trending": "",
                "viral_potential": 70,
            },
        ]
        topics = bridge.topics_to_instagram_topics(trends=mock_trends, max_topics=2)
        assert len(topics) == 2
        assert "AI 혁명" in topics[0]
        assert "테크" in topics[0]
        assert "봄날씨" in topics[1]


# ---- Image Generator Tests ----


class TestImageGenerator:
    """Tests for ImageGenerator."""

    def test_validate_url_jpeg(self):
        from services.image_generator import ImageGenerator

        assert ImageGenerator.validate_image_url("https://cdn.example.com/photo.jpg")
        assert ImageGenerator.validate_image_url("https://cdn.example.com/photo.jpeg")
        assert not ImageGenerator.validate_image_url("https://cdn.example.com/photo.png")
        assert not ImageGenerator.validate_image_url("http://insecure.com/photo.jpg")

    def test_validate_url_cdn(self):
        from services.image_generator import ImageGenerator

        assert ImageGenerator.validate_image_url("https://storage.googleapis.com/bucket/image")
        assert ImageGenerator.validate_image_url("https://firebasestorage.googleapis.com/v0/b/bucket/image.jpg")

    def test_make_filename(self):
        from services.image_generator import ImageGenerator

        gen = ImageGenerator()
        fname = gen._make_filename("AI 트렌드 2026")
        assert fname.startswith("ig_")
        assert fname.endswith(".jpg")

    def test_ensure_jpeg_already_jpeg(self):
        from services.image_generator import ImageGenerator

        result = ImageGenerator.ensure_jpeg("/some/path/image.jpg")
        assert result == "/some/path/image.jpg"

        result = ImageGenerator.ensure_jpeg("/some/path/image.jpeg")
        assert result == "/some/path/image.jpeg"
