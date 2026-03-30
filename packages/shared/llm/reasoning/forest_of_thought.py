"""shared.llm.reasoning.forest_of_thought - Recursive sub-task decomposition.

Implements Forest-of-Thought (FoT) reasoning:
- Decomposes complex queries into independent sub-tasks
- Solves each sub-task with a fresh context (prevents context rot)
- Synthesizes partial results into a coherent final answer

Particularly effective for:
- Complex code generation (multi-file changes)
- Long-form analysis
- Multi-step debugging
- Natural language → code translation in vibe coding

Usage:
    engine = ForestOfThoughtEngine(client)
    result = engine.run(
        messages=[{"role": "user", "content": "전체 시스템 리팩토링 계획"}],
        system="You are an architect.",
    )
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..models import LLMPolicy, TaskTier

if TYPE_CHECKING:
    from ..client import LLMClient

log = logging.getLogger("shared.llm.reasoning.fot")

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_DECOMPOSE_PROMPT = """다음 복잡한 요청을 독립적으로 해결 가능한 서브태스크로 분해해주세요.

<request>
{query}
</request>

규칙:
1. 각 서브태스크는 독립적으로 해결 가능해야 합니다
2. 서브태스크 간 의존 관계가 있으면 순서를 명시하세요
3. 3~7개의 서브태스크로 분해하세요
4. 각 서브태스크를 한 줄로 명확하게 기술하세요

다음 형식으로 응답하세요 (숫자 번호만):
1. [서브태스크 1]
2. [서브태스크 2]
...
"""

_SUBTASK_PROMPT = """다음 서브태스크를 해결해주세요.

<context>
원래 요청: {original_query}
</context>

<subtask>
{subtask}
</subtask>

이 서브태스크만 집중하여 정확하고 구체적인 답변을 제공해주세요."""

_SYNTHESIS_PROMPT = """다음은 하나의 복잡한 요청에 대해 서브태스크별로 해결한 결과입니다.
모든 결과를 종합하여 일관된 최종 답변을 작성해주세요.

<original_request>
{original_query}
</original_request>

<subtask_results>
{results}
</subtask_results>

