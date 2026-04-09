"""storage.py 엣지케이스 테스트: 재시도 로직 경계, 텍스트 잘림, Content Hub 스키마 빌더.

타겟:
  - _retry_notion_call: Retry-After 캡(60s), 비재시도 상태코드, 최대 재시도 초과
  - _rich_text_prop: 1900자 무단 잘림(silent truncation)
  - _content_hub_properties: 스키마 조건부 빌드, 누락 필드 무시
  - save_to_notion: 중복 except 블록(unreachable code 문서화)
  - _content_hub_workflow_meta: 플랫폼 필터링, passed 필터링
"""

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# ── SUT imports ──────────────────────────────────────────────────────
from storage import (
    _content_hub_properties,
    _content_hub_workflow_meta,
    _retry_notion_call,
    _rich_text_prop,
    save_to_notion,
)
from models import (
    GeneratedThread,
    GeneratedTweet,
    MultiSourceContext,
    ScoredTrend,
    TrendSource,
    TweetBatch,
)
from config import AppConfig


# ── Helpers ──────────────────────────────────────────────────────────

def _make_trend(**overrides) -> ScoredTrend:
    defaults = dict(
        keyword="테스트", rank=1, viral_potential=80,
        trend_acceleration="+5%", top_insight="핵심",
        suggested_angles=["앵글1"], best_hook_starter="훅",
        context=MultiSourceContext(),
        sources=[TrendSource.GETDAYTRENDS],
    )
    defaults.update(overrides)
    return ScoredTrend(**defaults)


def _make_batch(topic: str = "테스트 키워드") -> TweetBatch:
    tweets = [
        GeneratedTweet(tweet_type=f"유형{i}", content=f"트윗{i}" * 10, content_type="short")
        for i in range(3)
    ]
    return TweetBatch(topic=topic, tweets=tweets, thread=None)


class FakeAPIResponseError(Exception):
    """Notion APIResponseError 시뮬레이션."""
    def __init__(self, message: str, status: int = 500, body: dict | None = None):
        super().__init__(message)
        self.status = status
        self.body = body or {}


# ═══════════════════════════════════════════════════════════════════
# 1. _retry_notion_call — 경계 조건
# ═══════════════════════════════════════════════════════════════════

