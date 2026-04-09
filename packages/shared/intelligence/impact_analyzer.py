"""shared.intelligence.impact_analyzer — Change Impact Analysis Engine.

High-level API that combines CodeGraphStore with git diff detection
to answer: "이 변경이 시스템 어디에 영향을 주는가?"

Integrates with:
  - shared.harness.RiskScanner: impact-based risk scoring
  - shared.harness.TokenBudget: suggest minimal detail for high-impact changes
  - Pipeline QA: feed impact data into finalize_quality()

Usage::

    from shared.intelligence.impact_analyzer import ImpactAnalyzer

    analyzer = ImpactAnalyzer("d:/AI project")
    report = await analyzer.analyze_changes(["shared/harness/core.py"])
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .code_graph import CodeGraphStore, ImpactResult

logger = logging.getLogger(__name__)


@dataclass
class ChangeReport:
    """Comprehensive change impact report."""

    changed_files: list[str]
    impact: ImpactResult | None = None
    risk_level: str = "low"  # low | medium | high | critical
    risk_score: float = 0.0
    affected_modules: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    graph_stats: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """One-line summary for logging/audit."""
        return (
            f"[{self.risk_level.upper()}] {len(self.changed_files)} file(s) changed, "
            f"{self.impact.total_nodes if self.impact else 0} node(s) impacted, "
            f"risk={self.risk_score:.2f}"
        )


def _classify_risk(score: float) -> str:
    """Classify numeric risk score into level."""
    if score >= 0.8:
        return "critical"
    if score >= 0.5:
        return "high"
    if score >= 0.2:
        return "medium"
    return "low"


def _generate_recommendations(
    report: ChangeReport,
    impact: ImpactResult,
) -> list[str]:
    """Generate actionable recommendations based on impact analysis."""
    recs: list[str] = []

    if report.risk_level == "critical":
        recs.append("⚠️ CRITICAL: This change affects 80%+ of the dependency graph. Full regression test required.")
        recs.append("Consider breaking this into smaller, incremental changes.")
    elif report.risk_level == "high":
        recs.append("🔴 HIGH IMPACT: Run targeted tests for affected modules before merging.")

    # Depth-based recommendations
    deep_nodes = [n for n in impact.impacted_nodes if n.get("depth", 0) >= 3]
    if deep_nodes:
        recs.append(
            f"📊 {len(deep_nodes)} node(s) impacted at depth ≥3 — cascading effects detected."
        )

    # Module diversity
    affected_files = {n["file_path"] for n in impact.impacted_nodes}
    if len(affected_files) > 5:
        recs.append(
            f"📁 Impact spans {len(affected_files)} files across multiple modules. "
            f"Consider cross-module integration tests."
        )

    if not recs:
        recs.append("✅ Low-impact change. Standard review process is sufficient.")

    return recs


class ImpactAnalyzer:
    """High-level change impact analysis API.

    Combines code graph indexing with git-aware change detection
    to produce actionable impact reports.
    """

    def __init__(
        self,
        repo_root: str | Path,
        *,
        db_path: str | Path | None = None,
        max_depth: int = 5,
        auto_index: bool = True,
    ):
        self._repo_root = Path(repo_root).resolve()
        self._db_path = db_path
        self._max_depth = max_depth
        self._auto_index = auto_index

    async def analyze_changes(
        self,
        changed_files: list[str] | None = None,
        *,
        max_depth: int | None = None,
    ) -> ChangeReport:
        """Analyze impact of changed files.

        Args:
            changed_files: List of relative file paths. If None, auto-detect via git.
            max_depth: Override max BFS depth.

        Returns:
            ChangeReport with risk classification and recommendations.
        """
        report = ChangeReport(changed_files=changed_files or [])

        # Auto-detect changes from git if not provided
        if not report.changed_files:
            report.changed_files = self._detect_git_changes()
            if not report.changed_files:
                report.recommendations.append("No changes detected in git working tree.")
                return report

        try:
            async with CodeGraphStore(
                self._repo_root,
                db_path=self._db_path,
                max_depth=max_depth or self._max_depth,
            ) as graph:
                # Auto-index changed files if needed
                if self._auto_index:
                    for f in report.changed_files:
                        if f.endswith(".py"):
                            await graph.index_file(f)

                # Run impact BFS
                report.impact = await graph.get_impact_radius(
                    report.changed_files, max_depth=max_depth,
                )
                report.risk_score = report.impact.risk_score
                report.risk_level = _classify_risk(report.risk_score)

                # Identify affected modules
                affected_files = {
                    n["file_path"]
                    for n in report.impact.impacted_nodes
                }
                report.affected_modules = sorted(
                    {f.split("/")[0] for f in affected_files if "/" in f}
                )

                # Generate recommendations
                report.recommendations = _generate_recommendations(report, report.impact)

                # Graph stats for diagnostics
                report.graph_stats = await graph.get_stats()

        except Exception as exc:
            logger.error("Impact analysis failed: %s", exc)
            report.errors.append(f"Analysis error: {type(exc).__name__}: {exc}")
            report.recommendations.append("⚠️ Impact analysis failed. Manual review recommended.")

        return report

    def _detect_git_changes(self) -> list[str]:
        """Detect changed files via git diff (staged + unstaged)."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=str(self._repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return []
            files = [
                f.strip().replace("\\", "/")
                for f in result.stdout.strip().splitlines()
                if f.strip()
            ]
            return files
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
