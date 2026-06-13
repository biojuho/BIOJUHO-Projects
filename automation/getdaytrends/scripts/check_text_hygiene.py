"""Check key getdaytrends docs for mojibake and broken text markers."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILES = (
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "WORKFLOW.md",
    PROJECT_ROOT / "GETDAYTRENDS_COMPLETION_PLAN.md",
    PROJECT_ROOT / "docs" / "RUNBOOK_ROLLBACK_FAILOVER.md",
    PROJECT_ROOT / "docs" / "GITHUB_BENCHMARK_2026-06-04.md",
    PROJECT_ROOT / "dashboard_html.py",
)
DEFAULT_REPORT = PROJECT_ROOT / "logs" / "hygiene" / "text_hygiene_latest.json"

MOJIBAKE_PATTERNS = {
    "replacement_character": re.compile("\ufffd"),
    "cp949_replacement_text": re.compile("\u5360\uc3d9\uc619"),
    "utf8_as_latin1": re.compile(
        r"(?:\u00c3.|\u00c2.|\u00e2\u20ac|\u00e2\u20ac\u2122|\u00e2\u20ac\u0153|"
        r"\u00e2\u20ac\x9d|\u00e2\u20ac\u201c|\u00e2\u20ac\u201d|\u00f0\u0178)"
    ),
    "escaped_replacement": re.compile(r"\\ufffd|\\uFFFD"),
    "html_mojibake": re.compile(r"&iuml;|&iquest;|&frac12;"),
    "question_prefixed_hangul": re.compile(r"\?[\u3130-\u318f\uac00-\ud7a3]"),
    "known_cp949_artifacts": re.compile(r"占|쨌|濡|諛|珥|湲"),
}


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    column: int
    pattern: str
    excerpt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "line": self.line,
            "column": self.column,
            "pattern": self.pattern,
            "excerpt": self.excerpt,
        }


def _excerpt(line: str, start: int, width: int = 90) -> str:
    left = max(0, start - width // 2)
    right = min(len(line), start + width // 2)
    return line[left:right].strip()


def scan_text(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern_name, pattern in MOJIBAKE_PATTERNS.items():
            for match in pattern.finditer(line):
                findings.append(
                    Finding(
                        path=path,
                        line=line_number,
                        column=match.start() + 1,
                        pattern=pattern_name,
                        excerpt=_excerpt(line, match.start()),
                    )
                )
    return findings


def scan_files(paths: list[Path]) -> tuple[list[Finding], list[dict[str, str]]]:
    findings: list[Finding] = []
    read_errors: list[dict[str, str]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            read_errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
            continue
        findings.extend(scan_text(path, text))
    return findings, read_errors


def write_report(report_path: Path, payload: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_check(paths: list[Path], report_path: Path) -> dict[str, Any]:
    resolved_paths = [path if path.is_absolute() else PROJECT_ROOT / path for path in paths]
    findings, read_errors = scan_files(resolved_paths)
    payload = {
        "schema_version": 1,
        "status": "pass" if not findings and not read_errors else "fail",
        "generated_at": datetime.now().astimezone().isoformat(),
        "project_root": str(PROJECT_ROOT),
        "summary": {
            "checked": len(resolved_paths),
            "findings": len(findings),
            "read_errors": len(read_errors),
        },
        "checked_files": [str(path) for path in resolved_paths],
        "findings": [finding.to_dict() for finding in findings],
        "read_errors": read_errors,
    }
    write_report(report_path, payload)
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check key docs for mojibake and broken text markers.")
    parser.add_argument(
        "--file",
        action="append",
        type=Path,
        dest="files",
        help="File to check. May be provided multiple times. Defaults to production docs.",
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Path to write the JSON report.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = args.files or list(DEFAULT_FILES)
    payload = run_check(paths, args.report)
    print(f"getdaytrends text hygiene: {payload['status']}")
    print(f"report: {args.report}")
    print(f"checked: {len(payload['checked_files'])}")
    print(f"findings: {len(payload['findings'])}")
    print(f"read_errors: {len(payload['read_errors'])}")
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
