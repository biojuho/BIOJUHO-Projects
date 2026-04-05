"""getdaytrends.harness_integration — Harness Governance Layer for Pipeline.

Non-invasive middleware that wraps each pipeline step as a governed
"tool call" through shared.harness. This module acts as the bridge
between the existing pipeline orchestrator and the new governance layer.

Architecture:
    main.py → pipeline.py → harness_integration.py → shared.harness
                                    ↓
                            Constitution check
                            Risk scan
                            Audit logging
                            Budget gating
                                    ↓
                            original step function

Usage (in pipeline.py):
    from getdaytrends.harness_integration import get_pipeline_harness

    harness = get_pipeline_harness(config)
    # harness is None if not enabled, allowing graceful fallback
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_CONSTITUTION_PATH = Path(__file__).parent / "constitution.yaml"

# Lazy-loaded singleton
_harness_instance: Any | None = None


def _load_constitution():
    """Load the GetDayTrends constitution from YAML."""
    from shared.harness.constitution import Constitution

    if _CONSTITUTION_PATH.exists():
        return Constitution.from_yaml(_CONSTITUTION_PATH)

    # Fallback: try shared location
    shared_path = Path(__file__).resolve().parents[1] / "shared" / "harness" / "constitutions" / "getdaytrends.yaml"
    if shared_path.exists():
        return Constitution.from_yaml(shared_path)

    # Last resort: minimal in-code constitution
    return Constitution.from_dict({
        "agent_name": "getdaytrends-pipeline",
        "max_budget_usd": 2.0,
        "tools": [
            {"name": "collect_trends", "allowed": True, "max_calls": 10},
            {"name": "score_trends", "allowed": True, "max_calls": 10},
            {"name": "generate_content", "allowed": True, "max_calls": 50},
            {"name": "save_results", "allowed": True, "max_calls": 20},
            {"name": "web_search", "allowed": True, "max_calls": 100},
            {"name": "llm_call", "allowed": True, "max_calls": 200},
            {"name": "database_write", "allowed": True, "max_calls": 100},
            {"name": "database_read", "allowed": True, "max_calls": 200},
            {"name": "notion_api", "allowed": True, "max_calls": 30},
            {"name": "shell_execute", "allowed": True, "max_calls": 5,
             "requires_approval": True},
            {"name": "file_delete", "allowed": False},
        ],
        "risk_patterns": [
            r"rm -rf",
            r"DROP TABLE",
            r"os\.system\(",
            r"eval\(",
        ],
    })


def get_pipeline_harness(config=None):
    """Get or create the pipeline harness singleton.

    Returns None if shared.harness is not available, allowing the
    pipeline to fall back to ungovoked execution gracefully.
    """
    global _harness_instance

    if _harness_instance is not None:
        return _harness_instance

    try:
        from shared.harness import AuditLogger, HarnessConfig, HarnessWrapper
        from shared.harness.hooks import (
            HookChain,
            InputSanitizerHook,
            MetricsHook,
            OutputTruncatorHook,
        )
        from shared.harness.risk import RiskScanner
    except ImportError:
        log.debug("shared.harness not available — running without governance")
        return None

    try:
        constitution = _load_constitution()

        # Audit log path
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        audit_log_path = log_dir / "harness_audit.jsonl"

        # Configure components
        audit_logger = AuditLogger(
            agent_name=constitution.agent_name,
            log_path=audit_log_path,
            emit_to_logging=True,
            max_input_chars=300,
        )

        risk_scanner = RiskScanner(constitution)

        metrics_hook = MetricsHook()
        hook_chain = HookChain(
            pre_hooks=[InputSanitizerHook()],
            post_hooks=[OutputTruncatorHook(max_chars=50_000), metrics_hook],
        )

        # HITL callback for tools requiring approval (e.g., shell_execute)
        try:
            from shared.harness.hitl import create_notifier_hitl_callback
            hitl_cb = create_notifier_hitl_callback(notify_only=True)
        except ImportError:
            hitl_cb = None

        harness_config = HarnessConfig(
            constitution=constitution,
            audit_logger=audit_logger,
            risk_scanner=risk_scanner,
            hook_chain=hook_chain,
            hitl_callback=hitl_cb,
        )

        _harness_instance = HarnessWrapper(harness_config)
        log.info(
            f"[Harness] Governance enabled — agent={constitution.agent_name} "
            f"tools={len(constitution.allowed_tools())} "
            f"budget=${constitution.max_budget_usd:.2f}"
        )
        return _harness_instance

    except Exception as e:
        log.warning(f"[Harness] Initialization failed (running ungoverned): {e}")
        return None


async def governed_step(
    step_name: str,
    step_fn,
    *args,
    harness=None,
    cost_estimate: float = 0.0,
    **kwargs,
):
    """Execute a pipeline step through the harness governance layer.

    If harness is None (not available), executes the step directly.
    This is the key integration point — each pipeline step becomes
    a governed "tool call" that goes through the 6-step governance pipeline.

    Args:
        step_name: Tool name for governance (e.g., "collect_trends").
        step_fn: The actual async step function to execute.
        *args: Arguments for step_fn.
        harness: HarnessWrapper instance (None = bypass governance).
        cost_estimate: Estimated USD cost for budget gating.
        **kwargs: Keyword arguments for step_fn.

    Returns:
        The result of step_fn execution.
    """
    if harness is None:
        # No governance — direct execution
        if asyncio.iscoroutinefunction(step_fn):
            return await step_fn(*args, **kwargs)
        return step_fn(*args, **kwargs)

    # Create an executor that calls the actual step function
    async def _executor(tool_name: str, tool_input: Any) -> Any:
        fn = tool_input.get("_fn")
        fn_args = tool_input.get("_args", ())
        fn_kwargs = tool_input.get("_kwargs", {})
        if asyncio.iscoroutinefunction(fn):
            return await fn(*fn_args, **fn_kwargs)
        return fn(*fn_args, **fn_kwargs)

    tool_input = {
        "_fn": step_fn,
        "_args": args,
        "_kwargs": kwargs,
        "step": step_name,
    }

    return await harness.execute_tool(
        step_name,
        tool_input,
        executor=_executor,
        cost_estimate=cost_estimate,
    )


def print_harness_summary(harness) -> None:
    """Print a post-run governance summary."""
    if harness is None:
        return

    summary = harness.get_session_summary()
    print("\n  [Harness] Governance Summary")
    print("  " + "-" * 33)
    print(f"  Agent          : {summary['agent_name']}")
    print(f"  Total calls    : {summary['total_calls']}")
    print(f"  Session cost   : ${summary['session_cost_usd']:.4f}")
    print(f"  Budget remain  : ${summary['budget_remaining_usd']:.4f}")
    print(f"  Denied actions : {summary['audit_denied_count']}")

    if summary['tool_call_counts']:
        print("  Tool breakdown :")
        for tool, count in sorted(summary['tool_call_counts'].items(), key=lambda x: -x[1]):
            print(f"    {tool}: {count}")


