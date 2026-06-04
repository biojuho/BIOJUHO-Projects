from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL_PATH = SKILL_DIR / "SKILL.md"
REQUIRED_FILES = [
    "SKILL.md",
    "references/source-backed-patterns.md",
    "references/workspace-loop.md",
    "examples/self-improvement-cycle.yaml",
]
REQUIRED_TRIGGERS = [
    "AutoResearch",
    "Karpathy concept",
    "self-improving skill",
    "continuous A/B testing",
    "find related GitHub projects",
    "오토리서치",
]
REQUIRED_TERMS = [
    "prompt-to-artifact checklist",
    "completion audit",
    "success criteria",
    "uncovered requirements",
    "proxy-verified",
    "github_modernization_radar.py",
    "run_workspace_smoke.py",
    "browser_smoke.py",
    "A/B",
    "commit",
    "push",
]
FORBIDDEN_PATTERNS = [
    r"git\s+reset\s+--hard",
    r"git\s+checkout\s+--\s",
    r"rm\s+-rf",
]


def validate(skill_dir: Path = SKILL_DIR) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        path = skill_dir / relative
        ok = path.exists() and path.is_file()
        checks.append({"name": f"file:{relative}", "ok": ok})
        if not ok:
            errors.append(f"missing required file: {relative}")

    text = SKILL_PATH.read_text(encoding="utf-8") if SKILL_PATH.exists() else ""
    frontmatter_ok = bool(re.match(r"^---\n[\s\S]+?\n---\n", text))
    checks.append({"name": "frontmatter", "ok": frontmatter_ok})
    if not frontmatter_ok:
        errors.append("SKILL.md must start with YAML frontmatter")

    description_ok = "description: This skill should be used when" in text
    checks.append({"name": "third_person_description", "ok": description_ok})
    if not description_ok:
        errors.append("description must use third-person trigger wording")

    for trigger in REQUIRED_TRIGGERS:
        ok = trigger in text
        checks.append({"name": f"trigger:{trigger}", "ok": ok})
        if not ok:
            errors.append(f"missing trigger phrase: {trigger}")

    for term in REQUIRED_TERMS:
        ok = term in text
        checks.append({"name": f"term:{term}", "ok": ok})
        if not ok:
            errors.append(f"missing workflow term: {term}")

    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [skill_dir / relative for relative in REQUIRED_FILES]
        if path.exists()
    )
    for pattern in FORBIDDEN_PATTERNS:
        ok = re.search(pattern, combined, flags=re.IGNORECASE) is None
        checks.append({"name": f"forbidden:{pattern}", "ok": ok})
        if not ok:
            errors.append(f"forbidden destructive pattern found: {pattern}")

    source_reference = skill_dir / "references" / "source-backed-patterns.md"
    source_text = source_reference.read_text(encoding="utf-8") if source_reference.exists() else ""
    for url in [
        "https://www.youtube.com/watch?v=LCEmiRjPEtQ",
        "https://github.com/PrefectHQ/fastmcp",
        "https://github.com/lastmile-ai/mcp-eval",
        "https://github.com/evalstate/fast-agent",
        "https://github.com/Uninen/devserver-mcp",
    ]:
        ok = url in source_text
        checks.append({"name": f"source:{url}", "ok": ok})
        if not ok:
            errors.append(f"missing source URL: {url}")

    example = skill_dir / "examples" / "self-improvement-cycle.yaml"
    example_text = example.read_text(encoding="utf-8") if example.exists() else ""
    for key in [
        "schema_version:",
        "cycle_id:",
        "ab_test:",
        "decision_rule:",
        "completion_audit:",
        "success_criteria:",
        "evidence:",
        "uncovered_requirements:",
        "continue_if_missing:",
        "commit_policy:",
    ]:
        ok = key in example_text
        checks.append({"name": f"example_key:{key}", "ok": ok})
        if not ok:
            errors.append(f"example is missing key: {key}")

    return {
        "ok": not errors,
        "skill_dir": str(skill_dir),
        "checks": checks,
        "errors": errors,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
