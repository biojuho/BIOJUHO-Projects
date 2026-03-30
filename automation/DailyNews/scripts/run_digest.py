"""Generate and manage Digest summaries from DailyNews reports.

Usage:
    python scripts/run_digest.py [--action run|master|status]
"""

import argparse
import asyncio
import logging
import sys
from datetime import date

sys.path.insert(0, r"D:\AI project\DailyNews\src")
sys.path.insert(0, r"D:\AI project\packages")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def run_digest():
    """Generate a digest from pending queue."""
    from antigravity_mcp.config import get_settings
    from antigravity_mcp.integrations.digest_adapter import DigestAdapter
    from antigravity_mcp.state.store import PipelineStateStore

    settings = get_settings()
    state_store = PipelineStateStore(settings.pipeline_state_db)
    digest = DigestAdapter(state_store=state_store)

    if not digest.is_available():
        print("[ERROR] DigestAdapter not available (LLM client missing)")
        return

    # Get pending queue
    pending = state_store.get_digest_queue(status="pending")
    if not pending:
        print("No pending reports in digest queue")
        return

    print(f"{'=' * 60}")
    print(f"Digest Generation — {date.today().isoformat()}")
    print(f"Pending entries: {len(pending)}")
    print(f"{'=' * 60}\n")

    for entry in pending:
        print(f"Processing digest {entry.digest_id} ({len(entry.report_ids)} reports)")

        # Load report data
        reports_data = []
        for rid in entry.report_ids:
            report = state_store.get_report(rid)
            if report:
                reports_data.append(
                    {
                        "report_id": report.report_id,
                        "category": report.category,
                        "summary_lines": report.summary_lines,
                        "insights": report.insights,
                    }
                )

        if not reports_data:
            print("  ⚠️ No valid reports found, skipping")
            continue

        result = await digest.generate_digest(reports_data)
        print(f"  ✅ Summary: {result.get('summary', '')[:100]}...")
        print(f"  Themes: {result.get('key_themes', '')}")
        print(f"  Outlook: {result.get('outlook', '')}")
        print()


async def run_master():
    """Generate DigestMaster from all generated digests."""
    from antigravity_mcp.config import get_settings
    from antigravity_mcp.integrations.digest_adapter import DigestAdapter
    from antigravity_mcp.state.store import PipelineStateStore

    settings = get_settings()
    state_store = PipelineStateStore(settings.pipeline_state_db)
    digest = DigestAdapter(state_store=state_store)

    if not digest.is_available():
        print("[ERROR] DigestAdapter not available")
        return

    generated = state_store.get_digest_queue(status="generated")
    if not generated:
        print("No generated digests to merge")
        return

    digests_data = [{"serial_number": d.serial_number, "summary_text": d.summary_text} for d in generated]

    print(f"Merging {len(digests_data)} digests into DigestMaster...")
    master = await digest.generate_digest_master(digests_data)
    if master:
        output = settings.output_dir / f"digest_master_{date.today().isoformat()}.md"
        output.write_text(master, encoding="utf-8")
        print(f"✅ DigestMaster saved: {output}")
        print(f"Length: {len(master)} chars")
    else:
        print("❌ DigestMaster generation failed")


async def show_status():
    """Show current digest queue status."""
    from antigravity_mcp.config import get_settings
    from antigravity_mcp.state.store import PipelineStateStore

    settings = get_settings()
    state_store = PipelineStateStore(settings.pipeline_state_db)

    for status in ["pending", "generated", "pinned"]:
        entries = state_store.get_digest_queue(status=status)
        print(f"[{status.upper()}] {len(entries)} entries")
        for e in entries[:3]:
            print(f"  {e.digest_id}: {len(e.report_ids)} reports | {e.serial_number or 'no serial'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DailyNews Digest Manager")
    parser.add_argument("--action", default="run", choices=["run", "master", "status"])
    args = parser.parse_args()

    if args.action == "run":
        asyncio.run(run_digest())
    elif args.action == "master":
        asyncio.run(run_master())
    elif args.action == "status":
        asyncio.run(show_status())
