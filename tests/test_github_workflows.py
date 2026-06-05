from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SMOKE_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "workspace-smoke.yml"
PR_ANALYSIS_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "pr-analysis.yml"


def test_workspace_smoke_workflow_runs_autoresearch_audit_regression_tests() -> None:
    workflow = WORKSPACE_SMOKE_WORKFLOW.read_text(encoding="utf-8")

    assert "Run AutoResearch audit regression tests" in workflow
    assert "uv run pytest tests/test_github_workflows.py tests/test_autoresearch_ci_regression.py" in workflow
    assert "tests/test_autoresearch_objective_coverage.py -q --tb=short" in workflow
    assert "PYTHONIOENCODING: utf-8" in workflow
    assert 'PYTHONUTF8: "1"' in workflow


def test_workspace_smoke_workflow_runs_autoresearch_audits_after_smoke_suite() -> None:
    workflow = WORKSPACE_SMOKE_WORKFLOW.read_text(encoding="utf-8")

    smoke_step = workflow.index("Run workspace smoke suite")
    audit_step = workflow.index("Run AutoResearch audit regression tests")
    summary_step = workflow.index("Append summary")

    assert smoke_step < audit_step < summary_step


def test_pr_analysis_workflow_is_read_only_and_separate_from_triage_comment() -> None:
    workflow = PR_ANALYSIS_WORKFLOW.read_text(encoding="utf-8")

    assert "name: PR Analysis" in workflow
    assert "pull-requests: read" in workflow
    assert "issues: read" in workflow
    assert "issues: write" not in workflow
    assert "--mode analysis" in workflow
    assert "var/pr-analysis/pr-analysis-summary.md" in workflow
    assert "github-script" not in workflow
    assert "pr-triage-comment.md" not in workflow


def test_pr_analysis_workflow_supports_read_only_comment_trigger() -> None:
    workflow = PR_ANALYSIS_WORKFLOW.read_text(encoding="utf-8")
    normalized_workflow = " ".join(workflow.split())

    assert "issue_comment:" in workflow
    assert "contains(github.event.comment.body, '/pr-analysis')" in workflow
    assert "github.event.issue.pull_request != null" in workflow
    assert (
        '["gh", "api", f"repos/{repository}/pulls/{pr_number}"]'
        in normalized_workflow
    )
    assert "repos/{repository}/pulls/{pr_number}" in workflow
    assert "refs/heads/${BASE_REF}:refs/remotes/origin/pr/${PR_NUMBER}/base" in workflow
    assert "refs/pull/${PR_NUMBER}/head" in workflow
    assert "steps.resolve-pr.outputs.head_ref" in workflow
    assert "--body-file var/pr-analysis/pr-body.md" in workflow
    assert "github-script" not in workflow
    assert "issues: write" not in workflow
