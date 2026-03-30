"""
LLM Cache 분석 스크립트

LLM API 호출 캐시 히트율을 분석하여 비용 절감 및 성능 최적화 기회를 식별합니다.

Usage:
    python scripts/analyze_llm_cache.py [--days 7]
"""

import argparse
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "pipeline_state.db"


def analyze_cache_stats(days: int = 7):
    """캐시 통계 분석"""
    print("=" * 80)
    print(" " * 25 + "LLM Cache Analysis Report")
    print("=" * 80)
    print(f"Period: Last {days} days")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 전체 캐시 통계
    print("[ Overall Cache Statistics ]".ljust(80, "-"))
    cursor.execute("SELECT COUNT(*) FROM llm_cache")
    total_entries = cursor.fetchone()[0]
    print(f"  Total Cache Entries: {total_entries:,}")

    if total_entries == 0:
        print("  No cache data available yet.")
        conn.close()
        return

    # 기간별 통계
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

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

    unique, queries = cursor.fetchone() or (0, 0)

    if queries == 0:
        print(f"  No queries in the last {days} days.")
        conn.close()
        return

    # 캐시 히트율 계산
    cache_hits = queries - unique
    hit_rate = (cache_hits / queries * 100) if queries > 0 else 0

    print(f"  Unique Prompts (Last {days} Days): {unique:,}")
    print(f"  Total Queries (Last {days} Days): {queries:,}")
    print(f"  Cache Hits: {cache_hits:,}")
    print(f"  Cache Hit Rate: {hit_rate:.1f}%")
    print()

    # 캐시 효율성 평가
    print("[ Cache Efficiency ]".ljust(80, "-"))
    if hit_rate >= 60:
        efficiency = "Excellent"
        emoji = "[+++]"
    elif hit_rate >= 40:
        efficiency = "Good"
        emoji = "[++]"
    elif hit_rate >= 20:
        efficiency = "Fair"
        emoji = "[+]"
    else:
        efficiency = "Poor"
        emoji = "[-]"

    print(f"  Efficiency Rating: {emoji} {efficiency}")
    print()

    # 비용 절감 추정
    print("[ Cost Savings Estimate ]".ljust(80, "-"))

    # 가정: Gemini API 평균 비용 $0.01 per 1K tokens, 평균 500 tokens per request
    avg_tokens_per_request = 500
    cost_per_1k_tokens = 0.01
    cost_per_request = (avg_tokens_per_request / 1000) * cost_per_1k_tokens

    total_cost_without_cache = queries * cost_per_request
    total_cost_with_cache = unique * cost_per_request
    savings = total_cost_without_cache - total_cost_with_cache
    savings_pct = (savings / total_cost_without_cache * 100) if total_cost_without_cache > 0 else 0

    print(f"  API Calls Saved: {cache_hits:,}")
    print(f"  Estimated Cost Without Cache: ${total_cost_without_cache:.2f}")
    print(f"  Actual Cost With Cache: ${total_cost_with_cache:.2f}")
    print(f"  Estimated Savings: ${savings:.2f} ({savings_pct:.1f}%)")
    print()

    # 월간 추정 (7일 데이터 기반)
    if days == 7:
        monthly_queries = queries * 4.3  # 약 4.3주/월
        monthly_unique = unique * 4.3
        monthly_savings = savings * 4.3

        print("[ Monthly Projection (based on 7-day average) ]".ljust(80, "-"))
        print(f"  Projected Monthly Queries: {monthly_queries:,.0f}")
        print(f"  Projected Monthly Savings: ${monthly_savings:.2f}")
        print()

    # 가장 많이 사용된 프롬프트 (상위 10개)
    print("[ Most Frequent Prompts (Top 10) ]".ljust(80, "-"))

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

    # 권장 사항
    print("[ Recommendations ]".ljust(80, "-"))

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
    print("=" * 80)

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Analyze LLM cache statistics")
    parser.add_argument("--days", type=int, default=7, help="Number of days to analyze (default: 7)")
    args = parser.parse_args()

    analyze_cache_stats(days=args.days)


if __name__ == "__main__":
    main()
