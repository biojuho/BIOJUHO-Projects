"""
DORA Metrics 수집 스크립트 (v2.0)
Git 로그 기반으로 4가지 DORA 메트릭을 계산합니다.

DORA Metrics:
  1. Deployment Frequency (배포 빈도)
  2. Lead Time for Changes (변경 리드 타임)
  3. Change Failure Rate (변경 실패율) — fix 커밋 비율
  4. Mean Time to Restore (평균 복구 시간) ← v2.0 신규

v2.0 추가:
  - --by-project: 프로젝트별 분리 리포트
  - MTTR (Mean Time to Restore) 메트릭
  - 주간 트렌드 ASCII 차트

사용법:
    python scripts/dora_metrics.py
    python scripts/dora_metrics.py --days 30
    python scripts/dora_metrics.py --by-project
    python scripts/dora_metrics.py --json-out dora-report.json
"""

import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]

# 프로젝트 경로 매핑
PROJECT_PATHS = {
    "getdaytrends": "getdaytrends/",
    "desci-backend": "desci-platform/biolinker/",
    "desci-frontend": "desci-platform/frontend/",
    "desci-contracts": "desci-platform/contracts/",
    "AgriGuard-backend": "AgriGuard/backend/",
    "AgriGuard-frontend": "AgriGuard/frontend/",
    "DailyNews": "DailyNews/",
    "canva-mcp": "canva-mcp/",
    "shared": "shared/",
    "scripts": "scripts/",
}

FIX_KEYWORDS = ["fix", "hotfix", "bugfix", "patch", "revert", "수정", "버그", "오류"]


def get_git_log(days: int = 30) -> list[dict]:
    """최근 N일 커밋 로그를 가져옵니다 (변경 파일 포함)."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--format=%H|%aI|%s", "--no-merges", "--name-only"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=WORKSPACE, timeout=30,
        )
        commits = []
        current = None
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                if current:
                    commits.append(current)
                    current = None
                continue
            if "|" in line and len(line.split("|", maxsplit=2)) >= 3:
                parts = line.split("|", maxsplit=2)
                current = {
                    "hash": parts[0][:8],
                    "date": parts[1],
                    "message": parts[2],
                    "files": [],
                }
            elif current:
                current["files"].append(line.strip())

        if current:
            commits.append(current)
        return commits
    except Exception as e:
        print(f"⚠️ Git 로그 읽기 실패: {e}")
        return []


def get_merge_commits(days: int = 30) -> list[dict]:
    """최근 N일 머지 커밋 (배포 프록시)."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--merges", "--format=%H|%aI|%s"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=WORKSPACE, timeout=30,
        )
        merges = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("|", maxsplit=2)
            if len(parts) >= 3:
                merges.append({
                    "hash": parts[0][:8],
                    "date": parts[1],
                    "message": parts[2],
                })
        return merges
    except Exception:
        return []


def classify_commit_project(commit: dict) -> str:
    """커밋의 변경 파일을 기반으로 프로젝트 식별."""
    for proj_name, path_prefix in PROJECT_PATHS.items():
        for f in commit.get("files", []):
            if f.startswith(path_prefix):
                return proj_name
    # 커밋 메시지에서 [ProjectName] 패턴 추출
    match = re.match(r"\[([^\]]+)\]", commit.get("message", ""))
    if match:
        tag = match.group(1).lower()
        for proj_name in PROJECT_PATHS:
            if tag in proj_name.lower():
                return proj_name
    return "workspace"


def calc_deployment_frequency(commits: list[dict], days: int) -> dict:
    """배포 빈도: 일 평균 커밋 수."""
    total = len(commits)
    freq = total / max(days, 1)
    if freq >= 1:
        level = "Elite"
    elif freq >= 0.14:
        level = "High"
    elif freq >= 0.03:
        level = "Medium"
    else:
        level = "Low"
    return {
        "total_commits": total,
        "daily_avg": round(freq, 2),
        "period_days": days,
        "level": level,
    }


