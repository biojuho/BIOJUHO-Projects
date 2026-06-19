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
import re
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .models import LLMPolicy, TaskTier

if TYPE_CHECKING:
    from .client import LLMClient

LOGGER_NAME = "shared.llm.context_condenser"
log = logging.getLogger(LOGGER_NAME)

Message = dict[str, Any]
Metrics = dict[str, int | float]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Minimum history length before condensation kicks in
_MIN_HISTORY_FOR_CONDENSATION = 6

# Default number of recent messages to preserve verbatim
_DEFAULT_KEEP_RECENT = 3
_DEFAULT_SUMMARY_MAX_TOKENS = 500
_DEFAULT_PIPELINE_SUMMARY_MAX_TOKENS = 400

# Rough chars per token for estimation
_CHARS_PER_TOKEN = 3.5
_MILLISECONDS_PER_SECOND = 1000
_MESSAGE_ROLE_KEY = "role"
_MESSAGE_CONTENT_KEY = "content"
_USER_ROLE = "user"
_PIPELINE_CATEGORY_KEY = "category"
_PIPELINE_RESULT_KEY = "result"
_PIPELINE_STAGE_PREFIX = "Stage"
_DEFAULT_MESSAGE_ROLE = "unknown"
_DEFAULT_MESSAGE_CONTENT = ""
_MESSAGE_TRUNCATE_CHARS = 1000
_MESSAGE_TRUNCATION_SUFFIX = "... [truncated]"
_PIPELINE_RESULT_PREVIEW_CHARS = 500
_PIPELINE_FALLBACK_RESULT_CHARS = 100
_UNKNOWN_PIPELINE_CATEGORY = "?"
_METRIC_TOTAL_CONDENSATIONS = "total_condensations"
_METRIC_TOTAL_TOKENS_SAVED = "total_tokens_saved"
_METRIC_TOTAL_COST_USD = "total_cost_usd"
_CONVERSATION_SUMMARY_SYSTEM = "You are a precise conversation summarizer. Output only Korean."
_PIPELINE_SUMMARY_SYSTEM = "You are a pipeline context optimizer. Be concise."
_LOG_CONTEXT_CONDENSATION_FAILED = "Context condensation failed: %s. Returning truncated history."
_LOG_ASYNC_CONTEXT_CONDENSATION_FAILED = "Async context condensation failed: %s"
_LOG_PIPELINE_CONDENSATION_FAILED = "Pipeline condensation failed: %s"

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

    messages: list[Message]
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
    completed_categories: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    state_changes: dict[str, Any] = field(default_factory=dict)


def _summary_policy() -> LLMPolicy:
    return LLMPolicy(
        task_kind="summary",
        output_language="ko",
        enforce_korean_output=True,
    )


def _estimate_tokens_saved(old_messages: list[Message], summary_text: str) -> int:
    old_chars = sum(len(m.get(_MESSAGE_CONTENT_KEY, _DEFAULT_MESSAGE_CONTENT)) for m in old_messages)
    summary_chars = len(summary_text)
    return int((old_chars - summary_chars) / _CHARS_PER_TOKEN)


def _non_negative_tokens_saved(tokens_saved: int) -> int:
    return max(tokens_saved, 0)


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * _MILLISECONDS_PER_SECOND


def _user_message(content: str) -> Message:
    return {
        _MESSAGE_ROLE_KEY: _USER_ROLE,
        _MESSAGE_CONTENT_KEY: content,
    }


def _summary_prompt(history_text: str) -> str:
    return _SUMMARY_PROMPT.format(history_text=history_text)


def _pipeline_summary_prompt(results_text: str) -> str:
    return _PIPELINE_SUMMARY_PROMPT.format(results_text=results_text)


def _split_history(history: list[Message], keep_recent: int) -> tuple[list[Message], list[Message]]:
    return history[:-keep_recent], history[-keep_recent:]


def _recent_only_result(recent_messages: list[Message], original_count: int) -> CondensationResult:
    return CondensationResult(
        messages=recent_messages,
        original_count=original_count,
        condensed_count=len(recent_messages),
    )


def _unchanged_result(history: list[Message], original_count: int) -> CondensationResult:
    return CondensationResult(
        messages=list(history),
        original_count=original_count,
        condensed_count=original_count,
    )


