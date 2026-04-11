from unittest.mock import MagicMock, patch

import pytest

from config import AppConfig

# ══════════════════════════════════════════════════════
#  _should_skip_qa unit tests
# ══════════════════════════════════════════════════════


def _make_trend(viral_potential: int = 50, category: str = "IT"):
    """테스트용 간단한 트렌드 객체 생성."""
    trend = MagicMock()
    trend.viral_potential = viral_potential
    trend.category = category
    return trend


class TestShouldSkipQA:
    """A-2: QA Audit 조건부 스킵 로직 검증."""

    def _skip(self, trend, is_cached: bool, config: AppConfig) -> bool:
        from getdaytrends.core.pipeline_steps import _should_skip_qa

        return _should_skip_qa(trend, is_cached, config)

    def test_cached_content_skips_qa(self):
        """캐시 재사용 콘텐츠는 QA 스킵."""
        cfg = AppConfig()
        cfg.qa_skip_cached = True
        trend = _make_trend(viral_potential=50)
        assert self._skip(trend, is_cached=True, config=cfg) is True

    def test_cached_content_no_skip_when_disabled(self):
        """qa_skip_cached=False면 캐시여도 QA 실행."""
        cfg = AppConfig()
        cfg.qa_skip_cached = False
        trend = _make_trend(viral_potential=50)
        assert self._skip(trend, is_cached=True, config=cfg) is False

    def test_high_viral_score_skips_qa(self):
        """고바이럴 트렌드(≥85)는 QA 스킵."""
        cfg = AppConfig()
        trend = _make_trend(viral_potential=90)
        assert self._skip(trend, is_cached=False, config=cfg) is True

    def test_low_risk_category_skips_qa(self):
        """저위험 카테고리(날씨/음식/스포츠)는 QA 스킵."""
        cfg = AppConfig()
        for cat in ["날씨", "음식", "스포츠"]:
            trend = _make_trend(viral_potential=50, category=cat)
            assert self._skip(trend, is_cached=False, config=cfg) is True, f"Should skip for category '{cat}'"

    def test_normal_trend_runs_qa(self):
        """일반 트렌드(낮은 점수, 일반 카테고리, 미캐시)는 QA 실행."""
        cfg = AppConfig()
        trend = _make_trend(viral_potential=50, category="IT")
        assert self._skip(trend, is_cached=False, config=cfg) is False

    def test_quality_feedback_disabled_skips_all(self):
        """enable_quality_feedback=False면 모든 QA 전체 스킵."""
        cfg = AppConfig()
        cfg.enable_quality_feedback = False
        trend = _make_trend(viral_potential=50)
        assert self._skip(trend, is_cached=False, config=cfg) is True


# ══════════════════════════════════════════════════════
#  _is_accelerating unit tests
# ══════════════════════════════════════════════════════


class TestIsAccelerating:
    """급상승 판별 로직 검증."""

    def _check(self, val: str) -> bool:
        from getdaytrends.core.pipeline_steps import _is_accelerating

        return _is_accelerating(val)

    def test_korean_keyword(self):
        assert self._check("급상승") is True

    def test_percentage_above_threshold(self):
        assert self._check("+5%") is True
        assert self._check("+30%") is True

    def test_percentage_below_threshold(self):
        assert self._check("+1%") is False
        assert self._check("+2.5%") is False

    def test_exactly_threshold(self):
        assert self._check("+3%") is True

    def test_no_acceleration(self):
        assert self._check("정상") is False
        assert self._check("") is False


# ══════════════════════════════════════════════════════
#  _batch_from_cache unit tests
# ══════════════════════════════════════════════════════


class TestBatchFromCache:
    """캐시 → TweetBatch 재구성 검증."""

    def test_basic_reconstruction(self):
        from getdaytrends.core.pipeline_steps import _batch_from_cache

        rows = [
            {"tweet_type": "분석형", "content": "테스트 트윗", "content_type": "short"},
            {"tweet_type": "공감형", "content": "테스트 장문", "content_type": "long"},
            {"tweet_type": "재미형", "content": "테스트 Threads", "content_type": "threads"},
        ]
        batch = _batch_from_cache("테스트", rows)
        assert len(batch.tweets) == 1
        assert len(batch.long_posts) == 1
        assert len(batch.threads_posts) == 1
        assert batch.topic == "테스트"

    def test_deduplication(self):
        from getdaytrends.core.pipeline_steps import _batch_from_cache

        rows = [
            {"tweet_type": "분석형", "content": "첫번째", "content_type": "short"},
            {"tweet_type": "분석형", "content": "중복", "content_type": "short"},
        ]
        batch = _batch_from_cache("중복테스트", rows)
        assert len(batch.tweets) == 1
        assert batch.tweets[0].content == "첫번째"


# ══════════════════════════════════════════════════════
#  Existing test
# ══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_step_generate_handles_empty_trend_list():
    from getdaytrends.core.pipeline_steps import _step_generate

    cfg = AppConfig()

    with patch("getdaytrends.core.pipeline_steps.get_client", return_value=MagicMock()):
        result = await _step_generate([], cfg, conn=MagicMock())

    assert result == []