def calc_lead_time(commits: list[dict]) -> dict:
    """리드 타임: 커밋 간 평균 간격 (시간)."""
    if len(commits) < 2:
        return {"avg_hours": 0, "level": "N/A"}

    dates = []
    for c in commits:
        try:
            dt = datetime.fromisoformat(c["date"])
            dates.append(dt)
        except (ValueError, KeyError):
            continue

    if len(dates) < 2:
        return {"avg_hours": 0, "level": "N/A"}

    dates.sort()
    gaps = [(dates[i] - dates[i - 1]).total_seconds() / 3600 for i in range(1, len(dates))]
    avg = sum(gaps) / len(gaps)

    if avg < 24:
        level = "Elite"
    elif avg < 168:
        level = "High"
    elif avg < 720:
        level = "Medium"
    else:
        level = "Low"

    return {"avg_hours": round(avg, 1), "level": level}


def count_fix_commits(commits: list[dict]) -> dict:
    """변경 실패율: fix/hotfix/bugfix 커밋 비율."""
    fixes = [c for c in commits if any(k in c["message"].lower() for k in FIX_KEYWORDS)]
    total = len(commits)
    rate = (len(fixes) / total * 100) if total > 0 else 0

    if rate <= 15:
        level = "Elite"
    elif rate <= 30:
        level = "High"
    elif rate <= 45:
        level = "Medium"
    else:
        level = "Low"

    return {
        "total_commits": total,
        "fix_commits": len(fixes),
        "failure_rate_pct": round(rate, 1),
        "level": level,
    }


def calc_mttr(commits: list[dict]) -> dict:
    """Mean Time to Restore: fix 커밋과 직전 커밋 사이 시간차 평균."""
    if len(commits) < 2:
        return {"avg_hours": 0, "level": "N/A", "fix_count": 0}

    # 날짜순 정렬
    sorted_commits = sorted(commits, key=lambda c: c.get("date", ""))
    restore_times = []

    for i, commit in enumerate(sorted_commits):
        is_fix = any(k in commit["message"].lower() for k in FIX_KEYWORDS)
        if is_fix and i > 0:
            try:
                fix_dt = datetime.fromisoformat(commit["date"])
                prev_dt = datetime.fromisoformat(sorted_commits[i - 1]["date"])
                gap_hours = (fix_dt - prev_dt).total_seconds() / 3600
                if gap_hours >= 0:
                    restore_times.append(gap_hours)
            except (ValueError, KeyError):
                continue

    if not restore_times:
        return {"avg_hours": 0, "level": "N/A", "fix_count": 0}

    avg = sum(restore_times) / len(restore_times)
    if avg < 1:
        level = "Elite"
    elif avg < 24:
        level = "High"
    elif avg < 168:
        level = "Medium"
    else:
        level = "Low"

    return {
        "avg_hours": round(avg, 1),
        "fix_count": len(restore_times),
        "level": level,
    }


def generate_weekly_trend(commits: list[dict], days: int) -> list[dict]:
    """주간 커밋 트렌드 데이터."""
    weeks = defaultdict(int)
    for c in commits:
        try:
            dt = datetime.fromisoformat(c["date"])
            week_key = dt.strftime("%m/%d")
            weeks[week_key] += 1
        except (ValueError, KeyError):
            continue

    # 최근 주 기준 정렬
    today = datetime.now()
    trend = []
    for i in range(min(days, 28), -1, -1):
        day = today - timedelta(days=i)
        key = day.strftime("%m/%d")
        trend.append({"date": key, "commits": weeks.get(key, 0)})
    return trend


def generate_ascii_chart(trend: list[dict], width: int = 40) -> str:
    """간단한 ASCII 바 차트."""
    if not trend:
        return "  (데이터 없음)"

    max_val = max(t["commits"] for t in trend) or 1
    lines = []

    # 7일 단위로 그룹핑
    grouped = []
    for i in range(0, len(trend), 7):
        chunk = trend[i:i + 7]
        total = sum(t["commits"] for t in chunk)
        label = chunk[0]["date"]
        grouped.append({"label": label, "total": total})

    max_group = max(g["total"] for g in grouped) or 1
    for g in grouped:
        bar_len = int(g["total"] / max_group * width)
        bar = "█" * bar_len
        lines.append(f"  {g['label']} │{bar} {g['total']}")

    return "\n".join(lines)


