"""
DEPRECATED: getdaytrends/llm_client.py
이 모듈은 shared.llm으로 대체되었습니다.
하위 호환성을 위한 re-export 래퍼입니다.
"""

from shared.llm import LLMClient, LLMResponse, TaskTier, get_client, reset_client

__all__ = ["LLMClient", "LLMResponse", "TaskTier", "get_client", "reset_client"]
