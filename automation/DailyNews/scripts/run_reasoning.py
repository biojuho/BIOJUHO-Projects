"""Run inductive reasoning on recent DailyNews reports.

Usage:
    python scripts/run_reasoning.py [--category Tech] [--reports 3]
"""
import asyncio
import argparse
import json
import logging
import sys
from datetime import date

sys.path.insert(0, r"D:\AI project\DailyNews\src")
sys.path.insert(0, r"D:\AI project\packages")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main(category: str = "Tech", max_reports: int = 3):
    from antigravity_mcp.state.store import PipelineStateStore
    from antigravity_mcp.config import get_settings
    from antigravity_mcp.integrations.reasoning_adapter import ReasoningAdapter

    settings = get_settings()
    state_store = PipelineStateStore(settings.pipeline_state_db)
    reasoner = ReasoningAdapter(state_store=state_store)

    if not reasoner.is_available():
        print("[ERROR] ReasoningAdapter not available (LLM client missing)")
        return

    print(f"{'=' * 60}")
    print(f"Inductive Reasoning Pipeline — {date.today().isoformat()}")
    print(f"Category: {category} | Max reports: {max_reports}")
    print(f"{'=' * 60}\n")

    # Get recent reports
    with state_store._connect() as conn:
        rows = conn.execute(
            """
            SELECT report_id, category, summary_json, insights_json
            FROM content_reports
            WHERE category = ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (category, max_reports),
        ).fetchall()

    if not rows:
        print(f"No reports found for category '{category}'")
        return

    print(f"Found {len(rows)} report(s) to process\n")

    # Process each report
    for row in rows:
        report_id = row["report_id"]
        summaries = json.loads(row["summary_json"] or "[]")
        insights = json.loads(row["insights_json"] or "[]")
        content_text = "\n".join(summaries + insights)

        print(f"{'─' * 40}")
        print(f"Report: {report_id}")
        print(f"{'─' * 40}")

        result = await reasoner.run_full_reasoning(
            report_id=report_id,
            category=category,
            content_text=content_text,
            source_title=f"{category} report",
        )

        facts = result.get("facts", [])
        hyps = result.get("hypotheses", [])
        survived = result.get("survived_count", 0)
        patterns = result.get("new_patterns", [])

        print(f"  Step 1: {len(facts)} fact(s) extracted")
        print(f"  Step 2: {len(hyps)} hypothesis(es) generated")
        print(f"  Step 3: {survived}/{len(hyps)} survived falsification")
        if patterns:
            print(f"  New patterns:")
            for p in patterns:
                print(f"    → {p[:80]}...")
        print()

    # Show accumulated patterns
    all_patterns = state_store.get_active_patterns(category)
    if all_patterns:
        print(f"\n{'=' * 60}")
        print(f"Accumulated Patterns for '{category}' ({len(all_patterns)} total)")
        print(f"{'=' * 60}")
        for p in all_patterns:
            strength = "🟢" if p["strength"] == "strong" else "🟡"
            print(f"  {strength} [{p['survival_count']}x] {p['pattern_text'][:80]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run inductive reasoning on DailyNews reports")
    parser.add_argument("--category", default="Tech", help="Category to analyze")
    parser.add_argument("--reports", type=int, default=3, help="Max reports to process")
    args = parser.parse_args()
    asyncio.run(main(category=args.category, max_reports=args.reports))
