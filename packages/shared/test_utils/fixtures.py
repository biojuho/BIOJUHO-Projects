"""Shared test fixtures for DailyNews and getdaytrends."""

from __future__ import annotations

from pathlib import Path
from typing import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

class SystemFixtureFactory:
    """통합 모의 테스트(System Mocks) 환경을 구축하는 팩토리 클래스입니다.
    깨지기 쉬운 다중 monkeypatch 사용을 줄이고 일관된 임시 상태 구성을 지원합니다.
    """

    @staticmethod
    def construct_isolated_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """가상의 작업 디렉터리를 구축하여 각종 I/O를 임시 폴더로 강제 우회합니다."""
        data_dir = tmp_path / "data"
        log_dir = tmp_path / "logs"
        config_dir = tmp_path / "config"
        
        for d in (data_dir, log_dir, config_dir):
            d.mkdir(parents=True, exist_ok=True)
            
        # 시스템 환경변수 레벨에서 우회
        monkeypatch.setenv("DATA_DIR", str(data_dir))
        monkeypatch.setenv("LOG_DIR", str(log_dir))
        monkeypatch.setenv("CONFIG_DIR", str(config_dir))
        
        return {
            "data_dir": data_dir,
            "log_dir": log_dir,
            "config_dir": config_dir,
        }

    @staticmethod
    def patch_runtime_paths(monkeypatch: pytest.MonkeyPatch, runtime_module, tmp_path: Path):
        """런타임 관련 모듈의 경로 상수를 임시 디렉터리로 런타임 패치합니다."""
        env = SystemFixtureFactory.construct_isolated_workspace(monkeypatch, tmp_path)
        
        # 안전한 attr 변경을 위해 monkeypatch.setattr 활용 (모듈 존재 여부에 따라 유연하게 대응)
        if hasattr(runtime_module, "DATA_DIR"):
            monkeypatch.setattr(runtime_module, "DATA_DIR", env["data_dir"])
        if hasattr(runtime_module, "LOG_DIR"):
            monkeypatch.setattr(runtime_module, "LOG_DIR", env["log_dir"])
        if hasattr(runtime_module, "PIPELINE_STATE_DB"):
            monkeypatch.setattr(runtime_module, "PIPELINE_STATE_DB", env["data_dir"] / "pipeline_state.db")
        if hasattr(runtime_module, "SCHEDULER_LOG_PATH"):
            monkeypatch.setattr(runtime_module, "SCHEDULER_LOG_PATH", env["log_dir"] / "scheduler.log")
            
        return env



def make_tmp_state_store(tmp_path: Path):
    """Create a temporary PipelineStateStore for testing."""
    from antigravity_mcp.state.store import PipelineStateStore

    return PipelineStateStore(path=tmp_path / "test.db")


def make_mock_llm_client(response_text: str = '{"summary": ["test"]}'):
    """Create a mock LLM client with a predetermined response."""
    mock = MagicMock()
    mock_response = MagicMock()
    mock_response.text = response_text
    mock.create.return_value = mock_response
    mock.acreate = AsyncMock(return_value=mock_response)
    return mock


def make_sample_articles(count: int = 3, category: str = "Tech") -> list[dict]:
    """Create sample article dicts for testing."""
    return [
        {
            "title": f"Test Article {i}",
            "description": f"Description for test article {i} with enough text for testing.",
            "link": f"https://example.com/article-{i}",
            "source_name": f"Source{i}",
        }
        for i in range(count)
    ]
