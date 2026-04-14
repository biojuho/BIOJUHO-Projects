"""
DailyNews 모니터링 대시보드

간단한 CLI 기반 대시보드로 파이프라인 상태를 실시간 모니터링합니다.

Usage:
    python scripts/monitoring_dashboard.py
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def clear_screen():
    """화면 클리어 (크로스 플랫폼)"""
    import os

    os.system("cls" if os.name == "nt" else "clear")


def print_header():
    """대시보드 헤더 출력"""
    print("=" * 80)
    print(" " * 25 + "DailyNews Monitoring Dashboard")
    print("=" * 80)
    print(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()


def get_pipeline_stats(days: int = 7) -> dict[str, int]:
    """파이프라인 실행 통계"""
    db_path = PROJECT_ROOT / "data" / "pipeline_state.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute(
        """
        SELECT status, COUNT(*) as count
        FROM job_runs
        WHERE started_at >= ?
        GROUP BY status
    """,
        (cutoff_date,),
    )

    stats = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    return stats


def get_recent_runs(limit: int = 10) -> list[tuple]:
    """최근 실행 목록"""
    db_path = PROJECT_ROOT / "data" / "pipeline_state.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT run_id, job_name, status, started_at, finished_at
        FROM job_runs
        ORDER BY started_at DESC
        LIMIT ?
    """,
        (limit,),
    )

    runs = cursor.fetchall()
    conn.close()

    return runs


def get_insight_logs() -> list[dict]:
    """Insight 로그 파일 목록"""
    log_dir = PROJECT_ROOT / "logs" / "insights"

    if not log_dir.exists():
        return []

    logs = []
    for log_file in sorted(log_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True):
        logs.append(
            {
                "name": log_file.name,
                "size": log_file.stat().st_size,
                "modified": datetime.fromtimestamp(log_file.stat().st_mtime),
            }
        )

    return logs[:5]  # 최근 5개만


def get_database_stats() -> dict:
    """데이터베이스 통계"""
    db_path = PROJECT_ROOT / "data" / "pipeline_state.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {}

    # Job runs
    cursor.execute("SELECT COUNT(*) FROM job_runs")
    stats["total_runs"] = cursor.fetchone()[0]

    # Content reports
    cursor.execute("SELECT COUNT(*) FROM content_reports")
    stats["total_reports"] = cursor.fetchone()[0]

    # Article cache
    cursor.execute("SELECT COUNT(*) FROM article_cache")
    stats["cached_articles"] = cursor.fetchone()[0]

    # LLM cache
    cursor.execute("SELECT COUNT(*) FROM llm_cache")
    stats["llm_cache_entries"] = cursor.fetchone()[0]

    # DB size
    stats["db_size_kb"] = db_path.stat().st_size / 1024

    conn.close()

    return stats


def print_section(title: str):
    """섹션 헤더 출력"""
    print()
    print(f"[ {title} ]".ljust(80, "-"))


def print_pipeline_stats():
    """파이프라인 통계 출력"""
    print_section("Pipeline Statistics (Last 7 Days)")

    stats = get_pipeline_stats(days=7)
    total = sum(stats.values())

    if total == 0:
        print("  No runs in the last 7 days.")
        return

    # 성공률 계산
    success_count = stats.get("success", 0)
    success_rate = (success_count / total * 100) if total > 0 else 0

    print(f"  Total Runs: {total}")
    print(f"  Success Rate: {success_rate:.1f}% ({success_count}/{total})")
    print()
    print("  Status Distribution:")

    # 상태별 출력
    status_order = ["success", "partial", "running", "skipped", "failed"]
    for status in status_order:
        count = stats.get(status, 0)
        if count > 0:
            pct = count / total * 100
            bar_length = int(pct / 2)  # 50% = 25 chars
            bar = "#" * bar_length  # ASCII-safe for Windows console
            print(f"    {status:10s}: {count:3d} ({pct:5.1f}%) {bar}")


def print_recent_runs():
    """최근 실행 목록 출력"""
    print_section("Recent Runs (Last 10)")

    runs = get_recent_runs(limit=10)

    if not runs:
        print("  No runs found.")
        return

    # 헤더
    print(f"  {'Run ID':<35s} | {'Job':<20s} | {'Status':<8s} | {'Started':<19s}")
    print("  " + "-" * 78)

    # 실행 목록
    for run_id, job_name, status, started_at, finished_at in runs:
        run_id_short = run_id[:32] + "..." if len(run_id) > 35 else run_id
        job_name_short = job_name[:17] + "..." if len(job_name) > 20 else job_name
        started_short = started_at[:19] if started_at else "N/A"

        # 상태 표시 (ASCII-safe for Windows console)
        status_display = status
        if status == "success":
            status_display = "[OK]" + status[4:]
        elif status == "failed":
            status_display = "[X]" + status[4:]
        elif status == "degraded":
            status_display = "[!]" + status[8:]

        print(f"  {run_id_short:<35s} | {job_name_short:<20s} | {status_display:<12s} | {started_short:<19s}")


def print_insight_logs():
    """Insight 로그 파일 출력"""
    print_section("Insight Generation Logs (Latest 5)")

    logs = get_insight_logs()

    if not logs:
        print("  No insight logs found yet.")
        print("  (Logs will appear after first scheduled run)")
        return

    # 헤더
    print(f"  {'File Name':<40s} | {'Size':<10s} | {'Modified':<19s}")
    print("  " + "-" * 78)

    for log in logs:
        size_str = f"{log['size'] / 1024:.1f} KB"
        modified_str = log["modified"].strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {log['name']:<40s} | {size_str:<10s} | {modified_str:<19s}")


def print_database_stats():
    """데이터베이스 통계 출력"""
    print_section("Database Statistics")

    stats = get_database_stats()

    print(f"  Total Runs:        {stats['total_runs']:,}")
    print(f"  Content Reports:   {stats['total_reports']:,}")
    print(f"  Cached Articles:   {stats['cached_articles']:,}")
    print(f"  LLM Cache Entries: {stats['llm_cache_entries']:,}")
    print(f"  Database Size:     {stats['db_size_kb']:.1f} KB")


def print_scheduled_tasks():
    """스케줄된 작업 상태 (Windows)"""
    print_section("Scheduled Tasks (Windows)")

    try:
        import subprocess

        result = subprocess.run(
            [
                "powershell",
                "-Command",
                'Get-ScheduledTask | Where-Object {$_.TaskName -match "DailyNews"} | '
                "Select-Object TaskName,State | Format-Table -HideTableHeaders",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0 and result.stdout.strip():
            lines = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            if lines:
                print(f"  {'Task Name':<35s} | {'State':<10s}")
                print("  " + "-" * 47)
                for line in lines:
                    print(f"  {line}")
            else:
                print("  No DailyNews tasks found.")
                print("  Run: scripts\\setup_scheduled_tasks.ps1")
        else:
            print("  Unable to query scheduled tasks.")
    except Exception as e:
        print(f"  Error checking tasks: {e}")


def main():
    """메인 대시보드"""
    clear_screen()
    print_header()

    try:
        print_pipeline_stats()
        print_recent_runs()
        print_insight_logs()
        print_database_stats()
        print_scheduled_tasks()

        print()
        print("=" * 80)
        print("Press Ctrl+C to exit | Refresh: python scripts/monitoring_dashboard.py")
        print("=" * 80)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