def generate_report(days: int = 30, by_project: bool = False) -> dict:
    """DORA 메트릭 리포트 생성."""
    commits = get_git_log(days)
    merges = get_merge_commits(days)
    trend = generate_weekly_trend(commits, days)

    report = {
        "timestamp": datetime.now().isoformat(),
        "version": "2.0",
        "period_days": days,
        "total_commits": len(commits),
        "total_merges": len(merges),
        "metrics": {
            "deployment_frequency": calc_deployment_frequency(commits, days),
            "lead_time_for_changes": calc_lead_time(commits),
            "change_failure_rate": count_fix_commits(commits),
            "mean_time_to_restore": calc_mttr(commits),
        },
        "weekly_trend": trend,
    }

    if by_project:
        project_commits = defaultdict(list)
        for c in commits:
            proj = classify_commit_project(c)
            project_commits[proj].append(c)

        report["by_project"] = {}
        for proj_name, proj_commits_list in sorted(project_commits.items()):
            report["by_project"][proj_name] = {
                "total_commits": len(proj_commits_list),
                "deployment_frequency": calc_deployment_frequency(proj_commits_list, days),
                "change_failure_rate": count_fix_commits(proj_commits_list),
                "mttr": calc_mttr(proj_commits_list),
            }

    return report


def format_report(report: dict) -> str:
    """콘솔 출력."""
    lines = []
    lines.append("=" * 55)
    lines.append(f"📊 DORA Metrics Report v{report.get('version', '1.0')} — last {report['period_days']} days")
    lines.append("=" * 55)
    lines.append(f"총 커밋: {report['total_commits']} / 머지: {report['total_merges']}")

    m = report["metrics"]

    df = m["deployment_frequency"]
    lines.append(f"\n🚀 Deployment Frequency: {df['daily_avg']}/day [{df['level']}]")

    lt = m["lead_time_for_changes"]
    lines.append(f"⏱️ Lead Time: {lt['avg_hours']}h avg [{lt['level']}]")

    cfr = m["change_failure_rate"]
    lines.append(f"🔥 Change Failure Rate: {cfr['failure_rate_pct']}% [{cfr['level']}]")

    mttr = m["mean_time_to_restore"]
    lines.append(f"🔧 Mean Time to Restore: {mttr['avg_hours']}h avg ({mttr.get('fix_count', 0)} fixes) [{mttr['level']}]")

    # 주간 트렌드
    if report.get("weekly_trend"):
        lines.append("\n📈 Weekly Trend:")
        lines.append(generate_ascii_chart(report["weekly_trend"]))

    lines.append("\n" + "=" * 55)

    # 종합 레벨
    levels = [df["level"], lt["level"], cfr["level"], mttr["level"]]
    level_map = {"Elite": 4, "High": 3, "Medium": 2, "Low": 1, "N/A": 0}
    valid_levels = [l for l in levels if l != "N/A"]
    avg_score = sum(level_map.get(l, 0) for l in valid_levels) / max(len(valid_levels), 1)
    if avg_score >= 3.5:
        overall = "🏆 Elite"
    elif avg_score >= 2.5:
        overall = "⭐ High"
    elif avg_score >= 1.5:
        overall = "📈 Medium"
    else:
        overall = "📉 Low"
    lines.append(f"Overall DORA Level: {overall}")

    # 프로젝트별 리포트
    if report.get("by_project"):
        lines.append("\n" + "─" * 55)
        lines.append("📁 프로젝트별 분리 리포트:")
        lines.append("─" * 55)
        for proj_name, proj_data in report["by_project"].items():
            pf = proj_data["deployment_frequency"]
            pcfr = proj_data["change_failure_rate"]
            pmttr = proj_data.get("mttr", {})
            lines.append(
                f"  {proj_name:25s} │ "
                f"{proj_data['total_commits']:3d} commits │ "
                f"{pf['daily_avg']}/day [{pf['level']:6s}] │ "
                f"fail {pcfr['failure_rate_pct']}%"
            )

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="DORA Metrics v2")
    parser.add_argument("--days", type=int, default=30, help="분석 기간 (일)")
    parser.add_argument("--by-project", action="store_true", help="프로젝트별 분리 리포트")
    parser.add_argument("--json-out", help="JSON 리포트 출력 경로")
    args = parser.parse_args()

    report = generate_report(args.days, by_project=args.by_project)
    print(format_report(report))

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n📄 리포트 저장: {args.json_out}")


if __name__ == "__main__":
    main()
