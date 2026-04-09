from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_CIE_DIR = Path(__file__).resolve().parents[1]
if str(_CIE_DIR) not in sys.path:
    sys.path.insert(0, str(_CIE_DIR))

_PROJECT_ROOT = _CIE_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import main as cie_main
from config import CIEConfig
from storage.models import ContentBatch, MergedTrendReport, PlatformTrend, PlatformTrendReport


def _report(platform: str, keyword: str = "AI") -> PlatformTrendReport:
    return PlatformTrendReport(
        platform=platform,
        trends=[PlatformTrend(keyword=keyword, volume=100)],
        key_insights=[f"{platform} insight"],
    )


@pytest.mark.asyncio
async def test_step_collect_trends_marks_degraded_and_blocks_publish():
    config = CIEConfig()
    config.platforms = ["x", "threads", "naver"]

    with patch(
        "collectors.x_collector.collect_x_trends",
        new=AsyncMock(return_value=_report("x")),
    ), patch(
        "collectors.threads_collector.collect_threads_trends",
        new=AsyncMock(side_effect=RuntimeError("threads unavailable")),
    ), patch(
        "collectors.naver_collector.collect_naver_trends",
        new=AsyncMock(return_value=_report("naver")),
    ):
        merged = await cie_main.step_collect_trends(config)

    assert len(merged.platform_reports) == 2
    assert merged.degraded is True
    assert merged.publish_blocked is True
    assert merged.quorum_required == 2
    assert merged.failed_platforms == ["threads"]


@pytest.mark.asyncio
async def test_run_pipeline_stops_when_trend_quorum_is_missed():
    config = CIEConfig()
    config.platforms = ["x", "threads", "naver"]
    trend_report = MergedTrendReport(
        platform_reports=[_report("x")],
        degraded=True,
        failed_platforms=["threads", "naver"],
        publish_blocked=True,
        quorum_required=2,
    )

    with patch.object(cie_main, "step_collect_trends", new=AsyncMock(return_value=trend_report)), patch.object(
        cie_main,
        "step_save",
        new=AsyncMock(),
    ) as mock_save, patch.object(
        cie_main,
        "step_check_regulations",
        new=AsyncMock(),
    ) as mock_regulations, patch.object(
        cie_main,
        "step_generate_content",
        new=AsyncMock(),
    ) as mock_generate, patch.object(
        cie_main,
        "_step_predict_engagement",
        new=AsyncMock(),
    ) as mock_predict, patch.object(
        cie_main,
        "step_publish",
        new=AsyncMock(),
    ) as mock_publish:
        await cie_main.run_pipeline(config, mode="full", publish=True)

    mock_save.assert_awaited_once_with(config, trend_report=trend_report)
    mock_regulations.assert_not_awaited()
    mock_generate.assert_not_awaited()
    mock_predict.assert_not_awaited()
    mock_publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_pipeline_skips_publish_for_degraded_but_quorum_met_run():
    config = CIEConfig()
    config.platforms = ["x", "threads", "naver"]
    trend_report = MergedTrendReport(
        platform_reports=[_report("x"), _report("threads")],
        degraded=True,
        failed_platforms=["naver"],
        publish_blocked=True,
        quorum_required=2,
    )
    batch = ContentBatch(contents=[])

    with patch.object(cie_main, "step_collect_trends", new=AsyncMock(return_value=trend_report)), patch.object(
        cie_main,
        "step_check_regulations",
        new=AsyncMock(return_value=([], MagicMock())),
    ) as mock_regulations, patch.object(
        cie_main,
        "step_generate_content",
        new=AsyncMock(return_value=batch),
    ) as mock_generate, patch.object(
        cie_main,
        "_step_predict_engagement",
        new=AsyncMock(),
    ) as mock_predict, patch.object(
        cie_main,
        "step_save",
        new=AsyncMock(),
    ) as mock_save, patch.object(
        cie_main,
        "step_publish",
        new=AsyncMock(),
    ) as mock_publish:
        await cie_main.run_pipeline(config, mode="full", publish=True)

    mock_regulations.assert_awaited_once()
    mock_generate.assert_awaited_once()
    mock_predict.assert_awaited_once()
    mock_save.assert_awaited_once_with(config, trend_report, [], batch)
    mock_publish.assert_not_awaited()
