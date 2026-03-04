"""
DEPRECATED: getdaytrends/llm_client.py
이 모듈은 shared.llm으로 대체되었습니다.
하위 호환성을 위한 re-export 래퍼입니다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.llm import LLMClient, LLMResponse, TaskTier, get_client, reset_client  # noqa: F401

__all__ = ["LLMClient", "LLMResponse", "TaskTier", "get_client", "reset_client"]
