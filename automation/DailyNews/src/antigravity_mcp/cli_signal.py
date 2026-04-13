"""CLI subcommands for Signal Watch.

Usage:
  antigravity-mcp signal watch [--threshold 0.6] [--country KR]
  antigravity-mcp signal history [--last 24] [--min-score 0.3]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

logger = logging.getLogger(__name__)


def register_signal_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register 'signal' subcommand group."""
    signal_parser = subparsers.add_parser("signal", help="Real-time signal arbitrage commands")
    signal_sub = signal_parser.add_subparsers(dest="signal_command", required=True)

    # signal watch
    watch = signal_sub.add_parser("watch", help="Run one signal watch cycle")
    watch.add_argument("--threshold", type=float, default=0.6, help="Minimum composite score (default: 0.6)")
    watch.add_argument("--country", default="KR", help="Country for Google Trends (default: KR)")
    watch.add_argument("--categories", nargs="*", default=None, help="Target categories for scoring")
    watch.add_argument("--auto-draft", action="store_true", help="Auto-generate drafts for top signals")
    watch.add_argument("--limit", type=int, default=20, help="Max signals per source")
    watch.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    # signal history
    history = signal_sub.add_parser("history", help="View recent signal history")
    history.add_argument("--last", type=int, default=24, help="Hours to look back (default: 24)")
    history.add_argument("--min-score", type=float, default=0.0, help="Minimum score filter")
    history.add_argument("--limit", type=int, default=30, help="Max results")
    history.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")


def dispatch_signal_command(args: argparse.Namespace) -> int:
    """Dispatch signal subcommands."""
    if args.signal_command == "watch":
        return asyncio.run(_run_watch(args))
    if args.signal_command == "history":
        return _run_history(args)
    return 1


async def _run_watch(args: argparse.Namespace) -> int:
    """Execute a signal watch cycle."""
    from antigravity_mcp.pipelines.signal_watch import run_signal_watch

    # Lazy-load Notifier (fail-safe)
    try:
        from shared.notifications import Notifier
        notifier = Notifier.from_env()
    except Exception as exc:
        logger.debug("Notifier disabled or failed to load: %s", exc)
        notifier = None

    try:
        result = await run_signal_watch(
            threshold=args.threshold,
            auto_draft=getattr(args, "auto_draft", False),
            categories=args.categories,
            country=args.country,
            limit_per_source=args.limit,
        )
    except Exception as exc:
        logger.error("Signal watch cycle failed: %s", exc)
        print(f"❌ Error during signal watch: {exc}")
        if notifier:
            try:
                notifier.send_error("Signal watch cycle failed", error=exc)
            except Exception as notify_exc:
                logger.debug("Notifier send_error failed: %s", notify_exc)
        return 1

    if getattr(args, "json_output", False):
        sys.stdout.buffer.write((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
    else:
        _print_watch_result(result)

    if result.get("status") == "ok":
        if notifier:
            try:
                # Silent heartbeat for Grafana/metrics
                notifier.send_heartbeat("signal_watch")
                # Daily visibility message for chat (only if actionable signals were found)
                actionable_count = result.get("actionable", 0)
                if actionable_count > 0:
                    notifier.send(f"📡 *Signal Watch*\n탐지된 유효 트렌드: {actionable_count} 건")
            except Exception as notify_exc:
                logger.debug("Notifier send failed: %s", notify_exc)
        return 0

    return 1


def _print_watch_result(result: dict) -> None:
    """Pretty-print signal watch results."""
    print(f"{'='*60}")
    print("  Signal Watch Results")
    print(f"{'='*60}")
    print(f"  Sources:    {', '.join(result.get('sources', []))}")
    print(f"  Collected:  {result.get('total_collected', 0)}")
    print(f"  Scored:     {result.get('total_scored', 0)}")
    print(f"  Actionable: {result.get('actionable', 0)}")
    print(f"  Elapsed:    {result.get('elapsed_sec', 0):.1f}s")
    print(f"{'─'*60}")

    signals = result.get("signals", [])
    if not signals:
        print("  No actionable signals detected.")
    else:
        for _i, s in enumerate(signals, 1):
            icon = {"draft_now": "🔴", "differentiate": "🟡", "series": "🟢", "skip": "⚪"}.get(s["action"], "⚪")
            print(
                f"  {icon} [{s['score']:.2f}] {s['keyword']}"
                f"  ({s['type']}, {s['source_count']} sources)"
            )
            print(f"       Action: {s['action']} | Velocity: {s['velocity']:.2f}")
            if s.get("category"):
                print(f"       Category: {s['category']}")

    print(f"{'='*60}\n")


def _run_history(args: argparse.Namespace) -> int:
    """Show recent signal history."""
    from antigravity_mcp.pipelines.signal_watch import SignalStateStore

    store = SignalStateStore()
    records = store.get_signal_history(
        hours=args.last,
        min_score=args.min_score,
        limit=args.limit,
    )

    if getattr(args, "json_output", False):
        sys.stdout.buffer.write((json.dumps(records, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
    else:
        _print_history(records, hours=args.last)

    return 0


def _print_history(records: list[dict], *, hours: int = 24) -> None:
    """Pretty-print signal history."""
    print(f"\n{'='*60}")
    print(f"  Signal History (last {hours}h)")
    print(f"{'='*60}")

    if not records:
        print("  No signals found.")
    else:
        for r in records:
            sources = r.get("sources", "[]")
            if isinstance(sources, str):
                sources = json.loads(sources)
            print(
                f"  [{r['composite_score']:.2f}] {r['keyword']}"
                f"  ({r['arbitrage_type']}, {r.get('source_count', 0)} sources)"
            )
            print(f"       Action: {r['recommended_action']} | Detected: {r['detected_at'][:19]}")

    print(f"{'='*60}\n")
