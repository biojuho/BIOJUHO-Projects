"""Cross-project pipeline orchestrator.

Coordinates GetDayTrends, Content Intelligence, DailyNews publishing, and
performance tracking steps from one CLI.

Usage::
    python scripts/orchestrator.py --dry-run
    python scripts/orchestrator.py --execute
    python scripts/orchestrator.py --status
    python scripts/orchestrator.py --steps collect,generate
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from workspace_paths import find_workspace_root, rel_unit_path, unit_path

if TYPE_CHECKING:
    from pathlib import Path

WORKSPACE = find_workspace_root()


@dataclass
class StepResult:
    name: str
    status: str = "pending"
    started_at: str = ""
    finished_at: str = ""
    duration_sec: float = 0.0
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class PipelineRun:
    run_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    steps: list[StepResult] = field(default_factory=list)
    dry_run: bool = False
    total_cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "dry_run": self.dry_run,
            "total_cost": self.total_cost,
            "steps": [
                {
                    "name": step.name,
                    "status": step.status,
                    "duration_sec": step.duration_sec,
                    "error": step.error,
                }
                for step in self.steps
            ],
        }

    def summary(self) -> str:
        lines = [
            f"Pipeline Run: {self.run_id}",
            f"Mode: {'DRY-RUN' if self.dry_run else 'EXECUTE'}",
            f"Started: {self.started_at}",
            f"Finished: {self.finished_at}",
            f"Total Cost: ${self.total_cost:.4f}",
            "",
            "Steps:",
        ]
        for step in self.steps:
            icon = {
                "success": "[OK]",
                "failed": "[FAIL]",
                "skipped": "[SKIP]",
                "running": "[...]",
                "pending": "[ ]",
            }.get(step.status, "[ ]")
            duration = f" ({step.duration_sec:.1f}s)" if step.duration_sec > 0 else ""
            error = f" - {step.error}" if step.error else ""
            lines.append(f"  {icon} {step.name}{duration}{error}")
        return "\n".join(lines)


PIPELINE_STEPS = [
    "collect",
    "validate",
    "generate",
    "publish",
    "track",
]


def _prepend_sys_path(path: Path) -> None:
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)


def _check_budget() -> tuple[bool, float]:
    """Return whether the current daily cost is within budget."""
    try:
        from shared.telemetry.cost_tracker import get_daily_cost_summary

        summary = get_daily_cost_summary(days=1)
        current = summary.get("total_cost", 0.0)
        budget = 3.0
        with suppress(Exception):
            _prepend_sys_path(unit_path("getdaytrends"))
            from config import AppConfig

            cfg = AppConfig.from_env()
            budget = cfg.daily_budget_usd
        return current < budget, current
    except Exception:
        return True, 0.0


def _notify(message: str) -> None:
    """Send a best-effort notification if channels are configured."""
    with suppress(Exception):
        from shared.notifications.notifier import Notifier

        notifier = Notifier.from_env()
        if notifier.has_channels:
            notifier.send(message)


def step_collect(dry_run: bool) -> StepResult:
    """Step 1: collect GetDayTrends inputs."""
    result = StepResult(name="collect")
    if dry_run:
        result.status = "success"
        result.output = {"trends_count": 0, "message": "DRY-RUN: collect simulate"}
        return result
    try:
        _prepend_sys_path(unit_path("getdaytrends"))
        main_mod = importlib.import_module("main")
        if hasattr(main_mod, "collect_trends_sync"):
            trends = main_mod.collect_trends_sync()
            result.output = {"trends_count": len(trends) if trends else 0}
        else:
            result.output = {"message": "collect_trends_sync not found, using scraper directly"}
        result.status = "success"
    except Exception as exc:
        result.status = "failed"
        result.error = str(exc)
    return result


def step_validate(dry_run: bool) -> StepResult:
    """Step 2: run Content Intelligence validation if available."""
    result = StepResult(name="validate")
    if dry_run:
        result.status = "success"
        result.output = {"message": "DRY-RUN: validate simulate"}
        return result
    try:
        cie_path = unit_path("content-intelligence")
        if cie_path.exists():
            _prepend_sys_path(cie_path)
            try:
                importlib.import_module("regulators.checklist")
                result.output = {"message": "validation checklist loaded"}
            except ImportError:
                result.output = {"message": "validation checklist unavailable"}
            result.status = "success"
        else:
            result.status = "skipped"
            result.output = {"message": "content-intelligence missing"}
    except Exception as exc:
        result.status = "failed"
        result.error = str(exc)
    return result


def step_generate(dry_run: bool) -> StepResult:
    """Step 3: generate content."""
    result = StepResult(name="generate")
    if dry_run:
        result.status = "success"
        result.output = {"message": "DRY-RUN: generate simulate"}
        return result
    result.status = "skipped"
    result.output = {"message": "generate step missing"}
    return result


def step_publish(dry_run: bool) -> StepResult:
    """Step 4: publish content."""
    result = StepResult(name="publish")
    if dry_run:
        result.status = "success"
        result.output = {"message": "DRY-RUN: publish simulate"}
        return result
    result.status = "skipped"
    result.output = {"message": "publish auto_post missing"}
    return result


def step_track(dry_run: bool) -> StepResult:
    """Step 5: track performance."""
    result = StepResult(name="track")
    if dry_run:
        result.status = "success"
        result.output = {"message": "DRY-RUN: track simulate"}
        return result
    try:
        tracker_path = unit_path("getdaytrends") / "performance_tracker.py"
        if tracker_path.exists():
            result.output = {"message": "PerformanceTracker available"}
        else:
            result.output = {"message": "PerformanceTracker missing; skipping"}
        result.status = "success"
    except Exception as exc:
        result.status = "failed"
        result.error = str(exc)
    return result


STEP_FUNCTIONS = {
    "collect": step_collect,
    "validate": step_validate,
    "generate": step_generate,
    "publish": step_publish,
    "track": step_track,
}


def run_pipeline(
    steps: list[str] | None = None,
    dry_run: bool = True,
) -> PipelineRun:
    """Run the configured pipeline steps."""
    now = datetime.now(UTC)
    run = PipelineRun(
        run_id=now.strftime("%Y%m%d_%H%M%S"),
        started_at=now.isoformat(),
        dry_run=dry_run,
    )

    target_steps = steps or PIPELINE_STEPS
    within_budget, current_cost = _check_budget()
    run.total_cost = current_cost
    if not within_budget and not dry_run:
        _notify("[!] Pipeline blocked: daily cost budget exceeded")
        for step_name in target_steps:
            run.steps.append(StepResult(name=step_name, status="skipped", error="daily cost budget exceeded"))
        run.finished_at = datetime.now(UTC).isoformat()
        return run

    for step_name in target_steps:
        if step_name not in STEP_FUNCTIONS:
            run.steps.append(StepResult(name=step_name, status="skipped", error="unknown pipeline step"))
            continue

        step_func = STEP_FUNCTIONS[step_name]
        step_start = time.time()
        started_at = datetime.now(UTC).isoformat()

        result = step_func(dry_run)
        result.started_at = started_at
        result.duration_sec = round(time.time() - step_start, 2)
        result.finished_at = datetime.now(UTC).isoformat()
        run.steps.append(result)

        if result.status == "failed":
            _notify(f"[!] Pipeline step failed: {step_name} - {result.error}")
            for remaining in target_steps[target_steps.index(step_name) + 1 :]:
                run.steps.append(StepResult(name=remaining, status="skipped", error="previous step failed"))
            break

    run.finished_at = datetime.now(UTC).isoformat()

    success_count = sum(1 for step in run.steps if step.status == "success")
    total = len(run.steps)
    mode = "DRY-RUN" if dry_run else "EXECUTE"
    _notify(f"[OK] Pipeline completed ({mode}): {success_count}/{total} steps succeeded")

    return run


def show_status() -> None:
    """Print current orchestrator status."""
    print("=== Orchestrator Status ===\n")

    within, cost = _check_budget()
    budget_icon = "[OK]" if within else "[!]"
    print(f"{budget_icon} Daily cost: ${cost:.4f}")

    projects = {
        "GetDayTrends": WORKSPACE / rel_unit_path("getdaytrends", "main.py"),
        "Content-Intelligence": WORKSPACE / rel_unit_path("content-intelligence", "main.py"),
        "DailyNews": WORKSPACE / rel_unit_path("dailynews", "src"),
        "Performance Tracker": WORKSPACE / rel_unit_path("getdaytrends", "performance_tracker.py"),
        "Firecrawl Client": WORKSPACE / rel_unit_path("getdaytrends", "firecrawl_client.py"),
    }
    print("\nComponents:")
    for name, path in projects.items():
        exists = "[OK]" if path.exists() else "[--]"
        print(f"  {exists} {name}")

    channels = []
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        channels.append("Telegram")
    if os.getenv("DISCORD_WEBHOOK_URL"):
        channels.append("Discord")
    if os.getenv("SENTRY_DSN"):
        channels.append("Sentry")
    print(f"\nNotification channels: {', '.join(channels) or 'None configured'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-project Pipeline Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Simulate pipeline execution")
    parser.add_argument("--execute", action="store_true", help="Run the pipeline")
    parser.add_argument("--steps", type=str, help="Comma-separated steps, e.g. collect,generate,publish")
    parser.add_argument("--status", action="store_true", help="Show orchestrator status")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    dry_run = not args.execute
    steps = args.steps.split(",") if args.steps else None

    run = run_pipeline(steps=steps, dry_run=dry_run)

    if args.json:
        print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(run.summary())


if __name__ == "__main__":
    main()
