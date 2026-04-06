"""shared.harness.coordination.graph — Multi-agent pipeline graph.

LangGraph-based coordination layer for content generation pipelines.
Each node in the graph is a governed agent step that uses the existing
shared.llm.client and shared.harness governance.

Architecture:

    [collect] → [analyze] → [generate] → [qa] ─┬─→ [publish] → END
                                                 │
                                                 └─→ [generate] (retry)

Usage::

    from shared.harness.coordination import build_content_pipeline

    graph = build_content_pipeline(constitution)
    result = await graph.run({"trends_input": raw_trends})
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Awaitable, Optional

logger = logging.getLogger(__name__)

# --- LangGraph imports (graceful fallback) ---
try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    END = "end"
    StateGraph = None  # type: ignore[assignment]

from ..constitution import Constitution
from ..adapters.native import NativeHarnessAdapter


# --- State ---

class PipelineState(dict):
    """State for the content generation pipeline graph.

    Uses dict subclass for LangGraph compatibility. Key fields:

    - trends_input: Raw trend data to process
    - collected: Collected/enriched trend data
    - scored: Scored and filtered trends
    - generated: Generated content items
    - qa_results: Quality assessment results
    - approved: Whether content passed QA
    - retry_count: Number of generation retries
    - errors: Accumulated error messages
    - trace: Execution trace entries
    """

    @classmethod
    def initial(cls, trends_input: Any = None) -> PipelineState:
        return cls(
            trends_input=trends_input,
            collected=[],
            scored=[],
            generated=[],
            qa_results=[],
            approved=False,
            retry_count=0,
            max_retries=2,
            errors=[],
            trace=[],
        )


# --- Node Functions ---

AgentStepFn = Callable[[PipelineState], Awaitable[PipelineState]]


@dataclass
class ContentPipelineGraph:
    """Configurable multi-agent content pipeline.

    Each step can be overridden with a custom function, enabling
    the pipeline to be adapted for different content types
    (news, social media, research briefs, etc.).
    """

    adapter: NativeHarnessAdapter
    collect_fn: Optional[AgentStepFn] = None
    analyze_fn: Optional[AgentStepFn] = None
    generate_fn: Optional[AgentStepFn] = None
    qa_fn: Optional[AgentStepFn] = None
    publish_fn: Optional[AgentStepFn] = None
    qa_threshold: float = 7.0

    def _trace_entry(self, step_name: str, status: str, detail: str = "") -> dict:
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "step": step_name,
            "status": status,
            "detail": detail[:500],
        }

    async def _default_collect(self, state: PipelineState) -> PipelineState:
        """Default collect node — pass-through if no custom fn."""
        state["collected"] = state.get("trends_input", [])
        state["trace"].append(self._trace_entry("collect", "success", f"{len(state['collected'])} items"))
        return state

    async def _default_analyze(self, state: PipelineState) -> PipelineState:
        """Default analyze node — pass-through scoring."""
        items = state.get("collected", [])
        scored = []
        for item in items:
            if isinstance(item, dict):
                scored.append({**item, "score": item.get("score", 5.0)})
            else:
                scored.append({"data": item, "score": 5.0})
        state["scored"] = scored
        state["trace"].append(self._trace_entry("analyze", "success", f"{len(scored)} scored"))
        return state

    async def _default_generate(self, state: PipelineState) -> PipelineState:
        """Default generate node — uses adapter governance."""
        scored = state.get("scored", [])
        generated = []
        for item in scored:
            try:
                result = await self.adapter.execute_with_governance(
                    task={"action": "llm_call", "input": {"content": item}},
                    tools=["llm_call"],
                    cost_estimate=0.01,
                )
                generated.append({
                    "source": item,
                    "content": result.output,
                    "success": result.success,
                })
            except Exception as e:
                state["errors"].append(f"generate:{type(e).__name__}:{e}")
                generated.append({
                    "source": item,
                    "content": None,
                    "success": False,
                })

        state["generated"] = generated
        state["retry_count"] = state.get("retry_count", 0)
        state["trace"].append(
            self._trace_entry("generate", "success", f"{len(generated)} items, retry={state['retry_count']}")
        )
        return state

    async def _default_qa(self, state: PipelineState) -> PipelineState:
        """Default QA node — checks generated content quality."""
        generated = state.get("generated", [])
        qa_results = []
        for item in generated:
            if not item.get("success") or item.get("content") is None:
                qa_results.append({"item": item, "score": 0.0, "passed": False})
                continue
            # Default: pass everything with a neutral score
            qa_results.append({"item": item, "score": 7.5, "passed": True})

        state["qa_results"] = qa_results

        # Calculate approval
        passing = [r for r in qa_results if r["passed"]]
        avg_score = sum(r["score"] for r in passing) / max(len(passing), 1)
        state["approved"] = avg_score >= self.qa_threshold and len(passing) > 0

        state["trace"].append(
            self._trace_entry(
                "qa",
                "approved" if state["approved"] else "rejected",
                f"avg={avg_score:.1f} threshold={self.qa_threshold} passing={len(passing)}/{len(qa_results)}",
            )
        )
        return state

    async def _default_publish(self, state: PipelineState) -> PipelineState:
        """Default publish node — logs success, actual publishing via override."""
        approved_items = [r["item"] for r in state.get("qa_results", []) if r.get("passed")]
        state["trace"].append(
            self._trace_entry("publish", "success", f"{len(approved_items)} items ready")
        )
        return state

    def _should_retry(self, state: PipelineState) -> str:
        """Conditional edge: retry generation or proceed to publish."""
        if state.get("approved"):
            return "publish"
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)
        if retry_count < max_retries:
            return "regenerate"
        # Exhausted retries — mark as best effort and publish
        state["best_effort"] = True
        return "publish"

    async def _retry_gate(self, state: PipelineState) -> PipelineState:
        """Increment retry counter before re-entering generate."""
        state["retry_count"] = state.get("retry_count", 0) + 1
        state["trace"].append(
            self._trace_entry("retry_gate", "retrying", f"attempt {state['retry_count']}")
        )
        return state

    def build(self) -> Any:
        """Build the LangGraph StateGraph.

        Returns a compiled graph that can be invoked with:
            result = await graph.ainvoke(PipelineState.initial(trends))
        """
        if not LANGGRAPH_AVAILABLE:
            raise ImportError(
                "langgraph is required for coordination graphs. "
                "Install with: pip install langgraph"
            )

        graph = StateGraph(dict)

        # Register nodes with custom overrides
        graph.add_node("collect", self.collect_fn or self._default_collect)
        graph.add_node("analyze", self.analyze_fn or self._default_analyze)
        graph.add_node("generate", self.generate_fn or self._default_generate)
        graph.add_node("qa", self.qa_fn or self._default_qa)
        graph.add_node("publish", self.publish_fn or self._default_publish)
        graph.add_node("retry_gate", self._retry_gate)

        # Edges: linear flow with conditional retry loop
        graph.set_entry_point("collect")
        graph.add_edge("collect", "analyze")
        graph.add_edge("analyze", "generate")
        graph.add_edge("generate", "qa")

        # QA → conditional: publish or retry
        graph.add_conditional_edges(
            "qa",
            self._should_retry,
            {
                "publish": "publish",
                "regenerate": "retry_gate",
            },
        )
        graph.add_edge("retry_gate", "generate")
        graph.add_edge("publish", END)

        return graph.compile()

    async def run(self, initial_state: dict | None = None) -> PipelineState:
        """Convenience method: build and run the graph.

        Args:
            initial_state: Override initial state. If None, uses empty state.

        Returns:
            Final PipelineState after graph execution.
        """
        compiled = self.build()
        state = initial_state or PipelineState.initial()
        result = await compiled.ainvoke(state)
        return PipelineState(result)


# --- Factory ---

def build_content_pipeline(
    constitution: Constitution,
    *,
    qa_threshold: float = 7.0,
    collect_fn: Optional[AgentStepFn] = None,
    analyze_fn: Optional[AgentStepFn] = None,
    generate_fn: Optional[AgentStepFn] = None,
    qa_fn: Optional[AgentStepFn] = None,
    publish_fn: Optional[AgentStepFn] = None,
) -> ContentPipelineGraph:
    """Factory to create a governed content pipeline.

    Usage::

        from shared.harness import Constitution
        from shared.harness.coordination import build_content_pipeline

        constitution = Constitution.from_yaml("constitutions/getdaytrends.yaml")
        pipeline = build_content_pipeline(
            constitution,
            qa_threshold=7.5,
            generate_fn=my_custom_generator,
        )
        result = await pipeline.run({"trends_input": raw_trends})
    """
    adapter = NativeHarnessAdapter(constitution)
    return ContentPipelineGraph(
        adapter=adapter,
        qa_threshold=qa_threshold,
        collect_fn=collect_fn,
        analyze_fn=analyze_fn,
        generate_fn=generate_fn,
        qa_fn=qa_fn,
        publish_fn=publish_fn,
    )
