"""shared.llm.models - Data types for the unified LLM client."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Literal


class TaskTier(Enum):
    """Task complexity tiers for cost-optimized routing.

    LIGHTWEIGHT - scoring, filtering, classification (DeepSeek first)
    MEDIUM      - summarization, analysis (Gemini Flash first)
    HEAVY       - content generation, research (Claude Sonnet first)
    """

    LIGHTWEIGHT = "lightweight"
    MEDIUM = "medium"
    HEAVY = "heavy"


TaskKind = Literal[
    "classification",
    "keyword_extraction",
    "search_query_generation",
    "json_extraction",
    "summary",
    "analysis",
    "literature_review",
    "grant_writing",
    "youtube_longform",
    "generic",
]


ResponseMode = Literal["text", "json"]


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class LLMPolicy:
    """Runtime language and routing policy for an LLM request."""

    locale: str = "ko-KR"
    input_language: str = "auto"
    output_language: str = "ko"
    task_kind: TaskKind = "generic"
    enforce_korean_output: bool = True
    allow_source_quotes: bool = False
    preserve_terms: list[str] = field(default_factory=list)
    response_mode: ResponseMode = "text"
    # opt-in 네이티브 구조화 출력 스키마(JSON Schema dict). 제공 시 provider별로
    # Anthropic output_config.format / OpenAI·Grok response_format json_schema(strict) /
    # Gemini response_json_schema 로 변환. None(기본)이면 기존 loose-JSON 경로 유지.
    json_schema: dict | None = None


@dataclass
class BridgeMeta:
    """Metadata describing how the language bridge handled a response."""

    bridge_applied: bool = False
    detected_input_language: str = "unknown"
    detected_output_language: str = "unknown"
    quality_flags: list[str] = field(default_factory=list)
    fallback_reason: str = ""


@dataclass
class LLMResponse:
    """Unified response from any LLM backend."""

    text: str
    model: str
    backend: str
    tier: TaskTier = TaskTier.MEDIUM
    policy: LLMPolicy = field(default_factory=LLMPolicy)
    bridge_meta: BridgeMeta = field(default_factory=BridgeMeta)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


@dataclass
class CostRecord:
    """Per-call cost tracking record."""

    timestamp: datetime = field(default_factory=_utc_now)
    backend: str = ""
    model: str = ""
    tier: TaskTier = TaskTier.MEDIUM
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    success: bool = True
    error: str = ""
