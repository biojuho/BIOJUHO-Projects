"""
X/Twitter 발행 엔드포인트 테스트
"""
import pytest
from unittest.mock import AsyncMock, patch

# notebooklm_api.py는 notebooklm_automation을 사용하므로 미설치 시 skip
_nlm_available = True
try:
    import notebooklm_automation  # noqa: F401
except ImportError:
    _nlm_available = False

_skip_nlm = pytest.mark.skipif(
    not _nlm_available,
    reason="notebooklm_automation 패키지 미설치 (notebooklm_api 의존)",
)

@pytest.fixture
def x_publish_request():
    return {
        "tweet_text": "🔥 AI 에이전트 트렌드 분석 완료! 2026년 핵심 키워드를 확인하세요.",
        "x_access_token": "test_token_12345",
    }


@_skip_nlm
class TestXPublishEndpoint:
    """POST /publish-x 엔드포인트 테스트."""

    @pytest.mark.asyncio
    async def test_publish_x_success(self, x_publish_request):
        """X 발행 성공 시 tweet_id와 tweet_url 반환."""
        mock_result = {"ok": True, "tweet_id": "1234567890"}

        with patch("notebooklm_api.post_to_x_async", new_callable=AsyncMock, return_value=mock_result):
            from notebooklm_api import run_publish_x, XPublishRequest

            req = XPublishRequest(**x_publish_request)
            result = await run_publish_x(req)

            assert result.ok is True
            assert result.tweet_id == "1234567890"
            assert "1234567890" in result.tweet_url

    @pytest.mark.asyncio
    async def test_publish_x_no_token(self):
        """토큰 미설정 시 실패 반환."""
        with patch.dict("os.environ", {"X_ACCESS_TOKEN": ""}, clear=False):
            from notebooklm_api import run_publish_x, XPublishRequest

            req = XPublishRequest(tweet_text="테스트 트윗", x_access_token="")
            result = await run_publish_x(req)

            assert result.ok is False
            assert "미설정" in result.error

    @pytest.mark.asyncio
    async def test_publish_x_too_long(self, x_publish_request):
        """280자 초과 트윗 거부."""
        from notebooklm_api import run_publish_x, XPublishRequest

        long_text = "A" * 281
        req = XPublishRequest(tweet_text=long_text, x_access_token="test_token")
        result = await run_publish_x(req)

        assert result.ok is False
        assert "280자 초과" in result.error

    @pytest.mark.asyncio
    async def test_publish_x_api_failure(self, x_publish_request):
        """X API 호출 실패 시 에러 전달."""
        mock_result = {"ok": False, "error": "Rate limit exceeded", "code": 429}

        with patch("notebooklm_api.post_to_x_async", new_callable=AsyncMock, return_value=mock_result):
            from notebooklm_api import run_publish_x, XPublishRequest

            req = XPublishRequest(**x_publish_request)
            result = await run_publish_x(req)

            assert result.ok is False
            assert "Rate limit" in result.error


@_skip_nlm
class TestXPublishRequest:
    """XPublishRequest 모델 유효성 검사."""

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
        """Pydantic은 빈 문자열을 허용 (280자 제한은 엔드포인트에서 처리)."""
        from notebooklm_api import XPublishRequest
        req = XPublishRequest(tweet_text="")
        assert req.tweet_text == ""


class TestPostToXAsync:
    """scraper.post_to_x_async 함수 테스트."""

    @pytest.mark.asyncio
    async def test_no_token_returns_error(self):
        from scraper import post_to_x_async
        result = await post_to_x_async(content="test", access_token="")
        assert result["ok"] is False
        assert "미설정" in result["error"]

    @pytest.mark.asyncio
    async def test_over_280_returns_error(self):
        from scraper import post_to_x_async
        result = await post_to_x_async(content="X" * 281, access_token="tok")
        assert result["ok"] is False
        assert "280자" in result["error"]
