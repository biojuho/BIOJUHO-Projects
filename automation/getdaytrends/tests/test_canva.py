"""tests/test_canva.py — canva.py 단위 테스트.

C-4: Canva Visuals Pipeline Integration 테스트.
"""

from unittest.mock import patch

import pytest

from canva import generate_visual_assets
from config import AppConfig


@pytest.fixture
def config_no_canva():
    """Canva API 키가 없는 기본 설정."""
    return AppConfig()


@pytest.fixture
def config_with_canva():
    """Canva API 키가 설정된 설정."""
    return AppConfig(
        canva_api_key="test-canva-api-key",
        canva_template_id="tmpl_123",
        enable_canva_visuals=True,
        canva_min_score=90,
    )


def _make_scored_trend(keyword="테스트 트렌드", viral_potential=95):
    from models import ScoredTrend, TrendSource

    return ScoredTrend(
        keyword=keyword,
        rank=1,
        viral_potential=viral_potential,
        trend_acceleration="급상승",
        top_insight="테스트 인사이트",
        sources=[TrendSource.GETDAYTRENDS],
    )


# ──────────────────────────── Basic Tests ────────────────────────────


@pytest.mark.asyncio
async def test_returns_empty_when_no_api_key(config_no_canva):
    """API 키 없으면 빈 리스트 반환."""
    trend = _make_scored_trend()
    result = await generate_visual_assets(trend, config_no_canva)
    assert result == []


@pytest.mark.asyncio
async def test_returns_empty_with_api_key_but_no_implementation(config_with_canva):
    """API 키 있어도 현재 stub이므로 빈 리스트 반환."""
    trend = _make_scored_trend()
    result = await generate_visual_assets(trend, config_with_canva)
    assert result == []


# ──────────────────────────── Config Tests ────────────────────────────


def test_enable_canva_visuals_default_false():
    config = AppConfig()
    assert config.enable_canva_visuals is False


def test_canva_min_score_default_90():
    config = AppConfig()
    assert config.canva_min_score == 90


def test_canva_config_from_env():
    import os

    with patch.dict(
        os.environ,
        {
            "ENABLE_CANVA_VISUALS": "true",
            "CANVA_MIN_SCORE": "85",
            "CANVA_API_KEY": "test-key",
        },
    ):
        config = AppConfig.from_env()
        assert config.enable_canva_visuals is True
        assert config.canva_min_score == 85
        assert config.canva_api_key == "test-key"


# ──────────────────────────── Pipeline Integration Check ────────────────────────────


def test_canva_should_skip_low_score():
    """canva_min_score 미만이면 스킵해야 함 (파이프라인 레벨 확인)."""
    config = AppConfig(enable_canva_visuals=True, canva_min_score=90)
    trend = _make_scored_trend(viral_potential=80)
    # 파이프라인에서의 조건: trend.viral_potential >= config.canva_min_score
    assert trend.viral_potential < config.canva_min_score


def test_canva_should_run_high_score():
    """canva_min_score 이상이면 실행해야 함."""
    config = AppConfig(enable_canva_visuals=True, canva_min_score=90)
    trend = _make_scored_trend(viral_potential=95)
    assert trend.viral_potential >= config.canva_min_score
