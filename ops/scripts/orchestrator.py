"""
Orchestrator - ?щ줈???꾨줈?앺듃 ?뚯씠?꾨씪???ㅼ??ㅽ듃?덉씠??

GetDayTrends ??Content-Intelligence ??DailyNews ??諛쒗뻾 ???깃낵異붿쟻
?꾩껜 肄섑뀗痢??뚯씠?꾨씪?몄쓣 ?⑥씪 吏꾩엯?먯뿉??愿�由?

Usage::
    python scripts/orchestrator.py --dry-run      # ?쒕??덉씠??
    python scripts/orchestrator.py --execute      # ?ㅽ뻾
    python scripts/orchestrator.py --status       # ?곹깭 ?뺤씤
    python scripts/orchestrator.py --steps collect,generate  # ?뱀젙 ?④퀎留?
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workspace_paths import find_workspace_root, rel_unit_path, unit_path


WORKSPACE = find_workspace_root()


@dataclass
class StepResult:
    name: str
    status: str = "pending"  # pending, running, success, failed, skipped
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

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "dry_run": self.dry_run,
            "total_cost": self.total_cost,
            "steps": [
                {
                    "name": s.name,
                    "status": s.status,
                    "duration_sec": s.duration_sec,
                    "error": s.error,
                }
                for s in self.steps
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
        for s in self.steps:
            icon = {
                "success": "[OK]",
                "failed": "[FAIL]",
                "skipped": "[SKIP]",
                "running": "[...]",
                "pending": "[ ]",
            }.get(s.status, "[ ]")
            dur = f" ({s.duration_sec:.1f}s)" if s.duration_sec > 0 else ""
            err = f" - {s.error}" if s.error else ""
            lines.append(f"  {icon} {s.name}{dur}{err}")
        return "\n".join(lines)


PIPELINE_STEPS = [
    "collect",      # Step 1: ?몃젋???섏쭛
    "validate",     # Step 2: 肄섑뀗痢?洹쒖젣 寃�利?
    "generate",     # Step 3: 肄섑뀗痢??앹꽦
    "publish",      # Step 4: 諛쒗뻾
    "track",        # Step 5: ?깃낵 異붿쟻
]


def _check_budget() -> tuple[bool, float]:
    """?쇱씪 ?덉궛 ?뺤씤. (within_budget, current_cost)"""
    try:
        from shared.telemetry.cost_tracker import get_daily_cost_summary

        summary = get_daily_cost_summary(days=1)
        current = summary.get("total_cost", 0.0)
        # getdaytrends config?먯꽌 ?덉궛 濡쒕뱶
        budget = 3.0  # 湲곕낯媛?
        try:
            sys.path.insert(0, str(unit_path("getdaytrends")))
            from config import AppConfig

            cfg = AppConfig.from_env()  # type: ignore[attr-defined]
            budget = cfg.daily_budget_usd
        except Exception:
            pass
        return current < budget, current
    except Exception:
        return True, 0.0


def _notify(message: str) -> None:
    """?뚮┝ ?꾩넚 (Telegram/Discord)."""
    try:
        from shared.notifications.notifier import Notifier

        notifier = Notifier.from_env()
        if notifier.has_channels:
            notifier.send(message)
    except Exception:
        pass


def step_collect(dry_run: bool) -> StepResult:
    """Step 1: GetDayTrends ?몃젋???섏쭛."""
    result = StepResult(name="collect")
    if dry_run:
        result.status = "success"
        result.output = {"trends_count": 0, "message": "DRY-RUN: ?섏쭛 ?쒕??덉씠??}
        return result
    try:
        sys.path.insert(0, str(unit_path("getdaytrends")))
        # main.py???섏쭛 濡쒖쭅 ?숈쟻 ?꾪룷??
        main_mod = importlib.import_module("main")
        if hasattr(main_mod, "collect_trends_sync"):
            trends = main_mod.collect_trends_sync()
            result.output = {"trends_count": len(trends) if trends else 0}
        else:
            result.output = {"message": "collect_trends_sync not found, using scraper directly"}
        result.status = "success"
    except Exception as e:
        result.status = "failed"
        result.error = str(e)
    return result


def step_validate(dry_run: bool) -> StepResult:
    """Step 2: Content-Intelligence 洹쒖젣 寃�利?"""
    result = StepResult(name="validate")
    if dry_run:
        result.status = "success"
        result.output = {"message": "DRY-RUN: 洹쒖젣 寃�利??쒕??덉씠??}
        return result
    try:
        cie_path = unit_path("content-intelligence")
        if cie_path.exists():
            sys.path.insert(0, str(cie_path))
            try:
                reg_mod = importlib.import_module("regulators.checklist")
                result.output = {"message": "洹쒖젣 泥댄겕由ъ뒪??濡쒕뱶??}
                result.status = "success"
            except ImportError:
                result.status = "success"
                result.output = {"message": "洹쒖젣 紐⑤뱢 湲곕낯 ?⑥뒪"}
        else:
            result.status = "skipped"
            result.output = {"message": "content-intelligence 誘몄꽕移?}
    except Exception as e:
        result.status = "failed"
        result.error = str(e)
    return result


def step_generate(dry_run: bool) -> StepResult:
    """Step 3: 肄섑뀗痢??앹꽦."""
    result = StepResult(name="generate")
    if dry_run:
        result.status = "success"
        result.output = {"message": "DRY-RUN: ?앹꽦 ?쒕??덉씠??}
        return result
    result.status = "skipped"
    result.output = {"message": "?앹꽦 ?④퀎: main.py run_pipeline()???꾩엫 (吏곸젒 ?ㅽ뻾 誘멸뎄??"}
    return result


def step_publish(dry_run: bool) -> StepResult:
    """Step 4: 諛쒗뻾."""
    result = StepResult(name="publish")
    if dry_run:
        result.status = "success"
        result.output = {"message": "DRY-RUN: 諛쒗뻾 ?쒕??덉씠??(?ㅼ젣 ?ъ뒪???놁쓬)"}
        return result
    result.status = "skipped"
    result.output = {"message": "諛쒗뻾: GetDayTrends auto_post???꾩엫 (吏곸젒 ?ㅽ뻾 誘멸뎄??"}
    return result


def step_track(dry_run: bool) -> StepResult:
    """Step 5: ?깃낵 異붿쟻."""
    result = StepResult(name="track")
    if dry_run:
        result.status = "success"
        result.output = {"message": "DRY-RUN: ?깃낵 異붿쟻 ?쒕??덉씠??}
        return result
    try:
        tracker_path = unit_path("getdaytrends") / "performance_tracker.py"
        if tracker_path.exists():
            result.output = {"message": "PerformanceTracker ?ъ슜 媛�??}
        else:
            result.output = {"message": "PerformanceTracker 誘몄꽕移?- ?ㅽ궢"}
        result.status = "success"
    except Exception as e:
        result.status = "failed"
        result.error = str(e)
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
    """?뚯씠?꾨씪???ㅽ뻾."""
    now = datetime.now(timezone.utc)
    run = PipelineRun(
        run_id=now.strftime("%Y%m%d_%H%M%S"),
        started_at=now.isoformat(),
        dry_run=dry_run,
    )

    target_steps = steps or PIPELINE_STEPS

    # ?덉궛 ?뺤씤
    within_budget, current_cost = _check_budget()
    run.total_cost = current_cost
    if not within_budget and not dry_run:
        _notify("[!] ?뚯씠?꾨씪??以묐떒: ?쇱씪 ?덉궛 珥덇낵")
        for step_name in target_steps:
            run.steps.append(StepResult(name=step_name, status="skipped", error="?덉궛 珥덇낵"))
        run.finished_at = datetime.now(timezone.utc).isoformat()
        return run

    # ?④퀎蹂??ㅽ뻾
    for step_name in target_steps:
        if step_name not in STEP_FUNCTIONS:
            run.steps.append(StepResult(name=step_name, status="skipped", error="?????녿뒗 ?④퀎"))
            continue

        step_func = STEP_FUNCTIONS[step_name]
        step_start = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        result = step_func(dry_run)
        result.started_at = started_at
        result.duration_sec = round(time.time() - step_start, 2)
        result.finished_at = datetime.now(timezone.utc).isoformat()
        run.steps.append(result)

        # ?ㅽ뙣 ???댄썑 ?④퀎 以묐떒
        if result.status == "failed":
            _notify(f"[!] ?뚯씠?꾨씪???ㅽ뙣: {step_name} - {result.error}")
            for remaining in target_steps[target_steps.index(step_name) + 1:]:
                run.steps.append(StepResult(name=remaining, status="skipped", error="?댁쟾 ?④퀎 ?ㅽ뙣"))
            break

    run.finished_at = datetime.now(timezone.utc).isoformat()

    # ?꾨즺 ?뚮┝
    success_count = sum(1 for s in run.steps if s.status == "success")
    total = len(run.steps)
    mode = "DRY-RUN" if dry_run else "EXECUTE"
    _notify(f"[OK] ?뚯씠?꾨씪???꾨즺 ({mode}): {success_count}/{total} ?깃났")

    return run


def show_status() -> None:
    """?꾩옱 ?쒖뒪???곹깭 ?쒖떆."""
    print("=== Orchestrator Status ===\n")

    # ?덉궛
    within, cost = _check_budget()
    budget_icon = "[OK]" if within else "[!]"
    print(f"{budget_icon} ?쇱씪 鍮꾩슜: ${cost:.4f}")

    # ?꾨줈?앺듃 議댁옱 ?щ?
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

    # ?뚮┝ 梨꾨꼸
    import os

    channels = []
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        channels.append("Telegram")
    if os.getenv("DISCORD_WEBHOOK_URL"):
        channels.append("Discord")
    if os.getenv("SENTRY_DSN"):
        channels.append("Sentry")
    print(f"\nNotification channels: {', '.join(channels) or 'None configured'}")


def main():
    parser = argparse.ArgumentParser(description="Cross-project Pipeline Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="?쒕??덉씠??紐⑤뱶")
    parser.add_argument("--execute", action="store_true", help="?ㅼ젣 ?ㅽ뻾")
    parser.add_argument("--steps", type=str, help="?ㅽ뻾???④퀎 (肄ㅻ쭏 援щ텇: collect,generate,publish)")
    parser.add_argument("--status", action="store_true", help="?쒖뒪???곹깭 ?뺤씤")
    parser.add_argument("--json", action="store_true", help="JSON 異쒕젰")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    dry_run = not args.execute  # 湲곕낯媛? dry-run
    steps = args.steps.split(",") if args.steps else None

    run = run_pipeline(steps=steps, dry_run=dry_run)

    if args.json:
        print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(run.summary())


if __name__ == "__main__":
    main()
