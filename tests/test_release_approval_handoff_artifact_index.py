import importlib.util
import hashlib
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "write_release_approval_handoff_artifact_index.py"


def load_module():
    spec = importlib.util.spec_from_file_location("write_release_approval_handoff_artifact_index", SCRIPT_PATH)
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


def test_release_approval_handoff_artifact_index_reports_complete_bundle(tmp_path) -> None:
    module = load_module()
    _write_artifacts(tmp_path, [item["path"] for item in module.REVIEW_ORDER])

    payload = module.build_payload(
        root=tmp_path,
        json_out=module.DEFAULT_INDEX_PATH,
        wrapper_exit_code="1",
        release_gate_exit_code="0",
    )

    assert payload["schema_version"] == 1
    assert payload["generated_at"].endswith("Z")
    assert payload["first_decision_artifact"] == "var/desci-release-gate-release-approval-handoff-machine.json"
    assert payload["upload_before_fail_closed"] is True
    assert payload["all_required_artifacts_present"] is True
    assert payload["missing_artifact_count"] == 0
    assert payload["missing_artifacts"] == []
    assert payload["exit_codes"] == {
        "release_approval_wrapper": "1",
        "desci_release_gate_handoff": "0",
    }
    assert [item["id"] for item in payload["review_order"]] == [
        "product_release_gate_parent",
        "operator_markdown_summary",
        "raw_release_approval_analysis",
        "session_bootstrap_context",
        "workspace_smoke_context",
    ]
    assert all(item["exists"] is True for item in payload["artifacts"])
    assert all(isinstance(item["size_bytes"], int) and item["size_bytes"] > 0 for item in payload["artifacts"])
    expected_digest = hashlib.sha256((tmp_path / module.REVIEW_ORDER[0]["path"]).read_bytes()).hexdigest()
    assert payload["artifacts"][0]["sha256"] == expected_digest
    assert payload["artifacts"][0]["sha256_short"] == expected_digest[:12]


def test_release_approval_handoff_artifact_index_reports_missing_bundle_members(tmp_path) -> None:
    module = load_module()
    first_artifact = module.REVIEW_ORDER[0]["path"]
    _write_artifacts(tmp_path, [first_artifact])

    payload = module.build_payload(
        root=tmp_path,
        json_out=module.DEFAULT_INDEX_PATH,
        wrapper_exit_code=None,
        release_gate_exit_code=None,
    )

    assert payload["all_required_artifacts_present"] is False
    assert payload["missing_artifact_count"] == len(module.REVIEW_ORDER) - 1
    assert first_artifact not in payload["missing_artifacts"]
    assert "var/release-approval-check-machine.json" in payload["missing_artifacts"]
    assert payload["artifacts"][0]["exists"] is True
    assert payload["artifacts"][1]["exists"] is False
    assert payload["artifacts"][1]["size_bytes"] is None
    assert payload["artifacts"][1]["sha256"] is None
    assert payload["artifacts"][1]["sha256_short"] is None


def test_release_approval_handoff_artifact_index_renders_markdown_summary(tmp_path) -> None:
    module = load_module()
    first_artifact = module.REVIEW_ORDER[0]["path"]
    _write_artifacts(tmp_path, [first_artifact])

    payload = module.build_payload(
        root=tmp_path,
        json_out=module.DEFAULT_INDEX_PATH,
        wrapper_exit_code="1",
        release_gate_exit_code="0",
    )
    markdown = module.render_markdown_summary(payload)

    assert "## Release Approval Handoff Artifact Index" in markdown
    assert "- First decision artifact: `var/desci-release-gate-release-approval-handoff-machine.json`" in markdown
    assert "- Complete bundle: `no`" in markdown
    assert "- Missing artifacts: `4`" in markdown
    assert "| Order | Artifact | Exists | Size bytes | SHA-256 | Purpose |" in markdown
    assert "| 1 | `var/desci-release-gate-release-approval-handoff-machine.json` | yes |" in markdown
    assert "| 2 | `docs/reports/2026-06/RELEASE_APPROVAL_OPERATOR_HANDOFF_MACHINE.md` | no |  |  |" in markdown


def test_release_approval_handoff_artifact_index_appends_step_summary(tmp_path) -> None:
    module = load_module()
    summary_path = tmp_path / "summary.md"

    appended = module.append_github_step_summary("## Summary\n", str(summary_path))

    assert appended is True
    assert "## Summary" in summary_path.read_text(encoding="utf-8")


def test_release_approval_handoff_artifact_index_cli_writes_atomic_json(tmp_path) -> None:
    module = load_module()
    output = tmp_path / "var" / "release-approval-handoff-artifact-index-machine.json"
    markdown_output = tmp_path / "var" / "release-approval-handoff-artifact-index-summary.md"

    exit_code = module.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--json-out",
            "var/release-approval-handoff-artifact-index-machine.json",
            "--markdown-summary-out",
            "var/release-approval-handoff-artifact-index-summary.md",
            "--wrapper-exit-code",
            "7",
            "--release-gate-exit-code",
            "0",
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["index_path"] == "var/release-approval-handoff-artifact-index-machine.json"
    assert payload["exit_codes"]["release_approval_wrapper"] == "7"
    assert payload["exit_codes"]["desci_release_gate_handoff"] == "0"
    assert payload["missing_artifact_count"] == len(module.REVIEW_ORDER)
    assert payload["artifacts"][0]["sha256"] is None
    assert not output.with_name(f"{output.name}.tmp").exists()
    assert "Release Approval Handoff Artifact Index" in markdown_output.read_text(encoding="utf-8")
