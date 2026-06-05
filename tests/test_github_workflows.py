from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SMOKE_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "workspace-smoke.yml"
PR_ANALYSIS_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "pr-analysis.yml"
DASHBOARD_DEPLOY_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "deploy-dashboard.yml"
DASHBOARD_RELEASE_REFRESH_WORKFLOW = (
    PROJECT_ROOT / ".github" / "workflows" / "dashboard-release-refresh.yml"
)
WORKFLOW_DIR = PROJECT_ROOT / ".github" / "workflows"


def test_workspace_smoke_workflow_runs_autoresearch_audit_regression_tests() -> None:
    workflow = WORKSPACE_SMOKE_WORKFLOW.read_text(encoding="utf-8")

    assert "Run AutoResearch audit regression tests" in workflow
    assert "uv run pytest tests/test_github_workflows.py" in workflow
    assert "tests/test_agent_workflow_manifest.py" in workflow
    assert "tests/test_autoresearch_ci_regression.py" in workflow
    assert "tests/test_autoresearch_objective_coverage.py -q --tb=short" in workflow
    assert "PYTHONIOENCODING: utf-8" in workflow
    assert 'PYTHONUTF8: "1"' in workflow


def test_workspace_smoke_workflow_runs_autoresearch_audits_after_smoke_suite() -> None:
    workflow = WORKSPACE_SMOKE_WORKFLOW.read_text(encoding="utf-8")

    smoke_step = workflow.index("Run workspace smoke suite")
    audit_step = workflow.index("Run AutoResearch audit regression tests")
    summary_step = workflow.index("Append summary")

    assert smoke_step < audit_step < summary_step


def test_github_workflows_avoid_unsupported_repo_fork_remote_flag() -> None:
    offenders: list[str] = []
    for workflow_path in sorted(WORKFLOW_DIR.glob("*.yml")):
        for line_number, line in enumerate(workflow_path.read_text(encoding="utf-8").splitlines(), start=1):
            if "gh repo fork " in line and "--remote" in line:
                offenders.append(f"{workflow_path.relative_to(PROJECT_ROOT)}:{line_number}: {line.strip()}")

    assert offenders == []


def test_github_workflows_avoid_static_fork_owner_push_targets() -> None:
    offenders: list[str] = []
    static_fork_head = re.compile(r"--head\s+[\"']?[A-Za-z0-9_.-]+:")
    static_fork_remote = re.compile(r"github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git")

    for workflow_path in sorted(WORKFLOW_DIR.glob("*.yml")):
        for line_number, line in enumerate(workflow_path.read_text(encoding="utf-8").splitlines(), start=1):
            if "git remote add fork" in line and static_fork_remote.search(line):
                offenders.append(f"{workflow_path.relative_to(PROJECT_ROOT)}:{line_number}: {line.strip()}")
            if static_fork_head.search(line):
                offenders.append(f"{workflow_path.relative_to(PROJECT_ROOT)}:{line_number}: {line.strip()}")

    assert offenders == []


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


def test_dashboard_release_refresh_workflow_builds_and_uploads_dist_artifact() -> None:
    workflow = DASHBOARD_RELEASE_REFRESH_WORKFLOW.read_text(encoding="utf-8")

    assert "name: Dashboard Release Refresh" in workflow
    assert "workflow_dispatch:" in workflow
    assert "contents: read" in workflow
    assert "pull-requests: write" not in workflow
    assert "persist-credentials: false" in workflow
    assert "actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e" in workflow
    assert "github.event.inputs['node-version']" in workflow
    assert "cache-dependency-path: apps/dashboard/package-lock.json" in workflow
    assert "npm ci" in workflow
    assert "npm test -- --run" in workflow
    assert "npm run build" in workflow
    assert "npm run check:bundle" in workflow
    assert "actions/upload-artifact@330a01c490aca151604b8cf639adc76d48f6c5d4" in workflow
    assert "github.event.inputs['artifact-name']" in workflow
    assert "apps/dashboard/dist" in workflow
    assert "if-no-files-found: error" in workflow


def test_dashboard_deploy_workflow_checks_bundle_before_cloud_build() -> None:
    workflow = DASHBOARD_DEPLOY_WORKFLOW.read_text(encoding="utf-8")

    build_step = workflow.index("Build React Frontend")
    bundle_step = workflow.index("Check dashboard bundle budget")
    cloud_build_context_step = workflow.index("!apps/dashboard/dist/")
    cloud_build_step = workflow.index("gcloud builds submit")

    assert "npm run check:bundle" in workflow
    assert build_step < bundle_step < cloud_build_context_step < cloud_build_step