위 결과를 종합하여 원래 요청에 대한 완전하고 일관된 최종 답변을 작성해주세요.
중복은 제거하고, 모순이 있으면 더 정확한 쪽을 채택하세요."""


@dataclass
class FoTSubtaskResult:
    """Result from solving a single sub-task."""

    subtask: str
    text: str
    backend: str = ""
    cost_usd: float = 0.0
    latency_ms: float = 0.0


@dataclass
class FoTResult:
    """Result from Forest-of-Thought reasoning."""

    text: str
    subtasks: list[str] = field(default_factory=list)
    subtask_results: list[FoTSubtaskResult] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    subtask_count: int = 0


def _parse_subtasks(text: str) -> list[str]:
    """Parse numbered subtask list from LLM response."""
    subtasks = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Match patterns like "1. task" or "1) task" or "- task"
        for prefix_len in range(1, 4):
            if line[prefix_len : prefix_len + 1] in (".", ")", ":"):
                task = line[prefix_len + 1 :].strip()
                if task:
                    subtasks.append(task)
                break
        else:
            if line.startswith("- "):
                subtasks.append(line[2:].strip())
    return subtasks


class ForestOfThoughtEngine:
    """Forest-of-Thought: recursive sub-task decomposition and synthesis.

    Breaks complex queries into manageable sub-tasks, solves each
    independently (preventing context rot), then synthesizes results.
    """

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def run(
        self,
        *,
        messages: list[dict],
        system: str = "",
        policy: LLMPolicy | None = None,
        decompose_tier: TaskTier = TaskTier.MEDIUM,
        solve_tier: TaskTier = TaskTier.MEDIUM,
        synthesize_tier: TaskTier = TaskTier.MEDIUM,
        max_tokens: int = 2000,
        max_subtasks: int = 7,
    ) -> FoTResult:
        """Run Forest-of-Thought decomposition (synchronous)."""
        t0 = time.perf_counter()
        original_query = messages[-1].get("content", "") if messages else ""

        # Step 1: Decompose into sub-tasks
        decompose_resp = self._client.create(
            tier=decompose_tier,
            messages=[{"role": "user", "content": _DECOMPOSE_PROMPT.format(query=original_query)}],
            max_tokens=1000,
            system=system,
            policy=policy,
        )
        subtasks = _parse_subtasks(decompose_resp.text)[:max_subtasks]

        if not subtasks:
            # Fallback: couldn't decompose, do direct generation
            log.warning("FoT: decomposition yielded no subtasks, falling back to direct")
            direct = self._client.create(
                tier=solve_tier,
                messages=messages,
                max_tokens=max_tokens,
                system=system,
                policy=policy,
            )
            return FoTResult(
                text=direct.text,
                total_cost_usd=decompose_resp.cost_usd + direct.cost_usd,
                total_latency_ms=(time.perf_counter() - t0) * 1000,
            )

        log.info("FoT: decomposed into %d subtasks", len(subtasks))

        # Step 2: Solve each sub-task independently
        subtask_results: list[FoTSubtaskResult] = []
        total_cost = decompose_resp.cost_usd

        for idx, subtask in enumerate(subtasks):
            log.debug("FoT: solving subtask %d/%d: %s", idx + 1, len(subtasks), subtask[:60])
            resp = self._client.create(
                tier=solve_tier,
                messages=[
                    {
                        "role": "user",
                        "content": _SUBTASK_PROMPT.format(
                            original_query=original_query,
                            subtask=subtask,
                        ),
                    }
                ],
                max_tokens=max_tokens,
                system=system,
                policy=policy,
            )
            subtask_results.append(
                FoTSubtaskResult(
                    subtask=subtask,
                    text=resp.text,
                    backend=resp.backend,
                    cost_usd=resp.cost_usd,
                    latency_ms=resp.latency_ms,
                )
            )
            total_cost += resp.cost_usd

        # Step 3: Synthesize results
        results_text = "\n\n".join(
            f"### 서브태스크 {i + 1}: {r.subtask}\n{r.text}" for i, r in enumerate(subtask_results)
        )
        synth_resp = self._client.create(
            tier=synthesize_tier,
            messages=[
                {
                    "role": "user",
                    "content": _SYNTHESIS_PROMPT.format(
                        original_query=original_query,
                        results=results_text,
                    ),
                }
            ],
            max_tokens=max_tokens * 2,
            system=system,
            policy=policy,
        )
        total_cost += synth_resp.cost_usd

        return FoTResult(
            text=synth_resp.text,
            subtasks=subtasks,
            subtask_results=subtask_results,
            total_cost_usd=total_cost,
            total_latency_ms=(time.perf_counter() - t0) * 1000,
            subtask_count=len(subtasks),
        )

    async def arun(
        self,
        *,
        messages: list[dict],
        system: str = "",
        policy: LLMPolicy | None = None,
        decompose_tier: TaskTier = TaskTier.MEDIUM,
        solve_tier: TaskTier = TaskTier.MEDIUM,
        synthesize_tier: TaskTier = TaskTier.MEDIUM,
        max_tokens: int = 2000,
        max_subtasks: int = 7,
    ) -> FoTResult:
        """Run Forest-of-Thought decomposition (asynchronous)."""
        t0 = time.perf_counter()
        original_query = messages[-1].get("content", "") if messages else ""

        decompose_resp = await self._client.acreate(
            tier=decompose_tier,
            messages=[{"role": "user", "content": _DECOMPOSE_PROMPT.format(query=original_query)}],
            max_tokens=1000,
            system=system,
            policy=policy,
        )
        subtasks = _parse_subtasks(decompose_resp.text)[:max_subtasks]

        if not subtasks:
            direct = await self._client.acreate(
                tier=solve_tier,
                messages=messages,
                max_tokens=max_tokens,
                system=system,
                policy=policy,
            )
            return FoTResult(
                text=direct.text,
                total_cost_usd=decompose_resp.cost_usd + direct.cost_usd,
                total_latency_ms=(time.perf_counter() - t0) * 1000,
            )

        subtask_results: list[FoTSubtaskResult] = []
        total_cost = decompose_resp.cost_usd

        for idx, subtask in enumerate(subtasks):
            resp = await self._client.acreate(
                tier=solve_tier,
                messages=[
                    {
                        "role": "user",
                        "content": _SUBTASK_PROMPT.format(
                            original_query=original_query,
                            subtask=subtask,
                        ),
                    }
                ],
                max_tokens=max_tokens,
                system=system,
                policy=policy,
            )
            subtask_results.append(
                FoTSubtaskResult(
                    subtask=subtask,
                    text=resp.text,
                    backend=resp.backend,
                    cost_usd=resp.cost_usd,
                    latency_ms=resp.latency_ms,
                )
            )
            total_cost += resp.cost_usd

        results_text = "\n\n".join(
            f"### 서브태스크 {i + 1}: {r.subtask}\n{r.text}" for i, r in enumerate(subtask_results)
        )
        synth_resp = await self._client.acreate(
            tier=synthesize_tier,
            messages=[
                {
                    "role": "user",
                    "content": _SYNTHESIS_PROMPT.format(
                        original_query=original_query,
                        results=results_text,
                    ),
                }
            ],
            max_tokens=max_tokens * 2,
            system=system,
            policy=policy,
        )
        total_cost += synth_resp.cost_usd

        return FoTResult(
            text=synth_resp.text,
            subtasks=subtasks,
            subtask_results=subtask_results,
            total_cost_usd=total_cost,
            total_latency_ms=(time.perf_counter() - t0) * 1000,
            subtask_count=len(subtasks),
        )
