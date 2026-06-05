"""Audit GitHub Actions runtime deprecation surfaces.

The script is intentionally static and permission-safe: it reads local workflow
and composite-action files, reports known CodeQL v3/deprecated-input issues, and
lists action references that were observed in Node 20 runtime annotations.

Usage:
  python3 ops/scripts/audit_github_actions_runtime.py
  python3 ops/scripts/audit_github_actions_runtime.py --format json
  python3 ops/scripts/audit_github_actions_runtime.py --strict
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

Severity = Literal["action_required", "review"]

CODEQL_V3_RE = re.compile(r"\bgithub/codeql-action/(init|autobuild|analyze)@v3\b")
SETUP_PYTHON_DEPENDENCIES_RE = re.compile(r"\bsetup-python-dependencies\s*:\s*true\b")
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*(?P<ref>[^#\s]+)", re.MULTILINE)

NODE20_ANNOTATION_SURFACES = {
    "actions/checkout@v4",
    "actions/setup-node@v4",
    "actions/setup-python@v5",
    "actions/upload-artifact@v4",
    "astral-sh/setup-uv@v5",
    "gitleaks/gitleaks-action@v2",
}


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: Severity
    path: str
    line: int
    value: str
    message: str
    recommendation: str


def _repo_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def iter_audit_files(root: Path) -> list[Path]:
    """Return workflow and composite-action files that can contain JS actions."""
    files: list[Path] = []

    workflows_dir = root / ".github" / "workflows"
    if workflows_dir.exists():
        files.extend(sorted(workflows_dir.glob("*.yml")))
        files.extend(sorted(workflows_dir.glob("*.yaml")))

    actions_dir = root / ".github" / "actions"
    if actions_dir.exists():
        files.extend(sorted(actions_dir.glob("**/action.yml")))
        files.extend(sorted(actions_dir.glob("**/action.yaml")))

    return files


def scan_file(path: Path, root: Path) -> list[Finding]:
    text = path.read_text(encoding="utf-8")
    rel_path = _repo_relative(path, root)
    findings: list[Finding] = []

    for match in CODEQL_V3_RE.finditer(text):
        action_ref = match.group(0)
        action_name = action_ref.split("@", 1)[0]
        findings.append(
            Finding(
                rule="codeql_action_v3",
                severity="action_required",
                path=rel_path,
                line=_line_for_offset(text, match.start()),
                value=action_ref,
                message="CodeQL Action v3 is deprecated in December 2026.",
                recommendation=f"Update to {action_name}@v4 with workflow-edit permission.",
            )
        )

    for match in SETUP_PYTHON_DEPENDENCIES_RE.finditer(text):
        findings.append(
            Finding(
                rule="codeql_setup_python_dependencies",
                severity="action_required",
                path=rel_path,
                line=_line_for_offset(text, match.start()),
                value=match.group(0),
                message="CodeQL setup-python-dependencies is deprecated and has no effect.",
                recommendation="Remove this CodeQL init input.",
            )
        )

    for match in USES_RE.finditer(text):
        action_ref = match.group("ref").strip().strip("\"'")
        if action_ref not in NODE20_ANNOTATION_SURFACES:
            continue
        findings.append(
            Finding(
                rule="node20_annotation_surface",
                severity="review",
                path=rel_path,
                line=_line_for_offset(text, match.start("ref")),
                value=action_ref,
                message="This action ref appeared in Node 20 runtime annotation inventory.",
                recommendation=(
                    "Confirm the upstream major tag has moved to Node 24 or upgrade to a Node 24-compatible ref."
                ),
            )
        )

    return findings


def scan_root(root: Path) -> tuple[list[Path], list[Finding]]:
    audit_files = iter_audit_files(root)
    findings: list[Finding] = []
    for path in audit_files:
        findings.extend(scan_file(path, root))
    findings.sort(key=lambda finding: (finding.severity != "action_required", finding.path, finding.line, finding.rule))
    return audit_files, findings


def summarize(findings: list[Finding]) -> dict[str, int]:
    summary = {"action_required": 0, "review": 0}
    for finding in findings:
        summary[finding.severity] += 1
    return summary


def format_text(root: Path, files: list[Path], findings: list[Finding]) -> str:
    summary = summarize(findings)
    lines = [
        "GitHub Actions runtime audit",
        f"root: {root.resolve()}",
        f"files scanned: {len(files)}",
        f"action_required: {summary['action_required']}",
        f"review: {summary['review']}",
        "",
    ]

    if not findings:
        lines.append("No findings.")
        return "\n".join(lines)

    for finding in findings:
        lines.append(
            f"{finding.severity.upper()} {finding.path}:{finding.line} "
            f"{finding.rule} {finding.value}"
        )
        lines.append(f"  {finding.message}")
        lines.append(f"  Recommendation: {finding.recommendation}")

    return "\n".join(lines)


def format_json(root: Path, files: list[Path], findings: list[Finding]) -> str:
    payload = {
        "root": str(root.resolve()),
        "files_scanned": [_repo_relative(path, root) for path in files],
        "summary": summarize(findings),
        "findings": [asdict(finding) for finding in findings],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root to scan.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when action_required findings remain.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or [])
    root = Path(args.root)
    files, findings = scan_root(root)
    output = format_json(root, files, findings) if args.format == "json" else format_text(root, files, findings)
    print(output)

    if args.strict and summarize(findings)["action_required"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
