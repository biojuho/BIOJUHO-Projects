"""shared.llm.meta_optimizer - AWO-inspired workflow optimization engine.

Analyzes accumulated WorkflowTracer data to:
1. Detect repeated prompt patterns across pipelines
2. Suggest template conversions (replace LLM calls with hardcoded templates)
3. Identify underperforming stages for model/tier adjustment
4. Generate optimization reports

This module bridges the gap between raw trace data and actionable
optimizations, following the AWO (Agent Workflow Optimization) philosophy
of automated workflow improvement.

Usage:
    from shared.llm.meta_optimizer import MetaOptimizer

    optimizer = MetaOptimizer()
    report = optimizer.generate_report()
    suggestions = optimizer.suggest_optimizations()
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.telemetry.workflow_trace import PromptPattern, WorkflowTracer

log = logging.getLogger("shared.llm.meta_optimizer")


# ---------------------------------------------------------------------------
# Optimization suggestion types
# ---------------------------------------------------------------------------


class OptimizationType:
    """Types of optimization suggestions."""

    TEMPLATE_CONVERSION = "template_conversion"
    TIER_DOWNGRADE = "tier_downgrade"
    CACHE_CANDIDATE = "cache_candidate"
    STAGE_ELIMINATION = "stage_elimination"
    BATCH_MERGE = "batch_merge"


@dataclass
class OptimizationSuggestion:
    """A single optimization suggestion."""

    type: str
    priority: str  # "high", "medium", "low"
    pipeline: str
    stage: str = ""
    description: str = ""
    estimated_savings_usd: float = 0.0
    estimated_token_savings: int = 0
    prompt_hash: str = ""
    confidence: float = 0.0
    action: str = ""  # recommended action


@dataclass
class OptimizationReport:
    """Full optimization report from trace analysis."""

    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    analysis_period_days: int = 7
    total_traces_analyzed: int = 0
    total_cost_usd: float = 0.0
    suggestions: list[OptimizationSuggestion] = field(default_factory=list)
    pipeline_summaries: dict[str, dict] = field(default_factory=dict)
    repeated_patterns: list[dict] = field(default_factory=list)

    @property
    def total_estimated_savings(self) -> float:
        return sum(s.estimated_savings_usd for s in self.suggestions)

    @property
    def high_priority_count(self) -> int:
        return sum(1 for s in self.suggestions if s.priority == "high")

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dict."""
        return {
            "generated_at": self.generated_at,
            "analysis_period_days": self.analysis_period_days,
            "total_traces_analyzed": self.total_traces_analyzed,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_estimated_savings_usd": round(self.total_estimated_savings, 4),
            "high_priority_suggestions": self.high_priority_count,
            "suggestions": [
                {
                    "type": s.type,
                    "priority": s.priority,
                    "pipeline": s.pipeline,
                    "stage": s.stage,
                    "description": s.description,
                    "estimated_savings_usd": round(s.estimated_savings_usd, 6),
                    "action": s.action,
                }
                for s in self.suggestions
            ],
            "pipeline_summaries": self.pipeline_summaries,
        }

    def to_markdown(self) -> str:
        """Format as a human-readable markdown report."""
        lines = [
            "# 🔧 Meta-Optimizer Report",
            f"\n> Generated: {self.generated_at}",
            f"> Period: last {self.analysis_period_days} days",
            f"> Traces analyzed: {self.total_traces_analyzed}",
            f"> Total cost: ${self.total_cost_usd:.4f}",
            f"> **Estimated savings: ${self.total_estimated_savings:.4f}**",
        ]

        if self.suggestions:
            lines.append("\n## Optimization Suggestions\n")
            for i, s in enumerate(self.suggestions, 1):
                icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(s.priority, "⚪")
                lines.append(f"### {i}. {icon} [{s.priority.upper()}] {s.description}")
                lines.append(f"- **Pipeline**: {s.pipeline}")
                if s.stage:
                    lines.append(f"- **Stage**: {s.stage}")
                lines.append(f"- **Estimated savings**: ${s.estimated_savings_usd:.6f}")
                lines.append(f"- **Action**: {s.action}")
                lines.append("")

        if self.pipeline_summaries:
            lines.append("\n## Pipeline Summaries\n")
            lines.append("| Pipeline | Calls | Cost | Avg Latency | Failures |")
            lines.append("|:---|:---:|:---:|:---:|:---:|")
            for name, summary in self.pipeline_summaries.items():
                lines.append(
                    f"| {name} | {summary.get('calls', 0)} | "
                    f"${summary.get('total_cost_usd', 0):.4f} | "
                    f"{summary.get('avg_latency_ms', 0):.0f}ms | "
                    f"{summary.get('failures', 0)} |"
                )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Meta Optimizer
