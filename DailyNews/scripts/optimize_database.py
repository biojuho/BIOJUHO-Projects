"""
데이터베이스 최적화 스크립트

SQLite 데이터베이스에 인덱스를 추가하고 VACUUM을 실행합니다.

Usage:
    python scripts/optimize_database.py
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "pipeline_state.db"


def optimize_database():
    """데이터베이스 최적화"""
    print("=" * 80)
    print(" " * 25 + "Database Optimization")
    print("=" * 80)
    print()

    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. 인덱스 추가
        print("[ Step 1/3 ] Creating indexes...".ljust(80, "-"))

        indexes = [
            ("idx_job_runs_started_at", "job_runs", "started_at DESC"),
            ("idx_job_runs_status", "job_runs", "status"),
            ("idx_job_runs_job_name", "job_runs", "job_name"),
            ("idx_article_cache_link", "article_cache", "link"),
            ("idx_article_cache_collected_at", "article_cache", "collected_at DESC"),
            ("idx_llm_cache_prompt_hash", "llm_cache", "prompt_hash"),
            ("idx_llm_cache_created_at", "llm_cache", "created_at DESC"),
            ("idx_content_reports_category", "content_reports", "category"),
            ("idx_content_reports_created_at", "content_reports", "created_at DESC"),
        ]

        created_count = 0
        for idx_name, table, column in indexes:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
                created_count += 1
                print(f"  [OK] {idx_name}")
            except sqlite3.Error as e:
                print(f"  [SKIP] {idx_name}: {e}")

        print(f"  Created/verified {created_count} indexes.")
        print()

        # 2. VACUUM 실행
        print("[ Step 2/3 ] Running VACUUM...".ljust(80, "-"))

        db_size_before = DB_PATH.stat().st_size / 1024  # KB

        cursor.execute("VACUUM")
        conn.commit()

        db_size_after = DB_PATH.stat().st_size / 1024  # KB
        size_diff = db_size_before - db_size_after
        size_diff_pct = (size_diff / db_size_before * 100) if db_size_before > 0 else 0

        print(f"  Database size before: {db_size_before:.1f} KB")
        print(f"  Database size after:  {db_size_after:.1f} KB")
        print(f"  Space reclaimed: {size_diff:.1f} KB ({size_diff_pct:.1f}%)")
        print()

        # 3. 분석 실행
        print("[ Step 3/3 ] Running ANALYZE...".ljust(80, "-"))

        cursor.execute("ANALYZE")
        conn.commit()

        print("  Query optimizer statistics updated.")
        print()

        # 결과 요약
        print("[ Summary ]".ljust(80, "-"))
        print("  [+] All optimization steps completed successfully")
        print("  [+] Database is now optimized for faster queries")
        print()

        # 권장 사항
        print("[ Recommendations ]".ljust(80, "-"))
        print("  - Run this script monthly to maintain performance")
        print("  - Monitor query times after optimization")
        print("  - Consider archiving old data if database grows > 10 MB")
        print()

        print("=" * 80)

        return 0

    except sqlite3.Error as e:
        print(f"Error during optimization: {e}")
        return 1

    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(optimize_database())
