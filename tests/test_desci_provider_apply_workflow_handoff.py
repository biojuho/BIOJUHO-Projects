from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "desci-provider-apply-workflow-handoff.yml"


def test_desci_provider_apply_workflow_handoff_contract() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    for marker in (
        "workflow_dispatch",
        "permissions:",
        "contents: read",
        "Provider Apply Workflow Handoff",
        "Provider Apply Workflow Artifact Post-Download Verification",
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
        "actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0",
        "var/provider-workflow-downloaded-artifact",
        "var/provider-workflow-downloaded-artifact/desci-provider-workflow-artifact-index-machine.json",
        "provider-apply-workflow-post-download-verification-${{ github.run_id }}-${{ github.run_attempt }}",
        "var/provider-workflow-downloaded-artifact-bundle-verify.json",
        "var/provider-workflow-downloaded-artifact-bundle-verify.md",
        "--markdown-summary-out",
        "--artifact-root .",
        "--artifact-root var/provider-workflow-downloaded-artifact",
        "needs: provider-apply-workflow-handoff",
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


def test_desci_provider_apply_workflow_post_download_job_contract() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    assert "provider-apply-workflow-handoff" in jobs
    assert "provider-apply-workflow-artifact-post-download" in jobs

    handoff_steps = jobs["provider-apply-workflow-handoff"]["steps"]
    handoff_step_names = [step.get("name", "") for step in handoff_steps]
    assert handoff_step_names.index("Write provider apply workflow artifact index") < handoff_step_names.index(
        "Verify provider apply workflow artifact bundle"
    )
    assert handoff_step_names.index("Verify provider apply workflow artifact bundle") < handoff_step_names.index(
        "Upload provider apply workflow artifacts"
    )
    assert handoff_step_names.index("Upload provider apply workflow artifacts") < handoff_step_names.index(
        "Fail closed on provider apply workflow blockers"
    )

    post_download = jobs["provider-apply-workflow-artifact-post-download"]
    assert post_download["needs"] == "provider-apply-workflow-handoff"
    assert post_download["if"] == "always()"
    post_download_steps = post_download["steps"]
    post_download_step_names = [step.get("name", "") for step in post_download_steps]
    assert post_download_step_names == [
        "",
        "Download provider apply workflow artifact",
        "Verify downloaded provider apply workflow artifact bundle",
        "Upload downloaded provider apply workflow verification",
    ]
    assert post_download_steps[1]["uses"] == "actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0"
    assert post_download_steps[1]["with"]["path"] == "var/provider-workflow-downloaded-artifact"
