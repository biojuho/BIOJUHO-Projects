from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_script(relative_path: str):
    script_path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_session_bootstrap_counts_legacy_and_schema_v1_smoke_reports() -> None:
    module = load_script("ops/scripts/session_bootstrap.py")

    assert module._smoke_report_counts([{"ok": True}, {"ok": False}]) == (1, 2, "complete")
    assert module._smoke_report_label(1, 2, "complete") == "FAIL"
    assert module._smoke_report_counts(
        {
            "schema_version": 1,
            "status": "partial",
            "summary": {"passed": 1, "total": 3},
            "results": [{"ok": True}],
        }
    ) == (1, 3, "partial")
    assert module._smoke_report_label(1, 3, "partial") == "PARTIAL"


def test_context_snapshot_counts_legacy_and_schema_v1_smoke_reports() -> None:
    module = load_script("ops/scripts/generate_context_snapshot.py")

    assert module._smoke_report_counts([{"ok": True}]) == (1, 1, "complete")
    assert module._smoke_report_label(1, 1, "complete") == "PASS"
    assert module._smoke_report_counts(
        {
            "schema_version": 1,
            "status": "complete",
            "results": [{"ok": True}, {"ok": True}],
        }
    ) == (2, 2, "complete")
