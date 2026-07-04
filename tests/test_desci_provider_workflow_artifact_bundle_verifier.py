import importlib.util
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "write_desci_provider_workflow_artifact_index.py"
VERIFY_SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "verify_desci_provider_workflow_artifact_bundle.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
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
                "operator_phase": "provider_apply_workflow_ready" if ok else "provider_apply_workflow_blocked",
                "ready_to_apply": ok,
                "all_commands_succeeded": ok,
                "promotion_receipt_ok": ok,
                "summary": {
                    "failure_count": 0 if ok else 2,
                    "results_command_failure_count": 0 if ok else 1,
                    "operator_command_count": 8,
                    "operator_command_failure_count": 0,
                },
                "failures": [] if ok else ["provider apply plan is not ready"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_index(root: Path, *, workflow_ok: bool = False) -> Path:
    index_module = load_module(INDEX_SCRIPT_PATH, "write_desci_provider_workflow_artifact_index_test")
    _write_artifacts(root, [item["path"] for item in index_module.REVIEW_ORDER])
    _write_verify_json(root, index_module.DEFAULT_VERIFY_JSON, ok=workflow_ok)
    template_path = root / index_module.PROVIDER_TEMPLATE_DIR / "railway.env"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text("RAILWAY_TOKEN=\n", encoding="utf-8")
    payload = index_module.build_payload(
        root=root,
        json_out=index_module.DEFAULT_INDEX_PATH,
        external_exit_code="1",
        handoff_exit_code="1",
        results_exit_code="1",
        verify_exit_code="1",
    )
    index_path = root / index_module.DEFAULT_INDEX_PATH
    index_module.write_json_atomic(index_path, payload)
    return index_path


def test_provider_workflow_bundle_verifier_accepts_complete_no_go_bundle(tmp_path) -> None:
    module = load_module(VERIFY_SCRIPT_PATH, "verify_desci_provider_workflow_artifact_bundle")
    index_path = _write_index(tmp_path, workflow_ok=False)

    payload = module.verify_bundle(index_path=index_path, artifact_root=tmp_path)

    assert payload["ok"] is True
    assert payload["index_complete_bundle"] is True
    assert payload["provider_apply_workflow"]["ok"] is False
    assert payload["provider_apply_workflow"]["operator_command_count"] == 8
    assert payload["provider_apply_workflow"]["operator_command_failure_count"] == 0
    assert payload["summary"]["artifact_failure_count"] == 0
    assert payload["summary"]["missing_required_count"] == 0
    assert payload["summary"]["digest_mismatch_count"] == 0
    assert payload["summary"]["required_artifact_count"] == 9
    assert payload["artifacts"][0]["resolution_source"] == "index_path"


def test_provider_workflow_bundle_verifier_supports_downloaded_artifact_without_var_prefix(tmp_path) -> None:
    module = load_module(VERIFY_SCRIPT_PATH, "verify_desci_provider_workflow_artifact_bundle_downloaded")
    index_path = _write_index(tmp_path, workflow_ok=False)
    downloaded_root = tmp_path / "downloaded"
    downloaded_root.mkdir()
    for path in (tmp_path / "var").rglob("*"):
        if not path.is_file():
            continue
        target = downloaded_root / path.relative_to(tmp_path / "var")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())

    payload = module.verify_bundle(
        index_path=downloaded_root / "desci-provider-workflow-artifact-index-machine.json",
        artifact_root=downloaded_root,
    )

    assert payload["ok"] is True
    assert payload["summary"]["artifact_failure_count"] == 0
    assert payload["artifacts"][0]["resolution_source"] == "stripped_var_prefix"


