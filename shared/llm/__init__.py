"""shared.llm - Unified LLM client with tier-based routing.

Usage:
    from shared.llm import get_client, TaskTier

    client = get_client()
    resp = client.create(tier=TaskTier.HEAVY, messages=[...], system="...")
    resp = await client.acreate(tier=TaskTier.LIGHTWEIGHT, messages=[...])
"""

from .client import LLMClient
from .models import LLMResponse, TaskTier

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


__all__ = [
    "LLMClient",
    "LLMResponse",
    "TaskTier",
    "get_client",
    "reset_client",
]
