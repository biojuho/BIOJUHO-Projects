"""shared.llm.context_condenser - Intelligent context compression for long pipelines.

Inspired by OpenHands' Context Condensation pattern but adapted for our
batch-oriented automations (DailyNews 6-category sequential processing,
GetDayTrends multi-cycle analysis).

Key Design Decisions:
- Uses LIGHTWEIGHT tier for summarization (Gemini Flash / local models)
- Preserves the most recent N messages verbatim (prevents information loss)
- Compresses older messages into a structured summary
- Tracks compression metrics for observability

Usage:
    from shared.llm.context_condenser import ContextCondenser

    condenser = ContextCondenser(client)
    compressed = condenser.condense(
        history=long_message_list,
        keep_recent=3,
        summary_max_tokens=500,
    )
    # Returns a shorter message list with older history summarized
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .models import LLMPolicy, TaskTier

if TYPE_CHECKING:
    from .client import LLMClient

log = logging.getLogger("shared.llm.context_condenser")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Minimum history length before condensation kicks in
_MIN_HISTORY_FOR_CONDENSATION = 6

# Default number of recent messages to preserve verbatim
_DEFAULT_KEEP_RECENT = 3

# Rough chars per token for estimation
_CHARS_PER_TOKEN = 3.5

# Summary prompt template
_SUMMARY_PROMPT = """아래는 AI 어시스턴트와의 이전 대화 히스토리입니다.
핵심 내용만 간결하게 요약해주세요.

요약 규칙:
1. 사용자의 원래 목표와 현재 진행 상황을 반드시 포함
2. 중요한 기술적 결정사항과 그 이유를 보존
3. 실패했거나 문제가 있었던 시도를 명시
4. 수정/생성된 주요 파일명을 보존
5. 불필요한 대화(인사, 감사 등)는 제거
6. 200단어 이내로 작성

<history>
{history_text}
</history>

위 히스토리의 핵심 요약:"""

# Pipeline context summary (optimized for sequential category processing)
_PIPELINE_SUMMARY_PROMPT = """아래는 자동화 파이프라인에서 이전 카테고리 처리 결과입니다.
다음 카테고리 처리에 필요한 핵심 컨텍스트만 추출해주세요.

보존 항목:
1. 전체 파이프라인 목표
2. 지금까지 처리 완료된 카테고리와 각 결과 요약 (1줄씩)
3. 발견된 패턴이나 이슈
4. 다음 카테고리에 영향을 줄 설정/상태 변경

<previous_results>
{results_text}
</previous_results>