def test_provider_workflow_bundle_verifier_rejects_digest_mismatch(tmp_path) -> None:
    module = load_module(VERIFY_SCRIPT_PATH, "verify_desci_provider_workflow_artifact_bundle_mismatch")
    index_path = _write_index(tmp_path, workflow_ok=False)
    tampered = tmp_path / "var" / "external-gate-provider-workflow-machine-results.json"
    tampered.write_text("tampered\n", encoding="utf-8")

    payload = module.verify_bundle(index_path=index_path, artifact_root=tmp_path)

    assert payload["ok"] is False
    assert payload["summary"]["artifact_failure_count"] == 1
    assert payload["summary"]["digest_mismatch_count"] == 1
    matching = [
        item
        for item in payload["artifacts"]
        if item["path"] == "var/external-gate-provider-workflow-machine-results.json"
    ]
    assert matching
    assert "artifact sha256 mismatch" in matching[0]["failures"]


def test_provider_workflow_bundle_verifier_allows_indexed_missing_required_artifacts(tmp_path) -> None:
    index_module = load_module(
        INDEX_SCRIPT_PATH,
        "write_desci_provider_workflow_artifact_index_incomplete",
    )
    module = load_module(
        VERIFY_SCRIPT_PATH,
        "verify_desci_provider_workflow_artifact_bundle_incomplete",
    )
    _write_verify_json(tmp_path, index_module.DEFAULT_VERIFY_JSON, ok=False)
    payload = index_module.build_payload(
        root=tmp_path,
        json_out=index_module.DEFAULT_INDEX_PATH,
        external_exit_code="1",
        handoff_exit_code="1",
        results_exit_code="1",
        verify_exit_code="1",
    )
    index_path = tmp_path / index_module.DEFAULT_INDEX_PATH
    index_module.write_json_atomic(index_path, payload)

    verification = module.verify_bundle(
        index_path=index_path,
        artifact_root=tmp_path,
        require_complete_bundle=False,
    )

    assert verification["ok"] is True
    assert verification["index_complete_bundle"] is False
    assert verification["summary"]["missing_required_count"] == len(index_module.REVIEW_ORDER) - 1
    assert verification["summary"]["artifact_failure_count"] == 0


def test_provider_workflow_bundle_verifier_can_require_workflow_ok(tmp_path) -> None:
    module = load_module(VERIFY_SCRIPT_PATH, "verify_desci_provider_workflow_artifact_bundle_require_go")
    index_path = _write_index(tmp_path, workflow_ok=False)

    payload = module.verify_bundle(index_path=index_path, artifact_root=tmp_path, require_workflow_ok=True)

    assert payload["ok"] is False
    assert "provider apply workflow must be ok when require_workflow_ok is set" in payload["failures"]


def test_provider_workflow_bundle_verifier_cli_writes_json_markdown_and_summary(tmp_path) -> None:
    module = load_module(VERIFY_SCRIPT_PATH, "verify_desci_provider_workflow_artifact_bundle_cli")
    index_path = _write_index(tmp_path, workflow_ok=True)
    output = tmp_path / "var" / "bundle-verify.json"
    markdown = tmp_path / "var" / "bundle-verify.md"
    summary = tmp_path / "var" / "step-summary.md"

    old_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    os.environ["GITHUB_STEP_SUMMARY"] = str(summary)
    try:
        exit_code = module.main(
            [
                "--index",
                str(index_path),
                "--artifact-root",
                str(tmp_path),
                "--json-out",
                str(output),
                "--markdown-out",
                str(markdown),
                "--require-workflow-ok",
                "--append-github-step-summary",
            ]
        )
    finally:
        if old_summary is None:
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
        else:
            os.environ["GITHUB_STEP_SUMMARY"] = old_summary

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["provider_apply_workflow"]["ok"] is True
    assert payload["provider_apply_workflow"]["operator_command_count"] == 8
    assert "DeSci Provider Workflow Artifact Bundle Verification" in markdown.read_text(encoding="utf-8")
    assert "- Operator command count: `8`" in markdown.read_text(encoding="utf-8")
    assert "DeSci Provider Workflow Artifact Bundle Verification" in summary.read_text(encoding="utf-8")
