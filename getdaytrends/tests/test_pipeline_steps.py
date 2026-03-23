import pytest
from unittest.mock import MagicMock, patch

from config import AppConfig


@pytest.mark.asyncio
async def test_step_generate_handles_empty_trend_list():
    from core.pipeline_steps import _step_generate

    cfg = AppConfig()

    with patch("core.pipeline_steps.get_client", return_value=MagicMock()):
        result = await _step_generate([], cfg, conn=MagicMock())

    assert result == []
