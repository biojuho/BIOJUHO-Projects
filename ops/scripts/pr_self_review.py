"""
PR Self-Review Generator — M-1
AI-assisted development에서 솔로 개발자의 코드 리뷰 부재를 보완.
git diff를 분석하여 8-point 리뷰 체크리스트를 생성.

Usage:
  python ops/scripts/pr_self_review.py [--base main] [--format md|json]

Output: Markdown 체크리스트 (stdout 또는 GITHUB_STEP_SUMMARY)
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ── Risk categories ──

HIGH_RISK_PATHS = {
    "packages/shared/",
    ".github/workflows/",
    "ops/",
}

SECURITY_PATTERNS = [
    r"(api[_-]?key|secret|token|password|credential)\s*=\s*['\"]",
    r"serviceAccountKey",
    r"\.env\b",
]

SCHEMA_PATTERNS = [
    r"CREATE\s+TABLE",
    r"ALTER\s+TABLE",
    r"DROP\s+TABLE",
    r"ADD\s+COLUMN",
]

API_PATTERNS = [
    r"def\s+\w+\(",  # function signature changes
    r"class\s+\w+",  # class changes
    r"@app\.(get|post|put|delete|patch)",  # FastAPI routes
]


@dataclass
class ReviewFinding:
    category: str
    severity: str  # 🔴 🟡 🟢
    message: str
    file: str = ""
    line: int = 0


@dataclass
class DiffStats:
    files_changed: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    diff_content: str = ""


def get_diff_stats(base: str = "main") -> DiffStats:
    """Get git diff statistics against base branch."""
    stats = DiffStats()

    # File list
    result = subprocess.run(
        ["git", "diff", "--name-only", base],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    stats.files_changed = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

    # Stat summary
    result = subprocess.run(
        ["git", "diff", "--stat", base],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for line in result.stdout.split("\n"):
        m = re.search(r"(\d+)\s+insertion", line)
        if m:
            stats.insertions = int(m.group(1))
        m = re.search(r"(\d+)\s+deletion", line)
        if m:
            stats.deletions = int(m.group(1))

    # Full diff content
    result = subprocess.run(
        ["git", "diff", base],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    stats.diff_content = result.stdout
    return stats


def analyze(stats: DiffStats) -> list[ReviewFinding]:
    """Run 8-point review analysis on diff."""
    findings: list[ReviewFinding] = []

    # ── 1. Contract violation ──
    for f in stats.files_changed:
        if f.startswith("packages/shared/"):
            findings.append(ReviewFinding(
                category="1. 계약 위반",
                severity="🔴",
                message=f"shared/ 모듈 수정 — 모든 소비자 프로젝트에 영향",
                file=f,
            ))

    # ── 2. Side effects ──
    for f in stats.files_changed:
        if any(f.startswith(p) for p in HIGH_RISK_PATHS):
            findings.append(ReviewFinding(
                category="2. 부수 효과",
                severity="🟡",
                message=f"고위험 경로 변경 — blast radius 확인 필요",
                file=f,
            ))

    # ── 3. Test coverage ──
    changed_src = [f for f in stats.files_changed
                   if f.endswith(".py") and "test" not in f.lower()]
    changed_tests = [f for f in stats.files_changed
                     if f.endswith(".py") and "test" in f.lower()]

    if changed_src and not changed_tests:
        findings.append(ReviewFinding(
            category="3. 테스트 커버리지",
            severity="🔴",
            message=f"소스 {len(changed_src)}개 변경, 테스트 0개 변경 — 테스트 추가 필요",
        ))
    elif len(changed_src) > len(changed_tests) * 2:
        findings.append(ReviewFinding(
            category="3. 테스트 커버리지",
            severity="🟡",
            message=f"소스 {len(changed_src)}개 vs 테스트 {len(changed_tests)}개 — 비율 확인",
        ))
    else:
        findings.append(ReviewFinding(
            category="3. 테스트 커버리지",
            severity="🟢",
            message="소스와 테스트 비율 양호",
        ))

    # ── 4. Error handling ──
    new_try_except = len(re.findall(r"^\+.*(?:try:|except\s)", stats.diff_content, re.MULTILINE))
    new_raise = len(re.findall(r"^\+.*raise\s", stats.diff_content, re.MULTILINE))
    if new_try_except == 0 and stats.insertions > 50:
        findings.append(ReviewFinding(
            category="4. 에러 핸들링",
            severity="🟡",
            message=f"{stats.insertions}줄 추가인데 try/except 0개 — 에러 처리 누락 가능",
        ))

    # ── 5. Security ──
    for pattern in SECURITY_PATTERNS:
        matches = re.findall(r"^\+.*" + pattern, stats.diff_content, re.MULTILINE | re.IGNORECASE)
        if matches:
            findings.append(ReviewFinding(
                category="5. 보안",
                severity="🔴",
                message=f"보안 위험 패턴 감지: {pattern[:30]}... ({len(matches)}건)",
            ))

    # ── 6. Dependencies ──
    dep_files = [f for f in stats.files_changed
                 if f.endswith(("requirements.txt", "pyproject.toml", "package.json"))]
    if dep_files:
        findings.append(ReviewFinding(
            category="6. 의존성",
            severity="🟡",
            message=f"의존성 파일 변경: {', '.join(dep_files)}",
        ))

    # ── 7. Revertability ──
    schema_changes = []
    for pattern in SCHEMA_PATTERNS:
        matches = re.findall(r"^\+.*" + pattern, stats.diff_content, re.MULTILINE | re.IGNORECASE)
        schema_changes.extend(matches)

    if schema_changes:
        findings.append(ReviewFinding(
            category="7. 되돌림",
            severity="🔴",
            message=f"DB 스키마 변경 {len(schema_changes)}건 — revert 불가능할 수 있음",
        ))

    if len(stats.files_changed) > 7:
        findings.append(ReviewFinding(
            category="7. 되돌림",
            severity="🟡",
            message=f"{len(stats.files_changed)}개 파일 변경 — 큰 변경은 분리 커밋 권장",
        ))

    # ── 8. Naming ──
    new_defs = re.findall(r"^\+\s*(?:def|class)\s+(\w+)", stats.diff_content, re.MULTILINE)
    if new_defs:
        short_names = [n for n in new_defs if len(n) <= 2 and n not in ("id", "db")]
        if short_names:
            findings.append(ReviewFinding(
                category="8. 네이밍",
                severity="🟡",
                message=f"짧은 이름 감지: {', '.join(short_names)} — 명확한 이름 권장",
            ))

    return findings


def _severity_order(s: str) -> int:
    return {"🔴": 0, "🟡": 1, "🟢": 2}.get(s, 3)


def format_markdown(stats: DiffStats, findings: list[ReviewFinding]) -> str:
    """Format review as markdown checklist."""
    lines = [
        "## PR 셀프 리뷰 체크리스트",
        "",
        f"**변경 요약**: {len(stats.files_changed)}개 파일, "
        f"+{stats.insertions}/-{stats.deletions} 줄",
        "",
    ]

    # Summary counts
    red = sum(1 for f in findings if f.severity == "🔴")
    yellow = sum(1 for f in findings if f.severity == "🟡")
    green = sum(1 for f in findings if f.severity == "🟢")
    lines.append(f"| 🔴 반드시 수정 | 🟡 권장 | 🟢 괜찮음 |")
    lines.append(f"|:---:|:---:|:---:|")
    lines.append(f"| {red} | {yellow} | {green} |")
    lines.append("")

    # Sorted findings
    sorted_findings = sorted(findings, key=lambda f: _severity_order(f.severity))
    for f in sorted_findings:
        file_note = f" (`{f.file}`)" if f.file else ""
        lines.append(f"- {f.severity} **{f.category}**: {f.message}{file_note}")

    lines.append("")

    # Overall verdict
    if red > 0:
        lines.append("> ⚠️ **머지 전 수정 필요** — 🔴 항목을 해결하세요.")
    elif yellow > 2:
        lines.append("> 🟡 **주의 필요** — 권장 사항을 검토하세요.")
    else:
        lines.append("> ✅ **양호** — 머지 가능합니다.")

    return "\n".join(lines)


def main():
    # Windows cp949 encoding workaround
    import io
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    elif sys.stdout.encoding != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="PR Self-Review Generator")
    parser.add_argument("--base", default="main", help="Base branch to diff against")
    parser.add_argument("--format", default="md", choices=["md", "json"])
    args = parser.parse_args()

    stats = get_diff_stats(args.base)

    if not stats.files_changed:
        print("No changes detected against", args.base)
        return

    findings = analyze(stats)
    output = format_markdown(stats, findings)

    # Output to GITHUB_STEP_SUMMARY if available
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(output + "\n")

    print(output)

    # Exit code: 1 if any red findings
    red_count = sum(1 for f in findings if f.severity == "🔴")
    if red_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
