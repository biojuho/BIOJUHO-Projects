"""shared.llm - Unified LLM client with tier-based routing.

Usage:
    from shared.llm import get_client, TaskTier

    client = get_client()
    resp = client.create(tier=TaskTier.HEAVY, messages=[...], system="...")
    resp = await client.acreate(tier=TaskTier.LIGHTWEIGHT, messages=[...])
"""

from .client import LLMClient
from .errors import (
    AuthError,
    ContentFilterError,
    ContextLengthError,
    LLMError,
    ModelNotFoundError,
    NetworkError,
    QuotaExhaustedError,
    RateLimitError,
    ServerError,
    classify_error,
)
from .marl import MARLConfig, MARLPipeline, MARLResult
from .model_patches import apply_model_patch
from .models import BridgeMeta, LLMPolicy, LLMResponse, TaskTier
from .stats import CostTracker
from .tool_schema import ToolDefinition, ToolRegistry, ToolResult
from .reasoning import SmartRouter, QueryComplexity

_client: LLMClient | None = None


def get_client(**key_overrides: str) -> LLMClient:
    """Get or create the singleton LLMClient instance."""
    global _client
    if _client is None:
        _client = LLMClient(**key_overrides)
    return _client


def reset_client() -> None:
    """Reset the singleton (for testing or key rotation)."""
    global _client
    if _client is not None:
        _client.reset()
    _client = None


def export_usage_csv(days: int = 30):
    """Export LLM usage to CSV. Returns path or None."""
    if _client is not None:
        return _client._tracker.export_csv(days)
    return None


def get_daily_stats(days: int = 30) -> list[dict]:
    """Get daily aggregated stats from persistent storage."""
    if _client is not None:
        return _client._tracker.get_daily_stats(days)
    return []


__all__ = [
    # Core
    "LLMClient",
    "BridgeMeta",
    "CostTracker",
    "LLMPolicy",
    "LLMResponse",
    "TaskTier",
    "get_client",
    "reset_client",
    "export_usage_csv",
    "get_daily_stats",
    # Phase 1: Error classification
    "LLMError",
    "AuthError",
    "ContentFilterError",
    "ContextLengthError",
    "ModelNotFoundError",
    "NetworkError",
    "QuotaExhaustedError",
    "RateLimitError",
    "ServerError",
    "classify_error",
    # Phase 2: Model patches
    "apply_model_patch",
    # Phase 3: MARL pipeline
    "MARLConfig",
    "MARLPipeline",
    "MARLResult",
    # Phase 4: Tool schema
    "ToolDefinition",
    "ToolRegistry",
    "ToolResult",
    # Phase 5: Reasoning Engine
    "SmartRouter",
    "QueryComplexity",
]