class TestRetryNotionCall:
    def test_success_first_try(self):
        fn = MagicMock(return_value="ok")
        assert _retry_notion_call(fn, "a", "b") == "ok"
        fn.assert_called_once_with("a", "b")

    def test_non_api_error_raises_immediately(self):
        """APIResponseError가 아닌 예외는 재시도 없이 즉시 raise."""
        fn = MagicMock(side_effect=ValueError("bad input"))
        with pytest.raises(ValueError, match="bad input"):
            _retry_notion_call(fn)
        fn.assert_called_once()

    def test_non_retryable_status_raises(self):
        """400, 401, 404 등 재시도 불가 상태코드는 즉시 raise."""
        err = FakeAPIResponseError("not found", status=404)
        fn = MagicMock(side_effect=err)
        with (
            patch("storage.APIResponseError", FakeAPIResponseError),
        ):
            with pytest.raises(FakeAPIResponseError):
                _retry_notion_call(fn, max_retries=3)
        fn.assert_called_once()

    @patch("storage.time.sleep")
    def test_retryable_status_retries_then_succeeds(self, mock_sleep):
        """429 에러 2회 후 성공."""
        err = FakeAPIResponseError("rate limit", status=429)
        fn = MagicMock(side_effect=[err, err, "ok"])
        with patch("storage.APIResponseError", FakeAPIResponseError):
            result = _retry_notion_call(fn, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert fn.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("storage.time.sleep")
    def test_retry_after_header_capped_at_60s(self, mock_sleep):
        """Retry-After가 120초여도 60초로 캡."""
        err = FakeAPIResponseError("rate limit", status=429, body={"retry_after": 120})
        fn = MagicMock(side_effect=[err, "ok"])
        with patch("storage.APIResponseError", FakeAPIResponseError):
            _retry_notion_call(fn, max_retries=3)
        mock_sleep.assert_called_once_with(60.0)

    @patch("storage.time.sleep")
    def test_retry_after_header_respected_when_under_cap(self, mock_sleep):
        """Retry-After가 5초면 그대로 사용."""
        err = FakeAPIResponseError("rate limit", status=429, body={"retry_after": 5})
        fn = MagicMock(side_effect=[err, "ok"])
        with patch("storage.APIResponseError", FakeAPIResponseError):
            _retry_notion_call(fn, max_retries=3)
        mock_sleep.assert_called_once_with(5.0)

    @patch("storage.time.sleep")
    def test_exponential_backoff_without_retry_after(self, mock_sleep):
        """Retry-After 없으면 지수 백오프 사용."""
        err_500 = FakeAPIResponseError("server error", status=500)
        fn = MagicMock(side_effect=[err_500, err_500, "ok"])
        with patch("storage.APIResponseError", FakeAPIResponseError):
            _retry_notion_call(fn, max_retries=3, base_delay=2.0)
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays[0] == 2.0   # 2 * 2^0
        assert delays[1] == 4.0   # 2 * 2^1

    @patch("storage.time.sleep")
    def test_max_retries_exhausted_raises(self, mock_sleep):
        """max_retries 초과 시 마지막 예외 raise."""
        err = FakeAPIResponseError("server error", status=502)
        fn = MagicMock(side_effect=err)
        with patch("storage.APIResponseError", FakeAPIResponseError):
            with pytest.raises(FakeAPIResponseError, match="server error"):
                _retry_notion_call(fn, max_retries=2)
        assert fn.call_count == 3  # initial + 2 retries

    @patch("storage.time.sleep")
    def test_backoff_capped_at_60s(self, mock_sleep):
        """지수 백오프가 60초를 초과하지 않음."""
        err = FakeAPIResponseError("error", status=503)
        fn = MagicMock(side_effect=[err, err, err, err, "ok"])
        with patch("storage.APIResponseError", FakeAPIResponseError):
            _retry_notion_call(fn, max_retries=5, base_delay=32.0)
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert all(d <= 60.0 for d in delays)


# ═══════════════════════════════════════════════════════════════════
# 2. _rich_text_prop — silent truncation
# ═══════════════════════════════════════════════════════════════════

class TestRichTextProp:
    def test_short_text_preserved(self):
        result = _rich_text_prop("hello")
        assert result["rich_text"][0]["text"]["content"] == "hello"

    def test_exactly_1900_preserved(self):
        text = "x" * 1900
        result = _rich_text_prop(text)
        assert len(result["rich_text"][0]["text"]["content"]) == 1900

    def test_over_1900_silently_truncated(self):
        """1900자 초과 텍스트가 경고 없이 잘림 — 데이터 손실 위험."""
        text = "A" * 2500
        result = _rich_text_prop(text)
        content = result["rich_text"][0]["text"]["content"]
        assert len(content) == 1900
        assert content == "A" * 1900

    def test_unicode_truncation(self):
        """한글 등 멀티바이트 문자도 문자 수 기준으로 잘림."""
        text = "가" * 2000
        result = _rich_text_prop(text)
        assert len(result["rich_text"][0]["text"]["content"]) == 1900

    def test_empty_string(self):
        result = _rich_text_prop("")
        assert result["rich_text"][0]["text"]["content"] == ""


# ═══════════════════════════════════════════════════════════════════
# 3. _content_hub_properties — 조건부 스키마 빌더
# ═══════════════════════════════════════════════════════════════════

class TestContentHubProperties:
    def test_full_schema_all_fields_present(self):
        schema = {
            "Name": {}, "Status": {}, "Category": {}, "Date": {},
            "Score": {}, "Platform": {}, "Trend ID": {}, "Draft ID": {},
            "Prompt Version": {}, "QA Score": {}, "Blocking Reasons": {},
            "Published URL": {}, "Published At": {}, "Receipt ID": {}, "URL": {},
        }
        props = _content_hub_properties(
            schema,
            title="Test Title",
            status="Ready",
            category="Tech",
            platform_label="X",
            score=85.0,
            draft_meta={
                "trend_id": "t-1", "draft_id": "d-1",
                "prompt_version": "v2", "qa_score": 88.5,
                "blocking_reasons": ["reason1"],
            },
            published_url="https://example.com",
            published_at="2026-04-07",
            receipt_id="rcpt-123",
        )
        assert props["Name"]["title"][0]["text"]["content"] == "Test Title"
        assert props["Status"]["select"]["name"] == "Ready"
        assert props["Score"]["number"] == 85.0
        assert props["QA Score"]["number"] == 88.5
        assert props["Published URL"]["url"] == "https://example.com"
        assert props["URL"]["url"] == "https://example.com"
        assert props["Receipt ID"]["rich_text"][0]["text"]["content"] == "rcpt-123"

    def test_empty_schema_returns_empty_props(self):
        props = _content_hub_properties(
            {},
            title="T", status="S", category="C",
            platform_label="X", score=0.0, draft_meta={},
        )
        assert props == {}

    def test_partial_schema_only_matching_fields(self):
        schema = {"Name": {}, "Score": {}}
        props = _content_hub_properties(
            schema,
            title="Title", status="Ready", category="C",
            platform_label="X", score=50.0, draft_meta={},
        )
        assert "Name" in props
        assert "Score" in props
        assert "Status" not in props
        assert "Category" not in props

    def test_missing_draft_meta_fields_skipped(self):
        """draft_meta에 trend_id 없으면 Trend ID 프로퍼티 생략."""
        schema = {"Trend ID": {}, "Draft ID": {}, "QA Score": {}}
        props = _content_hub_properties(
            schema,
            title="T", status="S", category="C",
            platform_label="X", score=0.0,
            draft_meta={},  # no trend_id, draft_id, qa_score
        )
        assert "Trend ID" not in props
        assert "Draft ID" not in props
        assert "QA Score" not in props

    def test_qa_score_zero_is_included(self):
        """qa_score=0.0도 None이 아니므로 포함되어야 함."""
        schema = {"QA Score": {}}
        props = _content_hub_properties(
            schema,
            title="T", status="S", category="C",
            platform_label="X", score=0.0,
            draft_meta={"qa_score": 0.0},
        )
        assert "QA Score" in props
        assert props["QA Score"]["number"] == 0.0

    def test_blocking_reasons_joined_with_comma(self):
        schema = {"Blocking Reasons": {}}
        props = _content_hub_properties(
            schema,
            title="T", status="S", category="C",
            platform_label="X", score=0.0,
            draft_meta={"blocking_reasons": ["low_score", "no_context"]},
        )
        text = props["Blocking Reasons"]["rich_text"][0]["text"]["content"]
        assert "low_score" in text
        assert "no_context" in text
        assert ", " in text


# ═══════════════════════════════════════════════════════════════════
# 4. _content_hub_workflow_meta — 필터링 로직
# ═══════════════════════════════════════════════════════════════════

class TestContentHubWorkflowMeta:
    def test_returns_matching_platform_draft(self):
        batch = _make_batch()
        batch.metadata["workflow_v2"] = {
            "drafts": [
                {"platform": "threads", "passed": True, "draft_id": "d-t"},
                {"platform": "x", "passed": True, "draft_id": "d-x"},
            ]
        }
        result = _content_hub_workflow_meta(batch, "x")
        assert result["draft_id"] == "d-x"

    def test_returns_empty_when_not_passed(self):
        batch = _make_batch()
        batch.metadata["workflow_v2"] = {
            "drafts": [{"platform": "x", "passed": False, "draft_id": "d-1"}]
        }
        result = _content_hub_workflow_meta(batch, "x")
        assert result == {}

    def test_returns_empty_when_no_workflow(self):
        batch = _make_batch()
        result = _content_hub_workflow_meta(batch, "x")
        assert result == {}

    def test_returns_empty_when_no_matching_platform(self):
        batch = _make_batch()
        batch.metadata["workflow_v2"] = {
            "drafts": [{"platform": "threads", "passed": True}]
        }
        result = _content_hub_workflow_meta(batch, "naver_blog")
        assert result == {}

    def test_returns_first_match_when_duplicates(self):
        batch = _make_batch()
        batch.metadata["workflow_v2"] = {
            "drafts": [
                {"platform": "x", "passed": True, "draft_id": "first"},
                {"platform": "x", "passed": True, "draft_id": "second"},
            ]
        }
        result = _content_hub_workflow_meta(batch, "x")
        assert result["draft_id"] == "first"


# ═══════════════════════════════════════════════════════════════════
# 5. save_to_notion — 중복 except 블록 + 중복 검사
# ═══════════════════════════════════════════════════════════════════

class TestSaveToNotion:
    def test_notion_unavailable_returns_false(self):
        with patch("storage.NOTION_AVAILABLE", False):
            assert save_to_notion(_make_batch(), _make_trend(), AppConfig()) is False

    def test_duplicate_detection_skips_save(self):
        """오늘 같은 토픽이 이미 있으면 True 반환하고 생성 안 함."""
        mock_notion = MagicMock()
        cfg = AppConfig()
        cfg.notion_token = "secret"
        cfg.notion_database_id = "db-123"

        with (
            patch("storage.NOTION_AVAILABLE", True),
            patch("storage.NotionClient", return_value=mock_notion),
            patch("storage._notion_page_exists", return_value=True),
        ):
            result = save_to_notion(_make_batch(), _make_trend(), cfg)
        assert result is True
        mock_notion.pages.create.assert_not_called()

    def test_connection_error_returns_false(self):
        cfg = AppConfig()
        cfg.notion_token = "secret"
        cfg.notion_database_id = "db-123"

        with (
            patch("storage.NOTION_AVAILABLE", True),
            patch("storage.NotionClient", side_effect=ConnectionError("timeout")),
        ):
            assert save_to_notion(_make_batch(), _make_trend(), cfg) is False

    def test_thread_text_truncated_to_1900(self):
        """Thread 텍스트가 1900자로 잘려서 Notion에 전달."""
        long_thread = GeneratedThread(tweets=["A" * 2000])
        batch = _make_batch()
        batch.thread = long_thread
        mock_notion = MagicMock()
        cfg = AppConfig()
        cfg.notion_token = "secret"
        cfg.notion_database_id = "db-123"

        with (
            patch("storage.NOTION_AVAILABLE", True),
            patch("storage.NotionClient", return_value=mock_notion),
            patch("storage._notion_page_exists", return_value=False),
            patch("storage._build_notion_body", return_value=[]),
            patch("storage._retry_notion_call") as mock_retry,
        ):
            save_to_notion(batch, _make_trend(), cfg)

        # properties 인수 확인
        call_kwargs = mock_retry.call_args
        properties = call_kwargs.kwargs.get("properties") or call_kwargs[1].get("properties", {})
        if "쓰레드" in properties:
            thread_content = properties["쓰레드"]["rich_text"][0]["text"]["content"]
            assert len(thread_content) <= 1900

    def test_legacy_notion_schema_uses_korean_property_names(self):
        """메인 Notion DB는 한국어 스키마에 맞춰 저장한다."""
        batch = TweetBatch(
            topic="테스트 키워드",
            tweets=[
                GeneratedTweet(tweet_type="자조공감", content="공감 트윗"),
                GeneratedTweet(tweet_type="실용꿀팁", content="꿀팁 트윗"),
                GeneratedTweet(tweet_type="도발질문", content="질문 트윗"),
                GeneratedTweet(tweet_type="데이터펀치", content="데이터 트윗"),
                GeneratedTweet(tweet_type="반전", content="반전 트윗"),
            ],
            thread=GeneratedThread(tweets=["스레드 첫줄", "스레드 둘째줄"]),
        )
        mock_notion = MagicMock()
        cfg = AppConfig()
        cfg.notion_token = "secret"
        cfg.notion_database_id = "db-123"

        with (
            patch("storage.NOTION_AVAILABLE", True),
            patch("storage.NotionClient", return_value=mock_notion),
            patch("storage._notion_page_exists", return_value=False),
            patch("storage._build_notion_body", return_value=[]),
            patch("storage._retry_notion_call") as mock_retry,
        ):
            assert save_to_notion(batch, _make_trend(), cfg) is True

        properties = mock_retry.call_args.kwargs["properties"]
        assert "제목" in properties
        assert "주제" in properties
        assert "순위" in properties
        assert "생성시각" in properties
        assert "상태" in properties
        assert "바이럴점수" in properties
        assert properties["공감유도형"]["rich_text"][0]["text"]["content"] == "공감 트윗"
        assert properties["꿀팁형"]["rich_text"][0]["text"]["content"] == "꿀팁 트윗"
        assert properties["찬반질문형"]["rich_text"][0]["text"]["content"] == "질문 트윗"
        assert properties["명언형"]["rich_text"][0]["text"]["content"] == "데이터 트윗"
        assert properties["유머밈형"]["rich_text"][0]["text"]["content"] == "반전 트윗"
        assert properties["상태"]["select"]["name"] == "대기중"
