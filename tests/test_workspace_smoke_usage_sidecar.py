from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "run_workspace_smoke.py"


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("workspace_smoke", SMOKE_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _results_from_report(report: object) -> list[dict]:
    if isinstance(report, list):
        return report
    assert isinstance(report, dict)
    return report["results"]


def test_run_one_attaches_live_usage_sidecar(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    temp_dir = tmp_path / "workspace-smoke-usage"
    monkeypatch.setattr(smoke, "runtime_temp_dir", lambda root, item: temp_dir)
    code = (
        "import json, os, pathlib; "
        "pathlib.Path(os.environ['WORKSPACE_SMOKE_USAGE_OUT']).write_text("
        "json.dumps({'usage': {'prompt_tokens': 12, 'completion_tokens': 5, 'estimated_cost_usd': 0.0007}}), "
        "encoding='utf-8'); "
        "print('usage emitted')"
    )
    check = smoke.Check("mcp", "usage sidecar", ".", [sys.executable, "-c", code])

    result = smoke.run_one(PROJECT_ROOT, check)

    assert result.ok is True
    assert result.stdout_tail.splitlines() == ["usage emitted"]
    assert result.input_tokens == 12
    assert result.output_tokens == 5
    assert result.total_tokens == 17
    assert result.cost_usd == 0.0007
    assert result.usage_error is None


def test_json_report_includes_observed_usage_without_empty_fields(tmp_path) -> None:
    smoke = load_smoke_module()
    report_path = tmp_path / "smoke.json"
    no_usage = smoke.Result("workspace", "no usage", ".", "python -V", 0, True, "ok", "")
    with_usage = smoke.Result(
        "mcp",
        "with usage",
        ".",
        "python -V",
        0,
        True,
        "ok",
        "",
        input_tokens=12,
        output_tokens=5,
        total_tokens=17,
        cost_usd=0.0007,
    )

    if hasattr(smoke, "write_json_report"):
        smoke.write_json_report(report_path, [no_usage, with_usage], total_checks=2, complete=True)
    else:
        report_path.write_text(
            json.dumps([smoke.result_payload(no_usage), smoke.result_payload(with_usage)], indent=2),
            encoding="utf-8",
        )

    results = _results_from_report(json.loads(report_path.read_text(encoding="utf-8")))
    assert "input_tokens" not in results[0]
    assert results[1]["input_tokens"] == 12
    assert results[1]["output_tokens"] == 5
    assert results[1]["total_tokens"] == 17
    assert results[1]["cost_usd"] == 0.0007
