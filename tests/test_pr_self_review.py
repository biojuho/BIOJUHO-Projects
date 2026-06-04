from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SELF_REVIEW_PATH = PROJECT_ROOT / "ops" / "scripts" / "pr_self_review.py"


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _expect_equal(actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")


def _load_self_review_module():
    spec = importlib.util.spec_from_file_location("pr_self_review_under_test", SELF_REVIEW_PATH)
    _expect(spec is not None and spec.loader is not None, "self-review module spec should load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _contract_findings(findings) -> list:
    return [finding for finding in findings if finding.category.startswith("1.")]


def test_shared_source_without_tests_stays_red() -> None:
    review = _load_self_review_module()
    stats = review.DiffStats(
        files_changed=["packages/shared/fact_check/verifier.py"],
        insertions=5,
        deletions=0,
        diff_content="+def changed():\n",
    )

    findings = _contract_findings(review.analyze(stats))

    _expect_equal(len(findings), 1)
    _expect_equal(findings[0].severity, "\U0001f534")


def test_shared_source_with_matching_shared_tests_is_yellow() -> None:
    review = _load_self_review_module()
    stats = review.DiffStats(
        files_changed=[
            "packages/shared/fact_check/verifier.py",
            "packages/shared/tests/test_fact_check_verifier.py",
        ],
        insertions=20,
        deletions=1,
        diff_content="+def changed():\n+def test_changed():\n",
    )

    findings = _contract_findings(review.analyze(stats))

    _expect_equal(len(findings), 1)
    _expect_equal(findings[0].severity, "\U0001f7e1")