파이프라인 컨텍스트 요약:"""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CondensationResult:
    """Result of a context condensation operation."""
    messages: list[dict]
    original_count: int
    condensed_count: int
    summary_text: str = ""
    tokens_saved_estimate: int = 0
    condensation_cost_usd: float = 0.0
    condensation_latency_ms: float = 0.0

    @property
    def compression_ratio(self) -> float:
        if self.original_count == 0:
            return 1.0
        return self.condensed_count / self.original_count


@dataclass
class PipelineContext:
    """Accumulated context for sequential pipeline processing."""
    goal: str = ""
    completed_categories: list[dict] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    state_changes: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core condenser
# ---------------------------------------------------------------------------

class ContextCondenser:
    """Intelligent context compression for reducing LLM token consumption.

    Two modes of operation:

    1. **Conversation Condensation**: For long chat histories, summarizes
       older messages while preserving recent ones verbatim.

    2. **Pipeline Condensation**: For sequential batch processing (e.g.,
       DailyNews 6-category pipeline), compresses previous category results
       into a structured summary for the next category.

    Uses LIGHTWEIGHT tier to minimize condensation cost.
    """

    def __init__(self, client: LLMClient) -> None:
        self._client = client
        self._metrics = {
            "total_condensations": 0,
            "total_tokens_saved": 0,
            "total_cost_usd": 0.0,
        }

    # -- Conversation condensation -----------------------------------------

    def condense(
        self,
        history: list[dict],
        *,
        keep_recent: int = _DEFAULT_KEEP_RECENT,
        summary_max_tokens: int = 500,
    ) -> CondensationResult:
        """Condense a conversation history synchronously.

        Args:
            history: List of message dicts [{"role": "...", "content": "..."}]
            keep_recent: Number of most recent messages to keep verbatim
            summary_max_tokens: Max tokens for the summary output

        Returns:
            CondensationResult with the compressed message list
        """
        original_count = len(history)

        # Skip if history is too short
        if original_count <= max(keep_recent, _MIN_HISTORY_FOR_CONDENSATION):
            return CondensationResult(
                messages=list(history),
                original_count=original_count,
                condensed_count=original_count,
            )

        t0 = time.perf_counter()

        # Split history
        old_messages = history[:-keep_recent]
        recent_messages = history[-keep_recent:]

        # Format old messages for summarization
        history_text = self._format_messages(old_messages)

        # Summarize using LIGHTWEIGHT tier
        try:
            resp = self._client.create(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[{"role": "user", "content": _SUMMARY_PROMPT.format(history_text=history_text)}],
                max_tokens=summary_max_tokens,
                system="You are a precise conversation summarizer. Output only Korean.",
                policy=LLMPolicy(
                    task_kind="summary",
                    output_language="ko",
                    enforce_korean_output=True,
                ),
            )
            summary_text = resp.text
            condensation_cost = resp.cost_usd
        except Exception as e:
            log.warning("Context condensation failed: %s. Returning truncated history.", e)
            # Fallback: just keep recent messages without summary
            return CondensationResult(
                messages=recent_messages,
                original_count=original_count,
                condensed_count=len(recent_messages),
            )

        # Build condensed message list
        condensed = [
            {"role": "system", "content": f"[이전 대화 요약]\n{summary_text}"},
            *recent_messages,
        ]

        # Estimate tokens saved
        old_chars = sum(len(m.get("content", "")) for m in old_messages)
        summary_chars = len(summary_text)
        tokens_saved = int((old_chars - summary_chars) / _CHARS_PER_TOKEN)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Update metrics
        self._metrics["total_condensations"] += 1
        self._metrics["total_tokens_saved"] += max(tokens_saved, 0)
        self._metrics["total_cost_usd"] += condensation_cost

        log.info(
            "Condensed %d→%d messages (saved ~%d tokens, cost=$%.4f, %.0fms)",
            original_count, len(condensed), tokens_saved, condensation_cost, elapsed_ms,
        )

        return CondensationResult(
            messages=condensed,
            original_count=original_count,
            condensed_count=len(condensed),
            summary_text=summary_text,
            tokens_saved_estimate=max(tokens_saved, 0),
            condensation_cost_usd=condensation_cost,
            condensation_latency_ms=elapsed_ms,
        )

    async def acondense(
        self,
        history: list[dict],
        *,
        keep_recent: int = _DEFAULT_KEEP_RECENT,
        summary_max_tokens: int = 500,
    ) -> CondensationResult:
        """Async version of condense()."""
        original_count = len(history)

        if original_count <= max(keep_recent, _MIN_HISTORY_FOR_CONDENSATION):
            return CondensationResult(
                messages=list(history),
                original_count=original_count,
                condensed_count=original_count,
            )

        t0 = time.perf_counter()
        old_messages = history[:-keep_recent]
        recent_messages = history[-keep_recent:]
        history_text = self._format_messages(old_messages)

        try:
            resp = await self._client.acreate(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[{"role": "user", "content": _SUMMARY_PROMPT.format(history_text=history_text)}],
                max_tokens=summary_max_tokens,
                system="You are a precise conversation summarizer. Output only Korean.",
                policy=LLMPolicy(
                    task_kind="summary",
                    output_language="ko",
                    enforce_korean_output=True,
                ),
            )
            summary_text = resp.text
            condensation_cost = resp.cost_usd
        except Exception as e:
            log.warning("Async context condensation failed: %s", e)
            return CondensationResult(
                messages=recent_messages,
                original_count=original_count,
                condensed_count=len(recent_messages),
            )

        condensed = [
            {"role": "system", "content": f"[이전 대화 요약]\n{summary_text}"},
            *recent_messages,
        ]

        old_chars = sum(len(m.get("content", "")) for m in old_messages)
        summary_chars = len(summary_text)
        tokens_saved = int((old_chars - summary_chars) / _CHARS_PER_TOKEN)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        self._metrics["total_condensations"] += 1
        self._metrics["total_tokens_saved"] += max(tokens_saved, 0)
        self._metrics["total_cost_usd"] += condensation_cost

        return CondensationResult(
            messages=condensed,
            original_count=original_count,
            condensed_count=len(condensed),
            summary_text=summary_text,
            tokens_saved_estimate=max(tokens_saved, 0),
            condensation_cost_usd=condensation_cost,
            condensation_latency_ms=elapsed_ms,
        )

    # -- Pipeline condensation ---------------------------------------------

    def condense_pipeline_context(
        self,
        previous_results: list[dict],
        *,
        pipeline_goal: str = "",
        summary_max_tokens: int = 400,
    ) -> str:
        """Condense previous pipeline stage results for the next stage.

        Designed for sequential processing (e.g., DailyNews 6-category pipeline)
        where each category's result should inform the next without
        accumulating unbounded context.

        Args:
            previous_results: List of dicts with {"category": str, "result": str}
            pipeline_goal: High-level pipeline objective
            summary_max_tokens: Max tokens for the summary

        Returns:
            Condensed context string to inject into the next stage's prompt
        """
        if not previous_results:
            return ""

        results_text = "\n\n".join(
            f"### {r.get('category', f'Stage {i+1}')}\n{r.get('result', '')[:500]}"
            for i, r in enumerate(previous_results)
        )

        if pipeline_goal:
            results_text = f"파이프라인 목표: {pipeline_goal}\n\n{results_text}"

        try:
            resp = self._client.create(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[{
                    "role": "user",
                    "content": _PIPELINE_SUMMARY_PROMPT.format(results_text=results_text),
                }],
                max_tokens=summary_max_tokens,
                system="You are a pipeline context optimizer. Be concise.",
                policy=LLMPolicy(
                    task_kind="summary",
                    output_language="ko",
                    enforce_korean_output=True,
                ),
            )
            self._metrics["total_condensations"] += 1
            self._metrics["total_cost_usd"] += resp.cost_usd
            return resp.text
        except Exception as e:
            log.warning("Pipeline condensation failed: %s", e)
            # Fallback: return truncated results
            return "\n".join(
                f"- {r.get('category', '?')}: {r.get('result', '')[:100]}"
                for r in previous_results
            )

    # -- Helpers -----------------------------------------------------------

    @staticmethod
    def _format_messages(messages: list[dict]) -> str:
        """Format messages into a readable text block."""
        lines = []
        for m in messages:
            role = m.get("role", "unknown").upper()
            content = m.get("content", "")
            # Truncate very long messages
            if len(content) > 1000:
                content = content[:1000] + "... [truncated]"
            lines.append(f"[{role}]: {content}")
        return "\n\n".join(lines)

    @property
    def metrics(self) -> dict:
        """Return condensation metrics."""
        return dict(self._metrics)
