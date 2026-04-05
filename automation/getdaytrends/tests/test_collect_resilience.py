"""_step_collect 외부 API 장애 방어 테스트."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from config import AppConfig
from models import RunResult


def _make_run() -> RunResult:
    return RunResult(run_id="test-run-001")


class TestStepCollectResilience:
    """GAP #1: collect_trends / collect_contexts 예외 시 파이프라인 크래시 방지."""

    def test_collect_trends_exception_returns_empty(self):
        """collect_trends가 예외를 던지면 빈 리스트/딕트를 반환하고 에러를 기록한다."""
        from core.pipeline import _step_collect

        run = _make_run()
        cfg = AppConfig()

        with patch("core.pipeline.collect_trends", side_effect=ConnectionError("API timeout")):
            raw_trends, contexts = _step_collect(cfg, conn=MagicMock(), run=run)

        assert raw_trends == []
        assert contexts == {}
        assert any("collect_trends 예외" in e for e in run.errors)

    def test_collect_trends_exception_preserves_run_state(self):
        """예외 후에도 run.trends_collected가 초기값(0)을 유지한다."""
        from core.pipeline import _step_collect

        run = _make_run()
        cfg = AppConfig()

        with patch("core.pipeline.collect_trends", side_effect=RuntimeError("unexpected")):
            _step_collect(cfg, conn=MagicMock(), run=run)

        assert run.trends_collected == 0

    def test_collect_contexts_exception_keeps_raw_trends(self):
        """collect_contexts가 실패해도 이미 수집된 raw_trends는 보존된다."""
        from core.pipeline import _step_collect

        run = _make_run()
        cfg = AppConfig()

        fake_trend = MagicMock()
        fake_trend.name = "테스트 트렌드"
        fake_ctx = MagicMock()
        fake_ctx.to_combined_text.return_value = "x" * 50  # < _MIN_CTX_LEN(100) → deep 수집 유발

        with (
            patch("core.pipeline.collect_trends", return_value=([fake_trend], {fake_trend.name: fake_ctx})),
            patch("core.pipeline.collect_contexts", side_effect=TimeoutError("Twitter API timeout")),
        ):
            raw_trends, contexts = _step_collect(cfg, conn=MagicMock(), run=run)

        assert len(raw_trends) == 1
        assert fake_trend.name in contexts
        assert run.trends_collected == 1

    def test_collect_normal_path_succeeds(self):
        """정상 경로: 예외 없이 수집 완료."""
        from core.pipeline import _step_collect

        run = _make_run()
        cfg = AppConfig()

        fake_trend = MagicMock()
        fake_trend.name = "정상 트렌드"
        fake_ctx = MagicMock()
        fake_ctx.to_combined_text.return_value = "x" * 200  # 충분한 컨텍스트

        with patch("core.pipeline.collect_trends", return_value=([fake_trend], {fake_trend.name: fake_ctx})):
            raw_trends, contexts = _step_collect(cfg, conn=MagicMock(), run=run)

        assert len(raw_trends) == 1
        assert run.trends_collected == 1
