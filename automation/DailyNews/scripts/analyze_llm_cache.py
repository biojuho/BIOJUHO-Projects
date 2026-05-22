"""
LLM Cache analysis script.

Analyzes LLM API call cache hit rate to estimate cost savings and optimization opportunities.

Usage:
    python scripts/analyze_llm_cache.py [--days 7]
"""

import argparse
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "pipeline_state.db"
REPORT_WIDTH = 80
AVG_TOKENS_PER_REQUEST = 500
COST_PER_1K_TOKENS = 0.01


def _print_report_header(days: int) -> None:
    print("=" * REPORT_WIDTH)
    print(" " * 25 + "LLM Cache Analysis Report")
    print("=" * REPORT_WIDTH)
    print(f"Period: Last {days} days")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * REPORT_WIDTH)
    print()


def _print_section(title: str) -> None:
    print(f"[ {title} ]".ljust(REPORT_WIDTH, "-"))


def _load_window_stats(cursor: sqlite3.Cursor, cutoff: str) -> tuple[int, int]:
    cursor.execute(
        """
        SELECT
            COUNT(DISTINCT prompt_hash) as unique_prompts,
            COUNT(*) as total_queries
        FROM llm_cache
        WHERE created_at >= ?
    """,
        (cutoff,),
    )
    return cursor.fetchone() or (0, 0)


def _calculate_costs(unique: int, queries: int) -> tuple[int, float, float, float, float]:
    cache_hits = queries - unique
    cost_per_request = (AVG_TOKENS_PER_REQUEST / 1000) * COST_PER_1K_TOKENS
    total_cost_without_cache = queries * cost_per_request
    total_cost_with_cache = unique * cost_per_request
    savings = total_cost_without_cache - total_cost_with_cache
    savings_pct = (savings / total_cost_without_cache * 100) if total_cost_without_cache > 0 else 0
    return cache_hits, total_cost_without_cache, total_cost_with_cache, savings, savings_pct


def _efficiency_label(hit_rate: float) -> tuple[str, str]:
    if hit_rate >= 60:
        return "Excellent", "[+++]"
    if hit_rate >= 40:
        return "Good", "[++]"
    if hit_rate >= 20:
        return "Fair", "[+]"
    return "Poor", "[-]"


def _print_efficiency(hit_rate: float) -> None:
    _print_section("Cache Efficiency")
    efficiency, emoji = _efficiency_label(hit_rate)
    print(f"  Efficiency Rating: {emoji} {efficiency}")
    print()


def _print_cost_savings(unique: int, queries: int) -> float:
    _print_section("Cost Savings Estimate")
    cache_hits, total_without_cache, total_with_cache, savings, savings_pct = _calculate_costs(unique, queries)

    print(f"  API Calls Saved: {cache_hits:,}")
    print(f"  Estimated Cost Without Cache: ${total_without_cache:.2f}")
    print(f"  Actual Cost With Cache: ${total_with_cache:.2f}")
    print(f"  Estimated Savings: ${savings:.2f} ({savings_pct:.1f}%)")
    print()
    return savings


def _print_monthly_projection(days: int, queries: int, savings: float) -> None:
    if days != 7:
        return

    monthly_queries = queries * 4.3
    monthly_savings = savings * 4.3

    _print_section("Monthly Projection (based on 7-day average)")
    print(f"  Projected Monthly Queries: {monthly_queries:,.0f}")
    print(f"  Projected Monthly Savings: ${monthly_savings:.2f}")
    print()


def _print_frequent_prompts(cursor: sqlite3.Cursor, cutoff: str) -> None:
    _print_section("Most Frequent Prompts (Top 10)")

    cursor.execute(
        """
        SELECT
            prompt_hash,
            COUNT(*) as usage_count,
            MAX(created_at) as last_used
        FROM llm_cache
        WHERE created_at >= ?
        GROUP BY prompt_hash
        ORDER BY usage_count DESC
        LIMIT 10
    """,
        (cutoff,),
    )

    frequent_prompts = cursor.fetchall()

    if frequent_prompts:
        print(f"  {'Hash':<20s} | {'Usage Count':<12s} | {'Last Used':<19s}")
        print("  " + "-" * 75)
        for prompt_hash, count, last_used in frequent_prompts:
            hash_short = prompt_hash[:17] + "..." if len(prompt_hash) > 20 else prompt_hash
            last_used_short = last_used[:19] if last_used else "N/A"
            print(f"  {hash_short:<20s} | {count:<12d} | {last_used_short:<19s}")
    else:
        print("  No data available.")

    print()


def _print_recommendations(hit_rate: float) -> None:
    _print_section("Recommendations")

    if hit_rate < 40:
        print("  [!] Cache hit rate is below 40%.")
        print("      - Consider increasing cache TTL")
        print("      - Review prompt templates for consistency")
        print("      - Implement cache warming for common queries")
    elif hit_rate < 60:
        print("  [~] Cache hit rate is moderate (40-60%).")
        print("      - Good baseline, room for improvement")
        print("      - Monitor cache TTL effectiveness")
    else:
        print("  [+] Cache hit rate is excellent (60%+).")
        print("      - Current caching strategy is working well")
        print("      - Maintain current cache TTL settings")

    print()
    print("=" * REPORT_WIDTH)


def analyze_cache_stats(days: int = 7):
    """Analyze cache statistics."""
    _print_report_header(days)

    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()

        _print_section("Overall Cache Statistics")
        cursor.execute("SELECT COUNT(*) FROM llm_cache")
        total_entries = cursor.fetchone()[0]
        print(f"  Total Cache Entries: {total_entries:,}")

        if total_entries == 0:
            print("  No cache data available yet.")
            return

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        unique, queries = _load_window_stats(cursor, cutoff)

        if queries == 0:
            print(f"  No queries in the last {days} days.")
            return

        cache_hits = queries - unique
        hit_rate = (cache_hits / queries * 100) if queries > 0 else 0

        print(f"  Unique Prompts (Last {days} Days): {unique:,}")
        print(f"  Total Queries (Last {days} Days): {queries:,}")
        print(f"  Cache Hits: {cache_hits:,}")
        print(f"  Cache Hit Rate: {hit_rate:.1f}%")
        print()

        _print_efficiency(hit_rate)
        savings = _print_cost_savings(unique, queries)
        _print_monthly_projection(days, queries, savings)
        _print_frequent_prompts(cursor, cutoff)
        _print_recommendations(hit_rate)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Analyze LLM cache statistics")
    parser.add_argument("--days", type=int, default=7, help="Number of days to analyze (default: 7)")
    args = parser.parse_args()

    analyze_cache_stats(days=args.days)


if __name__ == "__main__":
    main()
