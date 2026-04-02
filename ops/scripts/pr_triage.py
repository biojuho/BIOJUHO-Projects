"""Generate a deterministic PR triage snapshot for this monorepo.

This is an adaptation of intention-first PR triage ideas for our repository.
It does not attempt to auto-close or auto-land PRs. Instead it:

- recovers the PR intent from the title/body
- classifies affected areas from changed paths
- flags likely human-attention cases
- recommends the smallest relevant repo checks
- emits JSON and Markdown for GitHub Actions summaries or local use
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

MARKER = "<!-- pr-triage-report -->"
ROOT = Path(__file__).resolve().parents[2]

AREA_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("DailyNews", ("automation/DailyNews/",)),
    ("GetDayTrends", ("automation/getdaytrends/",)),
    ("AgriGuard", ("apps/AgriGuard/",)),
    ("DeSci", ("apps/desci-platform/",)),
    ("Dashboard", ("apps/dashboard/",)),
    ("Shared", ("packages/shared/",)),
    ("Ops", ("ops/",)),
    ("Docs", ("docs/",)),
    ("GitHub", (".github/",)),
    ("MCP", ("mcp/",)),
)

TEMPLATE_HEADINGS: tuple[tuple[str, str], ...] = (
    ("plain_language_intent", "## Plain-Language Intent"),
    ("underlying_problem", "## Underlying Problem"),
    ("why_this_approach", "## Why This Approach"),
    ("human_judgment_needed", "## Human Judgment Needed"),
    ("validation_plan", "## Validation Plan"),
)

HUMAN_DECISION_CHECKS: tuple[tuple[str, str], ...] = (
    ("product_or_ux", "- [x] Product behavior or UX decision needed"),
    ("architecture_or_scope", "- [x] Architecture or scope decision needed"),
)

MAINTENANCE_EXTENSIONS = {
    ".md",
    ".txt",
    ".rst",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".lock",
    ".gitignore",
}


@dataclass
class DiffStats:
    files_changed: int = 0
    lines_added: int = 0
    lines_deleted: int = 0


@dataclass
class TemplateStatus:
    missing_sections: list[str] = field(default_factory=list)
    requested_human_decisions: list[str] = field(default_factory=list)


@dataclass
class TriageReport:
    title: str
    url: str = ""
    intent: str = ""
    affected_areas: list[str] = field(default_factory=list)
    change_kind: str = "mixed"
    risk_level: str = "medium"
    status: str = "autonomous-review-lane"
    changed_files: list[str] = field(default_factory=list)
    diff_stats: DiffStats = field(default_factory=DiffStats)
    missing_template_sections: list[str] = field(default_factory=list)
    requested_human_decisions: list[str] = field(default_factory=list)
    human_attention_reasons: list[str] = field(default_factory=list)
    recommended_checks: list[str] = field(default_factory=list)


def _run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def get_changed_files(base: str, head: str) -> list[str]:
    output = _run_git("diff", "--name-only", f"{base}...{head}")
    return [line.strip() for line in output.splitlines() if line.strip()]


def get_diff_stats(base: str, head: str) -> DiffStats:
    output = _run_git("diff", "--numstat", f"{base}...{head}")
    stats = DiffStats()
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, deleted, _path = parts
        stats.files_changed += 1
        if added.isdigit():
            stats.lines_added += int(added)
        if deleted.isdigit():
            stats.lines_deleted += int(deleted)
    return stats


def classify_areas(files: list[str]) -> list[str]:
    matched: list[str] = []
    for area, prefixes in AREA_RULES:
        if any(path.startswith(prefix) for path in files for prefix in prefixes):
            matched.append(area)
    if not matched and files:
        matched.append("Other")
    return matched


def is_docs_only(files: list[str]) -> bool:
    if not files:
        return False
    for path_str in files:
        path = Path(path_str)
        if path_str.startswith(".github/workflows/"):
            return False
        if path_str.startswith("docs/"):
            continue
        if path_str.startswith(".github/") and path.suffix == ".md":
            continue
        if path.suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".sh", ".ps1"}:
            return False
        if path.suffix and path.suffix not in MAINTENANCE_EXTENSIONS:
            return False
    return True


def infer_change_kind(title: str, body: str, files: list[str], areas: list[str]) -> str:
    text = f"{title}\n{body}".lower()
    if is_docs_only(files):
        return "docs"
    if any(path.startswith(".github/workflows/") for path in files):
        return "infra"
    if "ops/" in "\n".join(files):
        if any(token in text for token in ("infra", "workflow", "ci", "deploy")):
            return "infra"
    if any(token in text for token in ("bug", "fix", "regression", "hotfix")):
        return "bug-fix"
    if any(token in text for token in ("refactor", "cleanup", "reshape")):
        return "refactor"
    if any(token in text for token in ("docs", "readme", "runbook")):
        return "docs"
    if len(areas) == 1 and areas[0] in {"Docs", "GitHub"}:
        return "maintenance"
    return "feature"


def evaluate_template_status(body: str) -> TemplateStatus:
    status = TemplateStatus()
    for key, heading in TEMPLATE_HEADINGS:
        if heading not in body:
            status.missing_sections.append(key)
    lowered = body.lower()
    for label, checkbox in HUMAN_DECISION_CHECKS:
        if checkbox.lower() in lowered:
            status.requested_human_decisions.append(label)
    return status


def derive_intent(title: str, body: str, change_kind: str) -> str:
    intent_match = re.search(
        r"## Plain-Language Intent\s+(.*?)(?:\n## |\Z)",
        body,
        flags=re.DOTALL,
    )
    if intent_match:
        intent = " ".join(intent_match.group(1).strip().split())
        if intent and "<!--" not in intent:
            return intent
    fallback = title.strip()
    if change_kind == "docs":
        return f"Clarify repository behavior and expectations around {fallback}."
    if change_kind == "bug-fix":
        return f"Fix a user-visible problem described as: {fallback}."
    if change_kind == "infra":
        return f"Change repository automation or delivery behavior for: {fallback}."
    return fallback or "Intent needs author clarification."


def calculate_risk(files: list[str], areas: list[str], stats: DiffStats, change_kind: str) -> str:
    if is_docs_only(files):
        return "low"

    score = 0
    file_blob = "\n".join(files)

    if len(areas) >= 3:
        score += 2
    if "Shared" in areas and len([a for a in areas if a not in {"Docs", "GitHub"}]) >= 2:
        score += 2
    if ".github/workflows/" in file_blob:
        score += 2
    if any(token in file_blob for token in ("docker-compose", "migration", "alembic", "schema", "supabase")):
        score += 2
    if stats.files_changed >= 15:
        score += 1
    if stats.lines_added + stats.lines_deleted >= 600:
        score += 1
    if change_kind == "infra":
        score += 1

    if score >= 5:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def human_attention_reasons(
    files: list[str],
    areas: list[str],
    stats: DiffStats,
    template_status: TemplateStatus,
    risk_level: str,
) -> list[str]:
    reasons: list[str] = []
    file_blob = "\n".join(files)

    if template_status.missing_sections:
        reasons.append("PR description is missing intention-first template sections.")
    if template_status.requested_human_decisions:
        reasons.append("Author explicitly requested product or architecture judgment.")
    if ".github/workflows/" in file_blob:
        reasons.append("CI or workflow automation changed.")
    if "Shared" in areas and len([area for area in areas if area not in {"Shared", "Docs", "GitHub"}]) >= 2:
        reasons.append("Shared code changes affect multiple product areas.")
    if stats.files_changed >= 25 or stats.lines_added + stats.lines_deleted >= 900:
        reasons.append("Diff is large enough that manual scope review is prudent.")
    if risk_level == "high":
        reasons.append("Risk heuristics classify this PR as high risk.")

    return reasons


def recommended_checks(areas: list[str], change_kind: str, risk_level: str) -> list[str]:
    checks = ["security-quality-gate"]

    if risk_level != "low" or "Shared" in areas or "Ops" in areas or "GitHub" in areas:
        checks.append("workspace-smoke")

    if "DailyNews" in areas:
        checks.append("automation/DailyNews targeted pytest or regression command")
    if "GetDayTrends" in areas:
        checks.append("getdaytrends-tests")
    if "AgriGuard" in areas:
        checks.extend(["agriguard-ci", "agriguard-quality"])
    if "DeSci" in areas:
        checks.extend(["ci", "desci-platform-quality"])
    if "Dashboard" in areas:
        checks.append("apps/dashboard build or smoke path")
    if change_kind in {"docs", "maintenance"} and risk_level == "low":
        checks.append("Normal repo checks are sufficient; no bespoke validation lane required.")

    deduped: list[str] = []
    for item in checks:
        if item not in deduped:
            deduped.append(item)
    return deduped


def build_report(base: str, head: str, title: str, body: str, url: str = "") -> TriageReport:
    files = get_changed_files(base, head)
    stats = get_diff_stats(base, head)
    areas = classify_areas(files)
    change_kind = infer_change_kind(title, body, files, areas)
    template_status = evaluate_template_status(body)
    risk = calculate_risk(files, areas, stats, change_kind)
    reasons = human_attention_reasons(files, areas, stats, template_status, risk)
    status = "needs-human-attention" if reasons else "autonomous-review-lane"

    return TriageReport(
        title=title,
        url=url,
        intent=derive_intent(title, body, change_kind),
        affected_areas=areas,
        change_kind=change_kind,
        risk_level=risk,
        status=status,
        changed_files=files,
        diff_stats=stats,
        missing_template_sections=template_status.missing_sections,
        requested_human_decisions=template_status.requested_human_decisions,
        human_attention_reasons=reasons,
        recommended_checks=recommended_checks(areas, change_kind, risk),
    )


def report_to_markdown(report: TriageReport) -> str:
    lines = [
        MARKER,
        "## PR Triage Snapshot",
        "",
        f"- Intent: {report.intent}",
        f"- Areas: {', '.join(report.affected_areas) or 'None detected'}",
        f"- Change kind: {report.change_kind}",
        f"- Risk: {report.risk_level}",
        f"- Status: {report.status}",
        f"- Diff: {report.diff_stats.files_changed} files, +{report.diff_stats.lines_added} / -{report.diff_stats.lines_deleted}",
    ]

    if report.missing_template_sections:
        lines.extend(
            [
                "",
                "### Missing author context",
                *[f"- {section}" for section in report.missing_template_sections],
            ]
        )

    if report.requested_human_decisions:
        lines.extend(
            [
                "",
                "### Requested human decisions",
                *[f"- {item}" for item in report.requested_human_decisions],
            ]
        )

    if report.human_attention_reasons:
        lines.extend(
            [
                "",
                "### Why this should get human attention",
                *[f"- {reason}" for reason in report.human_attention_reasons],
            ]
        )

    lines.extend(
        [
            "",
            "### Recommended checks",
            *[f"- {check}" for check in report.recommended_checks],
        ]
    )

    if report.url:
        lines.extend(["", f"Source: {report.url}"])

    return "\n".join(lines) + "\n"


def load_event_context() -> tuple[str, str, str]:
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        return "", "", ""
    path = Path(event_path)
    if not path.exists():
        return "", "", ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "", "", ""
    pr = data.get("pull_request") or {}
    return (
        str(pr.get("title") or ""),
        str(pr.get("body") or ""),
        str(pr.get("html_url") or ""),
    )


def to_jsonable(report: TriageReport) -> dict:
    payload = asdict(report)
    payload["diff_stats"] = asdict(report.diff_stats)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PR triage snapshot")
    parser.add_argument("--base", required=True, help="Base ref or SHA")
    parser.add_argument("--head", required=True, help="Head ref or SHA")
    parser.add_argument("--title", default="", help="PR title override")
    parser.add_argument("--body-file", default="", help="Path to a file that contains the PR body")
    parser.add_argument("--output-dir", default="var/pr-triage", help="Directory for JSON and Markdown outputs")
    args = parser.parse_args()

    title, body, url = load_event_context()
    if args.title:
        title = args.title
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")

    report = build_report(args.base, args.head, title=title, body=body, url=url)

    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "pr-triage.json"
    summary_path = output_dir / "pr-triage-summary.md"
    comment_path = output_dir / "pr-triage-comment.md"

    json_path.write_text(json.dumps(to_jsonable(report), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown = report_to_markdown(report)
    summary_path.write_text(markdown, encoding="utf-8")
    comment_path.write_text(markdown, encoding="utf-8")

    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
