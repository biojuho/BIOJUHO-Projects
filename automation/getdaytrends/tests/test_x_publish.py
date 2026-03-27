from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("notebooklm_automation", reason="notebooklm_automation package unavailable")

from notebooklm_automation.config import reset_config
from notebooklm_automation.publishers.twitter import post_tweet


@pytest.fixture(autouse=True)
def reset_notebooklm_x_config():
    reset_config()
    yield
    reset_config()


@pytest.fixture
def x_publish_request():
    return {
        "tweet_text": "AI 에이전트 트렌드 분석 완료! 2026년 핵심 이슈를 빠르게 확인하세요.",
        "x_access_token": "test_token_12345",
    }


class TestXPublishEndpoint:
    @pytest.mark.asyncio
    async def test_publish_x_success(self, x_publish_request):
        mock_result = {"ok": True, "tweet_id": "1234567890"}

        with patch("notebooklm_api.post_tweet", new_callable=AsyncMock, return_value=mock_result):
            from notebooklm_api import XPublishRequest, run_publish_x

            req = XPublishRequest(**x_publish_request)
            result = await run_publish_x(req)

        assert result.ok is True
        assert result.tweet_id == "1234567890"
        assert "1234567890" in result.tweet_url

    @pytest.mark.asyncio
    async def test_publish_x_no_token(self, monkeypatch):
        monkeypatch.delenv("X_ACCESS_TOKEN", raising=False)

        from notebooklm_api import XPublishRequest, run_publish_x

        req = XPublishRequest(tweet_text="테스트 트윗", x_access_token="")
        result = await run_publish_x(req)

        assert result.ok is False
        assert "X_ACCESS_TOKEN" in result.error

    @pytest.mark.asyncio
    async def test_publish_x_too_long(self):
        from notebooklm_api import XPublishRequest, run_publish_x

        req = XPublishRequest(tweet_text="A" * 281, x_access_token="test_token")
        result = await run_publish_x(req)

        assert result.ok is False
        assert "280" in result.error

    @pytest.mark.asyncio
    async def test_publish_x_api_failure(self, x_publish_request):
        mock_result = {"ok": False, "error": "Rate limit exceeded", "code": 429}

        with patch("notebooklm_api.post_tweet", new_callable=AsyncMock, return_value=mock_result):
            from notebooklm_api import XPublishRequest, run_publish_x

            req = XPublishRequest(**x_publish_request)
            result = await run_publish_x(req)

        assert result.ok is False
        assert "Rate limit" in result.error


class TestXPublishRequest:
    def test_valid_request(self, x_publish_request):
        from notebooklm_api import XPublishRequest

        req = XPublishRequest(**x_publish_request)

        assert req.tweet_text == x_publish_request["tweet_text"]
        assert req.x_access_token == "test_token_12345"

    def test_token_optional(self):
        from notebooklm_api import XPublishRequest

        req = XPublishRequest(tweet_text="테스트")

        assert req.x_access_token == ""

    def test_empty_text_accepted_by_model(self):
        from notebooklm_api import XPublishRequest

        req = XPublishRequest(tweet_text="")

        assert req.tweet_text == ""


class TestPostTweet:
    @pytest.mark.asyncio
    async def test_no_token_returns_error(self):
        result = await post_tweet(text="test", access_token="")

        assert result["ok"] is False
        assert "X_ACCESS_TOKEN" in result["error"]

    @pytest.mark.asyncio
    async def test_over_280_returns_error(self):
        result = await post_tweet(text="X" * 281, access_token="tok")

        assert result["ok"] is False
        assert "280" in result["error"]

    @pytest.mark.asyncio
    async def test_success_returns_tweet_url(self):
        response = MagicMock()
        response.status_code = 201
        response.text = ""
        response.json.return_value = {"data": {"id": "42"}}

        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        client.post.return_value = response

        with patch("notebooklm_automation.publishers.twitter.httpx.AsyncClient", return_value=client):
            result = await post_tweet(text="hello", access_token="token")

        assert result["ok"] is True
        assert result["tweet_id"] == "42"
        assert result["tweet_url"].endswith("/42")
