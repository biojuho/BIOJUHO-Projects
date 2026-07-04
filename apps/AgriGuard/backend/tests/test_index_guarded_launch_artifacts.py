from __future__ import annotations

import importlib.util
import json
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = APP_ROOT / "scripts" / "index_guarded_launch_artifacts.py"
SPEC = importlib.util.spec_from_file_location("index_guarded_launch_artifacts", SCRIPT_PATH)
assert SPEC is not None
index_guarded_launch_artifacts = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(index_guarded_launch_artifacts)

RUN_WRAPPER = index_guarded_launch_artifacts.run_guarded_launch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_core_artifacts(output_dir: Path, prefix: str) -> dict[str, Path]:
    paths = index_guarded_launch_artifacts._artifact_paths(output_dir.resolve(), prefix, None)
    _write_json(
        paths["launch_report_json"],
        {
            "status": "fail",
            "stage": "preflight",
            "stop_reason": "preflight_failed",
            "results": [{"name": "preflight"}],
        },
    )
    _write_json(paths["handoff_json"], {"status": "blocked"})
    paths["handoff_markdown"].write_text("# Handoff\n", encoding="utf-8")
    _write_json(
        paths["handoff_validation_json"],
        {
            "status": "pass",
            "errors": [],
            "handoff_sha256": "abc",
            "schema_sha256": "def",
        },
    )
    _write_json(
        paths["handoff_consumer_json"],
        {
            "status": "fail",
            "blocker_class": "preflight_blocked",
            "validation_matches_handoff": True,
            "validation_status": "pass",
            "packet_validation_status": "pass",
            "packet_evidence_outputs_status": "pass",
            "packet_markdown_table_status": "pass",
            "packet_path_mismatch_count": 0,
            "errors": [],
        },
    )
    return paths


def test_index_guarded_launch_artifacts_passes_complete_blocked_evidence(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    _write_core_artifacts(output_dir, "blocked")

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )

    assert index["status"] == "pass"
    assert index["consumer_status"] == "fail"
    assert index["consumer_blocker_class"] == "preflight_blocked"
    assert index["validation_status"] == "pass"
    assert index["consumer_packet_validation_status"] == "pass"
    assert index["consumer_packet_markdown_table_status"] == "pass"
    assert index["missing_required_roles"] == []


def test_index_guarded_launch_artifacts_fails_packet_validation_drift(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    paths = _write_core_artifacts(output_dir, "blocked")
    consumer = json.loads(paths["handoff_consumer_json"].read_text(encoding="utf-8"))
    consumer["packet_validation_status"] = "fail"
    consumer["packet_markdown_table_status"] = "fail"
    paths["handoff_consumer_json"].write_text(json.dumps(consumer), encoding="utf-8")

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )

    assert index["status"] == "fail"
    assert index["consumer_packet_validation_status"] == "fail"
    assert index["consumer_packet_markdown_table_status"] == "fail"


def test_index_guarded_launch_artifacts_fails_missing_consumer(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    paths = _write_core_artifacts(output_dir, "blocked")
    paths["handoff_consumer_json"].unlink()

    index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
    )

    assert index["status"] == "fail"
    assert index["missing_required_roles"] == ["handoff_consumer_json"]


def test_index_guarded_launch_artifacts_can_require_status_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    status_json = tmp_path / "status.json"
    _write_core_artifacts(output_dir, "blocked")

    missing_index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
        status_json=status_json,
    )
    _write_json(status_json, {"status": "blocked"})
    present_index = index_guarded_launch_artifacts.build_index(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
        status_json=status_json,
    )

    assert missing_index["status"] == "fail"
    assert "status_json" in missing_index["missing_required_roles"]
    assert present_index["status"] == "pass"


def test_index_guarded_launch_artifacts_main_writes_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    json_out = tmp_path / "index.json"
    _write_core_artifacts(output_dir, "blocked")

    result = index_guarded_launch_artifacts.main(
        [
            "--app-root",
            str(APP_ROOT),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "blocked",
            "--json-out",
            str(json_out),
        ]
    )

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["status"] == "pass"
