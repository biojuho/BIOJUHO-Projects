from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = PROJECT_ROOT / "ops" / "scripts" / "audit_github_actions_runtime.py"


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _expect_equal(actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("gha_runtime_audit_under_test", AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("audit module spec should load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_codeql_v3_and_deprecated_input_are_action_required(tmp_path: Path) -> None:
    audit = _load_audit_module()
    _write(
        tmp_path / ".github" / "workflows" / "codeql.yml",
        """
name: CodeQL
jobs:
  analyze:
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          setup-python-dependencies: true
      - uses: github/codeql-action/analyze@v3
""",
    )

    files, findings = audit.scan_root(tmp_path)
    summary = audit.summarize(findings)

    _expect_equal(len(files), 1)
    _expect_equal(summary["action_required"], 3)
    _expect_equal(summary["review"], 1)
    _expect_equal(
        {finding.rule for finding in findings if finding.severity == "action_required"},
        {
            "codeql_action_v3",
            "codeql_setup_python_dependencies",
        },
    )


def test_node20_annotation_surfaces_are_review_not_strict(tmp_path: Path) -> None:
    audit = _load_audit_module()
    _write(
        tmp_path / ".github" / "actions" / "setup-python-uv" / "action.yml",
        """
name: setup-python-uv
runs:
  using: composite
  steps:
    - uses: astral-sh/setup-uv@v5
    - uses: actions/setup-python@v5
""",
    )

    _, findings = audit.scan_root(tmp_path)

    _expect_equal(audit.summarize(findings), {"action_required": 0, "review": 2})
    _expect_equal(
        {finding.value for finding in findings},
        {
            "astral-sh/setup-uv@v5",
            "actions/setup-python@v5",
        },
    )


def test_json_output_is_structured(tmp_path: Path, capsys) -> None:
    audit = _load_audit_module()
    _write(
        tmp_path / ".github" / "workflows" / "codeql.yml",
        """
name: CodeQL
jobs:
  analyze:
    steps:
      - uses: github/codeql-action/init@v4
      - uses: github/codeql-action/analyze@v4
""",
    )

    exit_code = audit.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    payload = json.loads(capsys.readouterr().out)

    _expect_equal(exit_code, 0)
    _expect_equal(payload["summary"], {"action_required": 0, "review": 0})
    _expect_equal(payload["findings"], [])
