"""shared.llm.reasoning.smart_router - Query complexity estimation and routing.

Implements Smart Routing for the inference engine:
- Analyzes query complexity WITHOUT making an LLM call (heuristic-based)
- Routes to the optimal reasoning strategy based on complexity
- Integrates CoT, FoT, SAGE, and direct calls into a unified interface

Complexity levels:
- LOW:      Direct Qwen3-Coder call (fast, $0)
- MEDIUM:   SAGE-enhanced call (adaptive depth)
- HIGH:     CoT multi-sample consensus
- CRITICAL: FoT recursive decomposition

Usage:
    from shared.llm.reasoning import SmartRouter

    router = SmartRouter(client)
    result = router.route_and_reason(
        messages=[{"role": "user", "content": "복잡한 시스템 설계"}],
        system="You are an architect.",
    )
"""

from __future__ import annotations

import enum
import logging
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..config import REASONING_CONFIG
from ..models import LLMPolicy, TaskTier

if TYPE_CHECKING:
    from ..client import LLMClient
    from ..context_map import ContextMap

log = logging.getLogger("shared.llm.reasoning.router")


class QueryComplexity(enum.Enum):
    """Estimated complexity of a user query."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ReasoningResult:
    """Result from the smart routing pipeline."""

    text: str
    strategy_used: str = "direct"
    complexity: QueryComplexity = QueryComplexity.LOW
    confidence: float = 0.0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    reasoning_metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Complexity estimation heuristics
# ---------------------------------------------------------------------------

# Keywords indicating different complexity levels
_CRITICAL_KEYWORDS = frozenset(
    {
        "리팩토링",
        "refactor",
        "전체",
        "entire",
        "시스템",
        "system",
        "아키텍처",
        "architecture",
        "마이그레이션",
        "migration",
        "redesign",
        "재설계",
        "multi-file",
        "다중 파일",
        "분산",
        "distributed",
        "microservice",
        "마이크로서비스",
    }
)

_HIGH_KEYWORDS = frozenset(
    {
        "디버깅",
        "debug",
        "debugging",
        "버그",
        "bug",
        "fix",
        "최적화",
        "optimize",
        "optimization",
        "성능",
        "performance",
        "보안",
        "security",
        "취약점",
        "vulnerability",
        "테스트",
        "test",
        "testing",
        "복잡한",
        "complex",
        "알고리즘",
        "algorithm",
        "분석",
        "analysis",
        "analyze",
        "설계",
        "design",
        "계획",
        "plan",
        "planning",
    }
)

_MEDIUM_KEYWORDS = frozenset(
    {
        "구현",
        "implement",
        "생성",
        "create",
        "generate",
        "작성",
        "write",
        "추가",
        "add",
        "수정",
        "modify",
        "함수",
        "function",
        "클래스",
        "class",
        "모듈",
        "module",
        "API",
        "endpoint",
        "라우트",
        "route",
        "설명",
        "explain",
        "요약",
        "summary",
        "summarize",
    }
)


def estimate_complexity(query: str) -> QueryComplexity:
    """Estimate query complexity using keyword heuristics and structural analysis.

    This function does NOT make any LLM calls — it's purely rule-based
    to avoid additional API cost overhead.
    """
    query_lower = query.lower()
    query_len = len(query)

    # Score accumulation
    score = 0

    # Keyword matching (weighted)
    for kw in _CRITICAL_KEYWORDS:
        if kw in query_lower:
            score += 3

    for kw in _HIGH_KEYWORDS:
        if kw in query_lower:
            score += 2

    for kw in _MEDIUM_KEYWORDS:
        if kw in query_lower:
            score += 1

    # Length-based scoring
    if query_len > 2000:
        score += 3
    elif query_len > 1000:
        score += 2
    elif query_len > 500:
        score += 1

    # Multi-line queries indicate more complexity
    line_count = query.count("\n") + 1
    if line_count > 20:
        score += 3
    elif line_count > 10:
        score += 2
    elif line_count > 5:
        score += 1

    # Code blocks in the query suggest technical complexity
    code_blocks = len(re.findall(r"```", query))
    score += code_blocks

    # Multiple questions/requirements
    question_marks = query.count("?")
    if question_marks > 3:
        score += 2
    elif question_marks > 1:
        score += 1

    # Numbered requirements lists
    numbered_items = len(re.findall(r"^\s*\d+[.)]\s", query, re.MULTILINE))
    if numbered_items > 5:
        score += 3
    elif numbered_items > 2:
        score += 1

    # Classify based on total score
    if score >= 10:
        return QueryComplexity.CRITICAL
    elif score >= 6:
        return QueryComplexity.HIGH
    elif score >= 3:
        return QueryComplexity.MEDIUM
    else:
        return QueryComplexity.LOW


# ---------------------------------------------------------------------------
# Smart Router
# ---------------------------------------------------------------------------


class SmartRouter:
    """Unified reasoning router that selects the optimal strategy.

    Routes queries to the appropriate reasoning engine based on
    estimated complexity, without making LLM calls for routing itself.
    """

    def __init__(
        self,
        client: LLMClient,
        context_map: ContextMap | None = None,
    ) -> None:
        self._client = client
        self._config = REASONING_CONFIG
        self._context_map = context_map

    def route_and_reason(
        self,
        *,
        messages: list[dict],
        system: str = "",
        policy: LLMPolicy | None = None,
        tier: TaskTier | None = None,
        max_tokens: int = 2000,
        force_strategy: str | None = None,
    ) -> ReasoningResult:
        """Route to the optimal reasoning strategy and execute (synchronous).

        Args:
            force_strategy: Override auto-routing. One of: "direct", "sage",
                "cot", "fot". If None, auto-selects based on complexity.
        """
        t0 = time.perf_counter()
        query = messages[-1].get("content", "") if messages else ""
        complexity = estimate_complexity(query)

        # Inject code context for complex queries (Phase 2.2)
        enriched_system = self._inject_code_context(system, query, complexity)

        strategy = force_strategy or self._select_strategy(complexity)
        resolved_tier = tier or self._tier_for_complexity(complexity)

        log.info(
            "SmartRouter: complexity=%s, strategy=%s, tier=%s, code_context=%s",
            complexity.value, strategy, resolved_tier.value,
            "injected" if enriched_system != system else "none",
        )

        if strategy == "direct":
            return self._run_direct(
                messages=messages,
                system=enriched_system,
                policy=policy,
                tier=resolved_tier,
                max_tokens=max_tokens,
                complexity=complexity,
                t0=t0,
            )
        elif strategy == "sage":
            return self._run_sage(
                messages=messages,
                system=enriched_system,
                policy=policy,
                tier=resolved_tier,
                max_tokens=max_tokens,
                complexity=complexity,
                t0=t0,
            )
        elif strategy == "cot":
            return self._run_cot(
                messages=messages,
                system=enriched_system,
                policy=policy,
                tier=resolved_tier,
                max_tokens=max_tokens,
                complexity=complexity,
                t0=t0,
            )
        elif strategy == "fot":
            return self._run_fot(
                messages=messages,
                system=enriched_system,
                policy=policy,
                tier=resolved_tier,
                max_tokens=max_tokens,
                complexity=complexity,
                t0=t0,
            )
        else:
            log.warning("SmartRouter: unknown strategy '%s', falling back to direct", strategy)
            return self._run_direct(
                messages=messages,
                system=enriched_system,
                policy=policy,
                tier=resolved_tier,
                max_tokens=max_tokens,
                complexity=complexity,
                t0=t0,
            )

    async def aroute_and_reason(
        self,
        *,
        messages: list[dict],
        system: str = "",
        policy: LLMPolicy | None = None,
        tier: TaskTier | None = None,
        max_tokens: int = 2000,
        force_strategy: str | None = None,
    ) -> ReasoningResult:
        """Route to the optimal reasoning strategy (asynchronous)."""
        t0 = time.perf_counter()
        query = messages[-1].get("content", "") if messages else ""
        complexity = estimate_complexity(query)

        # Inject code context for complex queries (Phase 2.2)
        enriched_system = self._inject_code_context(system, query, complexity)

        strategy = force_strategy or self._select_strategy(complexity)
        resolved_tier = tier or self._tier_for_complexity(complexity)

        log.info("SmartRouter async: complexity=%s, strategy=%s", complexity.value, strategy)

        # Async routing uses enriched_system for all strategies
        if strategy == "direct":
            resp = await self._client.acreate(
                tier=resolved_tier,
                messages=messages,
                max_tokens=max_tokens,
                system=enriched_system,
                policy=policy,
            )
            return ReasoningResult(
                text=resp.text,
                strategy_used="direct",
                complexity=complexity,
                confidence=1.0,
                total_cost_usd=resp.cost_usd,
                total_latency_ms=(time.perf_counter() - t0) * 1000,
            )
        elif strategy == "sage":
            from .sage import SAGEEngine

            engine = SAGEEngine(self._client)
            result = await engine.arun(
                messages=messages,
                system=enriched_system,
                policy=policy,
                tier=resolved_tier,
                max_tokens=max_tokens,
                confidence_high=self._config["sage_confidence_high"],
                confidence_low=self._config["sage_confidence_low"],
            )
            return ReasoningResult(
                text=result.text,
                strategy_used="sage",
                complexity=complexity,
                confidence=result.confidence,
                total_cost_usd=result.total_cost_usd,
                total_latency_ms=(time.perf_counter() - t0) * 1000,
                reasoning_metadata={"stages": result.stages_applied, "enhanced": result.was_enhanced},
            )
        elif strategy == "cot":
            from .chain_of_thought import ChainOfThoughtEngine

            engine = ChainOfThoughtEngine(self._client)
            result = await engine.arun(
                messages=messages,
                system=enriched_system,
                policy=policy,
                tier=resolved_tier,
                max_tokens=max_tokens,
                n_samples=self._config["cot_samples"],
                consensus_threshold=self._config["cot_consensus_threshold"],
            )
            return ReasoningResult(
                text=result.text,
                strategy_used="cot",
                complexity=complexity,
                confidence=result.confidence,
                total_cost_usd=result.total_cost_usd,
                total_latency_ms=(time.perf_counter() - t0) * 1000,
                reasoning_metadata={"samples": result.samples_used, "early_stopped": result.early_stopped},
            )
        elif strategy == "fot":
            from .forest_of_thought import ForestOfThoughtEngine

            engine = ForestOfThoughtEngine(self._client)
            result = await engine.arun(
                messages=messages,
                system=enriched_system,
                policy=policy,
                decompose_tier=resolved_tier,
                solve_tier=resolved_tier,
                synthesize_tier=resolved_tier,
                max_tokens=max_tokens,
                max_subtasks=self._config["fot_max_depth"] + 2,
            )
            return ReasoningResult(
                text=result.text,
                strategy_used="fot",
                complexity=complexity,
                confidence=0.8,
                total_cost_usd=result.total_cost_usd,
                total_latency_ms=(time.perf_counter() - t0) * 1000,
                reasoning_metadata={"subtasks": result.subtask_count},
            )
        else:
            resp = await self._client.acreate(
                tier=resolved_tier,
                messages=messages,
                max_tokens=max_tokens,
                system=enriched_system,
                policy=policy,
            )
            return ReasoningResult(
                text=resp.text,
                strategy_used="direct",
                complexity=complexity,
                total_cost_usd=resp.cost_usd,
                total_latency_ms=(time.perf_counter() - t0) * 1000,
            )

    # -- Strategy selection --

    def _select_strategy(self, complexity: QueryComplexity) -> str:
        """Select reasoning strategy based on complexity."""
        if not self._config.get("enabled", True):
            return "direct"

        mapping = {
            QueryComplexity.LOW: "direct",
            QueryComplexity.MEDIUM: "sage",
            QueryComplexity.HIGH: "cot",
            QueryComplexity.CRITICAL: "fot",
        }
        return mapping.get(complexity, "direct")

    def _tier_for_complexity(self, complexity: QueryComplexity) -> TaskTier:
        """Select TaskTier based on complexity level."""
        if self._config.get("prefer_local", False):
            # When prefer_local is set, use local models more aggressively
            return (
                TaskTier.MEDIUM
                if complexity in (QueryComplexity.HIGH, QueryComplexity.CRITICAL)
                else TaskTier.LIGHTWEIGHT
            )

        mapping = {
            QueryComplexity.LOW: TaskTier.LIGHTWEIGHT,
            QueryComplexity.MEDIUM: TaskTier.MEDIUM,
            QueryComplexity.HIGH: TaskTier.MEDIUM,
            QueryComplexity.CRITICAL: TaskTier.HEAVY,
        }
        return mapping.get(complexity, TaskTier.MEDIUM)

    # -- Code context injection (Phase 2.2) --

    def _inject_code_context(
        self,
        system: str,
        query: str,
        complexity: QueryComplexity,
    ) -> str:
        """Inject relevant code context into the system prompt for complex queries.

        Only activates for MEDIUM+ complexity to avoid overhead on simple queries.
        Uses the AST-based ContextMap (no LLM calls).
        """
        if self._context_map is None:
            return system

        # Only inject for queries that benefit from code context
        if complexity == QueryComplexity.LOW:
            return system

        # Scale token budget by complexity
        token_budgets = {
            QueryComplexity.MEDIUM: 500,
            QueryComplexity.HIGH: 800,
            QueryComplexity.CRITICAL: 1200,
        }
        max_tokens = token_budgets.get(complexity, 500)

        try:
            code_context = self._context_map.get_relevant_context(
                query, max_tokens=max_tokens,
            )
            if code_context:
                separator = "\n\n" if system else ""
                return f"{system}{separator}{code_context}"
        except Exception as e:
            log.debug("Code context injection failed (non-fatal): %s", e)

        return system

    # -- Strategy runners (sync) --

    def _run_direct(self, *, messages, system, policy, tier, max_tokens, complexity, t0) -> ReasoningResult:
        resp = self._client.create(
            tier=tier,
            messages=messages,
            max_tokens=max_tokens,
            system=system,
            policy=policy,
        )
        return ReasoningResult(
            text=resp.text,
            strategy_used="direct",
            complexity=complexity,
            confidence=1.0,
            total_cost_usd=resp.cost_usd,
            total_latency_ms=(time.perf_counter() - t0) * 1000,
        )

    def _run_sage(self, *, messages, system, policy, tier, max_tokens, complexity, t0) -> ReasoningResult:
        from .sage import SAGEEngine

        engine = SAGEEngine(self._client)
        result = engine.run(
            messages=messages,
            system=system,
            policy=policy,
            tier=tier,
            max_tokens=max_tokens,
            confidence_high=self._config["sage_confidence_high"],
            confidence_low=self._config["sage_confidence_low"],
        )
        return ReasoningResult(
            text=result.text,
            strategy_used="sage",
            complexity=complexity,
            confidence=result.confidence,
            total_cost_usd=result.total_cost_usd,
            total_latency_ms=(time.perf_counter() - t0) * 1000,
            reasoning_metadata={"stages": result.stages_applied, "enhanced": result.was_enhanced},
        )

    def _run_cot(self, *, messages, system, policy, tier, max_tokens, complexity, t0) -> ReasoningResult:
        from .chain_of_thought import ChainOfThoughtEngine

        engine = ChainOfThoughtEngine(self._client)
        result = engine.run(
            messages=messages,
            system=system,
            policy=policy,
            tier=tier,
            max_tokens=max_tokens,
            n_samples=self._config["cot_samples"],
            consensus_threshold=self._config["cot_consensus_threshold"],
        )
        return ReasoningResult(
            text=result.text,
            strategy_used="cot",
            complexity=complexity,
            confidence=result.confidence,
            total_cost_usd=result.total_cost_usd,
            total_latency_ms=(time.perf_counter() - t0) * 1000,
            reasoning_metadata={"samples": result.samples_used, "early_stopped": result.early_stopped},
        )

    def _run_fot(self, *, messages, system, policy, tier, max_tokens, complexity, t0) -> ReasoningResult:
        from .forest_of_thought import ForestOfThoughtEngine

        engine = ForestOfThoughtEngine(self._client)
        result = engine.run(
            messages=messages,
            system=system,
            policy=policy,
            decompose_tier=tier,
            solve_tier=tier,
            synthesize_tier=tier,
            max_tokens=max_tokens,
            max_subtasks=self._config["fot_max_depth"] + 2,
        )
        return ReasoningResult(
            text=result.text,
            strategy_used="fot",
            complexity=complexity,
            confidence=0.8,
            total_cost_usd=result.total_cost_usd,
            total_latency_ms=(time.perf_counter() - t0) * 1000,
            reasoning_metadata={"subtasks": result.subtask_count},
        )
