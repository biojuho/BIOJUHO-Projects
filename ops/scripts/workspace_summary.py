"""
Workspace Summary 스크립트 (v1.0)
세션 시작 시 한 번 실행하여 빠른 상태 파악.

기능:
  - Git uncommitted 변경 요약
  - 최신 세션 히스토리 → TODO 추출  
  - 프로젝트별 마지막 커밋 시간 → 방치 프로젝트 알림
  - DORA 점수 원라인 요약

사용법:
    python scripts/workspace_summary.py
    python scripts/workspace_summary.py --no-dora
"""

import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workspace_paths import find_workspace_root, rel_unit_path


WORKSPACE = find_workspace_root()
SESSION_HISTORY_DIR = WORKSPACE / ".agent" / "session-history"

PROJECT_DIRS = [
    rel_unit_path("getdaytrends"),
    rel_unit_path("desci-platform"),
    rel_unit_path("agriguard"),
    rel_unit_path("dailynews"),
    rel_unit_path("canva-mcp"),
    rel_unit_path("shared"),
    rel_unit_path("scripts"),
]

STALE_THRESHOLD_DAYS = 3


def get_git_status() -> dict:
    """Git uncommitted 변경 요약."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, cwd=WORKSPACE, timeout=10
        )
        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]

        # 유형별 분류
        modified = [l for l in lines if l.startswith("M") or l.startswith(" M")]
        added = [l for l in lines if l.startswith("A") or l.startswith("??")]
        deleted = [l for l in lines if l.startswith("D")]

        return {
            "total": len(lines),
            "modified": len(modified),
            "added": len(added),
            "deleted": len(deleted),
            "files": lines[:15],
        }
    except Exception as e:
        return {"error": str(e), "total": 0}


def get_latest_session_todos() -> dict:
    """최신 세션 히스토리에서 TODO 추출."""
    result = {"file": None, "todos": [], "issues": [], "last_session": None}

    if not SESSION_HISTORY_DIR.exists():
        return result

    history_files = sorted(SESSION_HISTORY_DIR.glob("*.md"), reverse=True)
    if not history_files:
        return result

    latest = history_files[0]
    result["file"] = latest.name

    try:
        content = latest.read_text(encoding="utf-8")

        # TODO 추출
        todo_section = False
        for line in content.split("\n"):
            if "다음 TODO" in line or "다음 세션" in line:
                todo_section = True
                continue
            if todo_section:
                if line.startswith("#") or line.startswith("---"):
                    todo_section = False
                    continue
                cleaned = line.strip().lstrip("0123456789.- ")
                if cleaned:
                    result["todos"].append(cleaned)

        # 미완성/버그 이슈 추출
        issue_section = False
        for line in content.split("\n"):
            if "미완성" in line or "버그 이슈" in line:
                issue_section = True
                continue
            if issue_section:
                if line.startswith("#") or line.startswith("---"):
                    issue_section = False
                    continue
                cleaned = line.strip().lstrip("- ")
                if cleaned and cleaned != "없음 (모든 이슈 해결 완료)":
                    result["issues"].append(cleaned)

        # 최근 세션 이름 추출
        for line in content.split("\n"):
            if line.startswith("### 세션") or line.startswith("## 세션"):
                result["last_session"] = line.strip("#").strip()

    except Exception:
        pass

    return result


def get_project_last_commits() -> list[dict]:
    """프로젝트별 마지막 커밋 시간 확인."""
    results = []
    for proj_dir in PROJECT_DIRS:
        full_path = WORKSPACE / proj_dir
        if not full_path.exists():
            continue
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%aI|%s", "--", f"{proj_dir}/"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=WORKSPACE, timeout=10,
            )
            output = result.stdout.strip()
            if "|" in output:
                parts = output.split("|", maxsplit=1)
                dt = datetime.fromisoformat(parts[0])
                age_days = (datetime.now(dt.tzinfo) - dt).days
                results.append({
                    "project": proj_dir,
                    "last_commit": parts[0][:10],
                    "message": parts[1][:60],
                    "age_days": age_days,
                    "stale": age_days > STALE_THRESHOLD_DAYS,
                })
            else:
                results.append({
                    "project": proj_dir,
                    "last_commit": "없음",
                    "message": "",
                    "age_days": 999,
                    "stale": True,
                })
        except Exception:
            pass
    return results


def get_dora_oneliner() -> str:
    """DORA 원라인 요약 (dora_metrics.py 호출)."""
    dora_script = WORKSPACE / "scripts" / "dora_metrics.py"
    if not dora_script.exists():
        return "DORA 스크립트 없음"

    try:
        result = subprocess.run(
            [sys.executable, str(dora_script), "--days", "7"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=WORKSPACE, timeout=30,
        )
        # "Overall DORA Level" 라인 추출
        for line in result.stdout.split("\n"):
            if "Overall DORA Level" in line:
                return line.strip()
        return "DORA 데이터 부족"
    except Exception as e:
        return f"DORA 실행 실패: {e}"


def format_summary(git: dict, todos: dict, projects: list[dict], dora: str) -> str:
    """콘솔 출력 포맷."""
    lines = []
    lines.append("╔" + "═" * 55 + "╗")
    lines.append("║   📋 Workspace Summary — " + datetime.now().strftime("%Y-%m-%d %H:%M") + "        ║")
    lines.append("╚" + "═" * 55 + "╝")

    # Git 상태
    lines.append(f"\n📦 Git: {git['total']} uncommitted change(s)")
    if git["total"] > 0:
        lines.append(f"   수정: {git.get('modified', 0)} / 추가: {git.get('added', 0)} / 삭제: {git.get('deleted', 0)}")
        for f in git.get("files", [])[:5]:
            lines.append(f"   {f}")
        if git["total"] > 5:
            lines.append(f"   ... 외 {git['total'] - 5}개")

    # 이전 세션 TODO
    if todos.get("last_session"):
        lines.append(f"\n📝 마지막 세션: {todos['last_session']}")
    if todos.get("todos"):
        lines.append(f"\n🎯 미완료 TODO ({len(todos['todos'])}개):")
        for i, t in enumerate(todos["todos"][:7], 1):
            lines.append(f"   {i}. {t}")
    if todos.get("issues"):
        lines.append(f"\n⚠️ 미해결 이슈:")
        for issue in todos["issues"][:3]:
            lines.append(f"   • {issue}")

    # 프로젝트 활성도
    stale = [p for p in projects if p["stale"]]
    active = [p for p in projects if not p["stale"]]
    lines.append(f"\n🏗️ 프로젝트 활성도 ({len(active)} active / {len(stale)} stale):")
    for p in sorted(projects, key=lambda x: x["age_days"]):
        icon = "🟢" if not p["stale"] else "🔴" if p["age_days"] > 14 else "🟡"
        lines.append(f"   {icon} {p['project']:20s} │ {p['last_commit']} ({p['age_days']}일 전)")

    # DORA
    lines.append(f"\n{dora}")

    # 추천 작업
    lines.append(f"\n💡 추천 작업:")
    if git["total"] > 0:
        lines.append(f"   1. uncommitted {git['total']}개 변경사항 커밋 (/deploy)")
    if stale:
        stale_names = ", ".join(p["project"] for p in stale[:3])
        lines.append(f"   2. 장기 방치 프로젝트 점검: {stale_names}")
    if todos.get("todos"):
        lines.append(f"   3. 이전 세션 TODO 이어서 작업")

    lines.append("\n" + "─" * 57)
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Workspace Summary")
    parser.add_argument("--no-dora", action="store_true", help="DORA 메트릭 생략 (빠른 실행)")
    args = parser.parse_args()

    git = get_git_status()
    todos = get_latest_session_todos()
    projects = get_project_last_commits()
    dora = get_dora_oneliner() if not args.no_dora else "📊 DORA: (생략)"

    print(format_summary(git, todos, projects, dora))


if __name__ == "__main__":
    main()