# ---------------------------------------------------------------------------

# Thresholds for optimization suggestions
_TEMPLATE_MIN_OCCURRENCES = 5
_TEMPLATE_MIN_COST = 0.01  # $0.01 minimum total cost to suggest conversion
_HIGH_FAILURE_RATE = 0.3  # 30%+ failure rate triggers alert
_LOW_COST_THRESHOLD = 0.001  # stages costing < $0.001/call are low priority


class MetaOptimizer:
    """AWO-inspired meta-optimization engine.

    Analyzes workflow traces to generate actionable optimization suggestions.
    All analysis is offline (no LLM calls) — purely data-driven.

    Workflow:
    1. Collect traces via WorkflowTracer (happens during pipeline execution)
    2. Run MetaOptimizer.generate_report() periodically (weekly/on-demand)
    3. Review suggestions and implement high-priority ones
    4. Repeat — the optimizer learns from reduced costs over time
    """

    def __init__(self, tracer: WorkflowTracer | None = None) -> None:
        self._tracer = tracer

    def _get_tracer(self) -> WorkflowTracer:
        """Lazy initialization of tracer."""
        if self._tracer is None:
            from shared.telemetry.workflow_trace import WorkflowTracer

            self._tracer = WorkflowTracer()
        return self._tracer

    def generate_report(self, *, days: int = 7) -> OptimizationReport:
        """Generate a full optimization report from trace data.

        Args:
            days: Number of days to analyze

        Returns:
            OptimizationReport with suggestions, summaries, and patterns
        """
        tracer = self._get_tracer()
        report = OptimizationReport(analysis_period_days=days)

        # 1. Find repeated patterns
        patterns = tracer.find_repeated_patterns(min_count=_TEMPLATE_MIN_OCCURRENCES, days=days)
        report.repeated_patterns = [
            {
                "hash": p.prompt_hash,
                "count": p.occurrence_count,
                "total_cost": p.total_cost_usd,
                "pipelines": p.pipelines,
            }
            for p in patterns
        ]

        # 2. Generate template conversion suggestions
        for pattern in patterns:
            if pattern.total_cost_usd >= _TEMPLATE_MIN_COST:
                suggestion = self._suggest_template_conversion(pattern)
                report.suggestions.append(suggestion)

        # 3. Analyze pipelines for per-stage insights
        known_pipelines = set()
        for pattern in patterns:
            known_pipelines.update(pattern.pipelines)

        for pipeline in known_pipelines:
            stages = tracer.get_stage_summary(pipeline, days=days)
            if stages:
                total_calls = sum(s["calls"] for s in stages)
                total_cost = sum(s["total_cost_usd"] for s in stages)
                total_failures = sum(s["failures"] for s in stages)

                report.pipeline_summaries[pipeline] = {
                    "calls": total_calls,
                    "total_cost_usd": round(total_cost, 4),
                    "avg_latency_ms": round(
                        sum(s["avg_latency_ms"] * s["calls"] for s in stages) / max(total_calls, 1),
                        1,
                    ),
                    "failures": total_failures,
                    "stages": stages,
                }
                report.total_traces_analyzed += total_calls
                report.total_cost_usd += total_cost

                # Check for high-failure stages
                for stage in stages:
                    if stage["calls"] > 0:
                        failure_rate = stage["failures"] / stage["calls"]
                        if failure_rate >= _HIGH_FAILURE_RATE:
                            report.suggestions.append(
                                OptimizationSuggestion(
                                    type=OptimizationType.TIER_DOWNGRADE,
                                    priority="high",
                                    pipeline=pipeline,
                                    stage=stage["stage"],
                                    description=f"{pipeline}/{stage['stage']} 실패율 {failure_rate:.0%}",
                                    confidence=0.9,
                                    action=f"모델/티어 변경 또는 프롬프트 개선 필요. "
                                    f"현재 {stage['failures']}/{stage['calls']} 실패.",
                                )
                            )

        # 4. Sort suggestions by priority and estimated savings
        priority_order = {"high": 0, "medium": 1, "low": 2}
        report.suggestions.sort(
            key=lambda s: (priority_order.get(s.priority, 3), -s.estimated_savings_usd)
        )

        log.info(
            "MetaOptimizer: %d traces, %d patterns, %d suggestions, savings=$%.4f",
            report.total_traces_analyzed,
            len(report.repeated_patterns),
            len(report.suggestions),
            report.total_estimated_savings,
        )

        return report

    def suggest_optimizations(self, *, days: int = 7) -> list[OptimizationSuggestion]:
        """Shortcut: generate report and return just the suggestions."""
        return self.generate_report(days=days).suggestions

    def save_report(
        self,
        report: OptimizationReport,
        output_dir: Path | None = None,
    ) -> Path:
        """Save report as both JSON and Markdown files."""
        if output_dir is None:
            output_dir = Path(__file__).resolve().parent.parent / "telemetry" / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

        # JSON report
        json_path = output_dir / f"optimization_report_{timestamp}.json"
        json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Markdown report
        md_path = output_dir / f"optimization_report_{timestamp}.md"
        md_path.write_text(report.to_markdown(), encoding="utf-8")

        log.info("Saved optimization report to %s", output_dir)
        return md_path

    # -- Suggestion generators ---------------------------------------------

    @staticmethod
    def _suggest_template_conversion(pattern: PromptPattern) -> OptimizationSuggestion:
        """Generate a template conversion suggestion for a repeated pattern."""
        # Estimate savings: if converted to template, all LLM calls are eliminated
        # Savings = total cost of the pattern
        savings = pattern.total_cost_usd

        # Priority based on cost impact
        if savings >= 0.10:
            priority = "high"
        elif savings >= 0.01:
            priority = "medium"
        else:
            priority = "low"

        pipelines_str = ", ".join(pattern.pipelines)
        stages_str = ", ".join(pattern.stages)

        return OptimizationSuggestion(
            type=OptimizationType.TEMPLATE_CONVERSION,
            priority=priority,
            pipeline=pipelines_str,
            stage=stages_str,
            description=(
                f"프롬프트 해시 {pattern.prompt_hash}가 {pattern.occurrence_count}회 반복. "
                f"하드코딩 템플릿으로 전환 시 LLM 호출 완전 제거 가능."
            ),
            estimated_savings_usd=savings,
            estimated_token_savings=int(
                pattern.avg_input_tokens * pattern.occurrence_count
            ),
            prompt_hash=pattern.prompt_hash,
            confidence=min(0.5 + pattern.occurrence_count * 0.05, 0.95),
            action=(
                f"1) trace DB에서 해시 {pattern.prompt_hash}의 원본 프롬프트 확인\n"
                f"2) 동일 출력 패턴이면 Python dict/string 템플릿으로 교체\n"
                f"3) 파이프라인 {pipelines_str}의 {stages_str} 단계에 적용"
            ),
        )
