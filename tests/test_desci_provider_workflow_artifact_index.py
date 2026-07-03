import importlib.util
import hashlib
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "write_desci_provider_workflow_artifact_index.py"


def load_module():
    spec = importlib.util.spec_from_file_location("write_desci_provider_workflow_artifact_index", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_artifacts(root: Path, paths: list[str]) -> None:
    for relative_path in paths:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative_path}\n", encoding="utf-8")


def _write_verify_json(root: Path, path: str, *, ok: bool = False) -> None:
    output = root / path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "ok": ok,
                "operator_phase": "provider_apply_workflow_blocked",
                "ready_to_apply": False,
                "all_commands_succeeded": False,
                "promotion_receipt_ok": False,
                "summary": {
                    "failure_count": 2,
                    "results_command_failure_count": 1,
                },
                "failures": [
                    "provider apply results must have all_commands_succeeded=true",
                    "post-apply promotion receipt must be go",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_desci_provider_workflow_artifact_index_reports_complete_bundle(tmp_path) -> None:
    module = load_module()
    _write_artifacts(tmp_path, [item["path"] for item in module.REVIEW_ORDER])
    _write_verify_json(tmp_path, module.DEFAULT_VERIFY_JSON)
    template_path = tmp_path / module.PROVIDER_TEMPLATE_DIR / "railway.env"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text("RAILWAY_TOKEN=\n", encoding="utf-8")

    payload = module.build_payload(
        root=tmp_path,
        json_out=module.DEFAULT_INDEX_PATH,
        external_exit_code="1",
        handoff_exit_code="1",
        results_exit_code="1",
        verify_exit_code="1",
    )

    assert payload["schema_version"] == 1
    assert payload["generated_at"].endswith("Z")
    assert payload["first_decision_artifact"] == module.DEFAULT_VERIFY_JSON
    assert payload["provider_template_dir"] == module.PROVIDER_TEMPLATE_DIR
    assert payload["upload_before_fail_closed"] is True
    assert payload["all_required_artifacts_present"] is True
    assert payload["missing_artifact_count"] == 0
    assert payload["missing_artifacts"] == []
    assert payload["exit_codes"] == {
        "external_release_gate": "1",
        "provider_handoff": "1",
        "provider_apply_results": "1",
        "provider_apply_workflow_verifier": "1",
    }
    assert payload["provider_apply_workflow"]["ok"] is False
    assert payload["provider_apply_workflow"]["operator_phase"] == "provider_apply_workflow_blocked"
    assert payload["provider_apply_workflow"]["failure_count"] == 2
    assert payload["provider_apply_workflow"]["results_command_failure_count"] == 1
    assert "post-apply promotion receipt must be go" in payload["provider_apply_workflow"]["failures"]
    assert payload["provider_templates"][0]["path"] == "var/external-gate-provider-workflow-machine/railway.env"
    assert payload["provider_templates"][0]["required_for_complete_bundle"] is False
    expected_digest = hashlib.sha256((tmp_path / module.REVIEW_ORDER[0]["path"]).read_bytes()).hexdigest()
    assert payload["artifacts"][0]["sha256"] == expected_digest
    assert payload["artifacts"][0]["sha256_short"] == expected_digest[:12]


def test_desci_provider_workflow_artifact_index_reports_missing_bundle_members(tmp_path) -> None:
    module = load_module()
    first_artifact = module.REVIEW_ORDER[0]["path"]
    _write_artifacts(tmp_path, [first_artifact])

    payload = module.build_payload(
        root=tmp_path,
        json_out=module.DEFAULT_INDEX_PATH,
        external_exit_code=None,
        handoff_exit_code=None,
        results_exit_code=None,
        verify_exit_code=None,
    )

    assert payload["all_required_artifacts_present"] is False
    assert payload["missing_artifact_count"] == len(module.REVIEW_ORDER) - 1
    assert first_artifact not in payload["missing_artifacts"]
    assert module.DEFAULT_VERIFY_JSON in payload["missing_artifacts"]
    assert payload["provider_apply_workflow"]["ok"] is None
    assert payload["artifacts"][0]["exists"] is True
    assert payload["artifacts"][1]["exists"] is False
    assert payload["artifacts"][1]["size_bytes"] is None
    assert payload["artifacts"][1]["sha256"] is None
    assert payload["artifacts"][1]["sha256_short"] is None


def test_desci_provider_workflow_artifact_index_renders_markdown_summary(tmp_path) -> None:
    module = load_module()
    first_artifact = module.REVIEW_ORDER[0]["path"]
    _write_artifacts(tmp_path, [first_artifact])
    _write_verify_json(tmp_path, module.DEFAULT_VERIFY_JSON)

    payload = module.build_payload(
        root=tmp_path,
        json_out=module.DEFAULT_INDEX_PATH,
        external_exit_code="1",
        handoff_exit_code="0",
        results_exit_code="1",
        verify_exit_code="1",
    )
    markdown = module.render_markdown_summary(payload)

    assert "## DeSci Provider Apply Workflow Artifact Index" in markdown
    assert f"- First decision artifact: `{module.DEFAULT_VERIFY_JSON}`" in markdown
    assert "- Complete bundle: `no`" in markdown
    assert "- Provider workflow ok: `no`" in markdown
    assert "- Provider workflow phase: `provider_apply_workflow_blocked`" in markdown
    assert "| Exit Code | Value |" in markdown
    assert "| `provider_handoff` | `0` |" in markdown
    assert "| Order | Artifact | Required | Exists | Size bytes | SHA-256 | Purpose |" in markdown
    assert "| 1 | `var/external-release-gate-provider-workflow-machine.json` | yes | yes |" in markdown
    assert "| 2 | `var/external-gate-handoff-provider-workflow-machine.json` | yes | no |  |  |" in markdown
    assert "post-apply promotion receipt must be go" in markdown


def test_desci_provider_workflow_artifact_index_appends_step_summary(tmp_path) -> None:
    module = load_module()
    summary_path = tmp_path / "summary.md"

    appended = module.append_github_step_summary("## Summary\n", str(summary_path))

    assert appended is True
    assert "## Summary" in summary_path.read_text(encoding="utf-8")


def test_desci_provider_workflow_artifact_index_cli_writes_atomic_json_and_markdown(tmp_path) -> None:
    module = load_module()
    output = tmp_path / "var" / "desci-provider-workflow-artifact-index-machine.json"
    markdown_output = tmp_path / "var" / "desci-provider-workflow-artifact-index-summary.md"
    summary_path = tmp_path / "var" / "github-step-summary.md"

    old_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    os.environ["GITHUB_STEP_SUMMARY"] = str(summary_path)
    try:
        exit_code = module.main(
            [
                "--workspace-root",
                str(tmp_path),
                "--json-out",
                "var/desci-provider-workflow-artifact-index-machine.json",
                "--markdown-summary-out",
                "var/desci-provider-workflow-artifact-index-summary.md",
                "--append-github-step-summary",
                "--external-exit-code",
                "7",
                "--handoff-exit-code",
                "0",
                "--results-exit-code",
                "1",
                "--verify-exit-code",
                "1",
            ]
        )
    finally:
        if old_summary is None:
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
        else:
            os.environ["GITHUB_STEP_SUMMARY"] = old_summary

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["index_path"] == "var/desci-provider-workflow-artifact-index-machine.json"
    assert payload["exit_codes"]["external_release_gate"] == "7"
    assert payload["exit_codes"]["provider_handoff"] == "0"
    assert payload["missing_artifact_count"] == len(module.REVIEW_ORDER)
    assert payload["artifacts"][0]["sha256"] is None
    assert not output.with_name(f"{output.name}.tmp").exists()
    assert "DeSci Provider Apply Workflow Artifact Index" in markdown_output.read_text(encoding="utf-8")
    assert "DeSci Provider Apply Workflow Artifact Index" in summary_path.read_text(encoding="utf-8")
