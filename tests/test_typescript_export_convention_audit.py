from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "typescript_export_convention_audit.py"


def load_module():
    spec = importlib.util.spec_from_file_location("typescript_export_convention_audit", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_workspace_has_no_experimental_prefix_violations() -> None:
    audit = load_module()

    report = audit.audit_export_conventions()

    assert report["status"] == "pass"
    assert report["violation_count"] == 0
    assert report["scanned_files"] > 0
    assert "vercel/ai@beb6c72357fc970c3985a9b7e5ec346622102f28" in report["source_signal"]


def test_audit_rejects_prefixed_declarations(tmp_path: Path) -> None:
    audit = load_module()
    source = tmp_path / "src" / "index.ts"
    source.parent.mkdir()
    source.write_text(
        "export class Experimental_Widget {}\n"
        "const experimental_runner = () => null;\n",
        encoding="utf-8",
    )

    report = audit.audit_export_conventions([source.parent], workspace_root=tmp_path)

    assert report["status"] == "fail"
    assert report["violation_count"] == 2
    assert {item["rule"] for item in report["violations"]} == {"experimental_prefix_declaration"}
    assert {item["symbol"] for item in report["violations"]} == {
        "Experimental_Widget",
        "experimental_runner",
    }


def test_audit_allows_alias_at_export_seam(tmp_path: Path) -> None:
    audit = load_module()
    source = tmp_path / "src" / "index.ts"
    feature = tmp_path / "src" / "widget.ts"
    source.parent.mkdir()
    source.write_text(
        "export { Widget as Experimental_Widget } from './widget';\n"
        "export { createWidget as experimental_createWidget } from './widget';\n",
        encoding="utf-8",
    )
    feature.write_text(
        "export class Widget {}\n"
        "export function createWidget() { return new Widget(); }\n",
        encoding="utf-8",
    )

    report = audit.audit_export_conventions([source.parent], workspace_root=tmp_path)

    assert report["status"] == "pass"
    assert report["violation_count"] == 0
    assert report["accepted_export_alias_count"] == 2
    assert {
        (item["local_symbol"], item["exported_symbol"]) for item in report["accepted_export_aliases"]
    } == {
        ("Widget", "Experimental_Widget"),
        ("createWidget", "experimental_createWidget"),
    }


def test_audit_rejects_unaliased_prefixed_imports(tmp_path: Path) -> None:
    audit = load_module()
    source = tmp_path / "src" / "consumer.ts"
    source.parent.mkdir()
    source.write_text(
        "import { Experimental_Widget, experimental_createWidget as experimental_createWidget } from 'sdk';\n",
        encoding="utf-8",
    )

    report = audit.audit_export_conventions([source.parent], workspace_root=tmp_path)

    assert report["status"] == "fail"
    assert report["violation_count"] == 2
    assert {item["rule"] for item in report["violations"]} == {"experimental_prefix_import_alias"}


def test_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    audit = load_module()
    source = tmp_path / "src" / "index.ts"
    json_out = tmp_path / "report.json"
    markdown_out = tmp_path / "report.md"
    source.parent.mkdir()
    source.write_text("export { Widget as Experimental_Widget } from './widget';\n", encoding="utf-8")

    result = audit.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--root",
            "src",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert result == 0
    assert payload["status"] == "pass"
    assert payload["global_objective_complete"] is False
    assert "TypeScript Experimental Export Convention Audit" in markdown
    assert "Experimental_Widget" in markdown