def _condensed_result(
    *,
    messages: list[Message],
    original_count: int,
    summary_text: str,
    tokens_saved: int,
    condensation_cost: float,
    elapsed_ms: float,
) -> CondensationResult:
    return CondensationResult(
        messages=messages,
        original_count=original_count,
        condensed_count=len(messages),
        summary_text=summary_text,
        tokens_saved_estimate=_non_negative_tokens_saved(tokens_saved),
        condensation_cost_usd=condensation_cost,
        condensation_latency_ms=elapsed_ms,
    )


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
    Thread-safe: metrics updates are guarded by a lock.
    """

    def __init__(self, client: LLMClient) -> None:
        self._client = client
        self._lock = threading.Lock()
        self._metrics: Metrics = {
            _METRIC_TOTAL_CONDENSATIONS: 0,
            _METRIC_TOTAL_TOKENS_SAVED: 0,
            _METRIC_TOTAL_COST_USD: 0.0,
        }

    @staticmethod
    def _sanitize_for_prompt(text: str) -> str:
        """Escape XML-like tags in user content to prevent prompt injection."""
        return re.sub(r"<(/?)(\w+)", r"&lt;\1\2", text)

    @staticmethod
    def _should_skip_condensation(original_count: int, keep_recent: int) -> bool:
        return original_count <= max(keep_recent, _MIN_HISTORY_FOR_CONDENSATION)

    def _record_conversation_metrics(self, condensation_cost: float, tokens_saved: int) -> None:
        with self._lock:
            self._metrics[_METRIC_TOTAL_CONDENSATIONS] += 1
            self._metrics[_METRIC_TOTAL_TOKENS_SAVED] += _non_negative_tokens_saved(tokens_saved)
            self._metrics[_METRIC_TOTAL_COST_USD] += condensation_cost

    def _record_pipeline_metrics(self, condensation_cost: float) -> None:
        with self._lock:
            self._metrics[_METRIC_TOTAL_CONDENSATIONS] += 1
            self._metrics[_METRIC_TOTAL_COST_USD] += condensation_cost

    # -- Conversation condensation -----------------------------------------

    def condense(
        self,
        history: list[Message],
        *,
        keep_recent: int = _DEFAULT_KEEP_RECENT,
        summary_max_tokens: int = _DEFAULT_SUMMARY_MAX_TOKENS,
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
        if self._should_skip_condensation(original_count, keep_recent):
            return _unchanged_result(history, original_count)

        t0 = time.perf_counter()

        # Split history
        old_messages, recent_messages = _split_history(history, keep_recent)

        # Format old messages for summarization (sanitize to prevent prompt injection)
        history_text = self._sanitize_for_prompt(self._format_messages(old_messages))

        # Summarize using LIGHTWEIGHT tier
        try:
            resp = self._client.create(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[_user_message(_summary_prompt(history_text))],
                max_tokens=summary_max_tokens,
                system=_CONVERSATION_SUMMARY_SYSTEM,
                policy=_summary_policy(),
            )
            summary_text = resp.text
            condensation_cost = resp.cost_usd
        except Exception as e:
            log.warning(_LOG_CONTEXT_CONDENSATION_FAILED, e)
            # Fallback: just keep recent messages without summary
            return _recent_only_result(recent_messages, original_count)

        # Build condensed message list
        condensed = [
            {"role": "system", "content": f"[이전 대화 요약]\n{summary_text}"},
            *recent_messages,
        ]

        # Estimate tokens saved
        tokens_saved = _estimate_tokens_saved(old_messages, summary_text)

        elapsed_ms = _elapsed_ms(t0)

        self._record_conversation_metrics(condensation_cost, tokens_saved)

        log.info(
            "Condensed %d→%d messages (saved ~%d tokens, cost=$%.4f, %.0fms)",
            original_count,
            len(condensed),
            tokens_saved,
            condensation_cost,
            elapsed_ms,
        )

        return _condensed_result(
            messages=condensed,
            original_count=original_count,
            summary_text=summary_text,
            tokens_saved=tokens_saved,
            condensation_cost=condensation_cost,
            elapsed_ms=elapsed_ms,
        )

    async def acondense(
        self,
        history: list[Message],
        *,
        keep_recent: int = _DEFAULT_KEEP_RECENT,
        summary_max_tokens: int = _DEFAULT_SUMMARY_MAX_TOKENS,
    ) -> CondensationResult:
        """Async version of condense()."""
        original_count = len(history)

        if self._should_skip_condensation(original_count, keep_recent):
            return _unchanged_result(history, original_count)

        t0 = time.perf_counter()
        old_messages, recent_messages = _split_history(history, keep_recent)
        history_text = self._sanitize_for_prompt(self._format_messages(old_messages))

        try:
            resp = await self._client.acreate(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[_user_message(_summary_prompt(history_text))],
                max_tokens=summary_max_tokens,
                system=_CONVERSATION_SUMMARY_SYSTEM,
                policy=_summary_policy(),
            )
            summary_text = resp.text
            condensation_cost = resp.cost_usd
        except Exception as e:
            log.warning(_LOG_ASYNC_CONTEXT_CONDENSATION_FAILED, e)
            return _recent_only_result(recent_messages, original_count)

        condensed = [
            {"role": "system", "content": f"[이전 대화 요약]\n{summary_text}"},
            *recent_messages,
        ]

        tokens_saved = _estimate_tokens_saved(old_messages, summary_text)
        elapsed_ms = _elapsed_ms(t0)

        self._record_conversation_metrics(condensation_cost, tokens_saved)

        return _condensed_result(
            messages=condensed,
            original_count=original_count,
            summary_text=summary_text,
            tokens_saved=tokens_saved,
            condensation_cost=condensation_cost,
            elapsed_ms=elapsed_ms,
        )

    # -- Pipeline condensation ---------------------------------------------

    def condense_pipeline_context(
        self,
        previous_results: list[dict[str, Any]],
        *,
        pipeline_goal: str = "",
        summary_max_tokens: int = _DEFAULT_PIPELINE_SUMMARY_MAX_TOKENS,
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
            f"### {r.get(_PIPELINE_CATEGORY_KEY, f'{_PIPELINE_STAGE_PREFIX} {i + 1}')}\n"
            f"{r.get(_PIPELINE_RESULT_KEY, '')[:_PIPELINE_RESULT_PREVIEW_CHARS]}"
            for i, r in enumerate(previous_results)
        )

        if pipeline_goal:
            results_text = f"파이프라인 목표: {pipeline_goal}\n\n{results_text}"

        # Sanitize to prevent prompt injection
        results_text = self._sanitize_for_prompt(results_text)

        try:
            resp = self._client.create(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[_user_message(_pipeline_summary_prompt(results_text))],
                max_tokens=summary_max_tokens,
                system=_PIPELINE_SUMMARY_SYSTEM,
                policy=_summary_policy(),
            )
            self._record_pipeline_metrics(resp.cost_usd)
            response_text: str = resp.text
            return response_text
        except Exception as e:
            log.warning(_LOG_PIPELINE_CONDENSATION_FAILED, e)
            # Fallback: return truncated results
            return "\n".join(
                f"- {r.get(_PIPELINE_CATEGORY_KEY, _UNKNOWN_PIPELINE_CATEGORY)}: "
                f"{r.get(_PIPELINE_RESULT_KEY, '')[:_PIPELINE_FALLBACK_RESULT_CHARS]}"
                for r in previous_results
            )

    # -- Helpers -----------------------------------------------------------

    @staticmethod
    def _format_messages(messages: list[Message]) -> str:
        """Format messages into a readable text block."""
        lines = []
        for m in messages:
            role = m.get(_MESSAGE_ROLE_KEY, _DEFAULT_MESSAGE_ROLE).upper()
            content = m.get(_MESSAGE_CONTENT_KEY, _DEFAULT_MESSAGE_CONTENT)
            # Truncate very long messages
            if len(content) > _MESSAGE_TRUNCATE_CHARS:
                content = content[:_MESSAGE_TRUNCATE_CHARS] + _MESSAGE_TRUNCATION_SUFFIX
            lines.append(f"[{role}]: {content}")
        return "\n\n".join(lines)

    @property
    def metrics(self) -> Metrics:
        """Return condensation metrics (thread-safe snapshot)."""
        with self._lock:
            return dict(self._metrics)
