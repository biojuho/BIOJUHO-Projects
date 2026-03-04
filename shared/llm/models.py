"""shared.llm.models - Data types for the unified LLM client."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class TaskTier(Enum):
    """Task complexity tiers for cost-optimized routing.

    LIGHTWEIGHT - scoring, filtering, classification (DeepSeek first)
    MEDIUM      - summarization, analysis (Gemini Flash first)
    HEAVY       - content generation, research (Claude Sonnet first)
    """

    LIGHTWEIGHT = "lightweight"
    MEDIUM = "medium"
    HEAVY = "heavy"


@dataclass
class LLMResponse:
    """Unified response from any LLM backend."""

    text: str
    model: str
    backend: str
    tier: TaskTier = TaskTier.MEDIUM
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


@dataclass
class CostRecord:
    """Per-call cost tracking record."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    backend: str = ""
    model: str = ""
    tier: TaskTier = TaskTier.MEDIUM
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    success: bool = True
    error: str = ""
