from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "desci-provider-apply-workflow-handoff.yml"


def test_desci_provider_apply_workflow_handoff_contract() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    for marker in (
        "workflow_dispatch",
        "permissions:",
        "contents: read",
        "Provider Apply Workflow Handoff",
        "external_release_gate.py",
        "external_gate_handoff.py",
        "--github-step-summary",
        "--github-annotations",
        "--github-output",
        "write_desci_provider_workflow_artifact_index.py",
        "verify_desci_provider_workflow_artifact_bundle.py",
        "desci-provider-workflow-artifact-index-machine.json",
        "desci-provider-workflow-artifact-index-summary.md",
        "desci-provider-workflow-artifact-bundle-verify.json",
        "desci-provider-workflow-artifact-bundle-verify.md",
        "--markdown-summary-out",
        "--artifact-root .",
        "EXTERNAL_RELEASE_GATE_EXIT_CODE",
        "provider_apply_workflow_ok",
        "provider-apply-workflow-handoff-${{ github.run_id }}-${{ github.run_attempt }}",
        "if-no-files-found: error",
        "retention-days: 30",
        "Fail closed on provider apply workflow blockers",
        "var/external-gate-provider-workflow-machine-verify.json",
        "var/external-gate-provider-workflow-machine-results.json",
        "exit 0",
        "exit 1",
    ):
        assert marker in workflow
