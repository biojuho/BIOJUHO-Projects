"""Tests for ops/scripts/verify_observability.py (offline observability contract).

Covers the passing path on the real repository plus each failure assertion by
pointing the verifier's ROOT at a synthetic checkout.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "verify_observability.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_observability", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    # Register before exec so dataclass annotation resolution can find the module.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mod():
    return _load_module()


# --- passing path on the real repo -------------------------------------------

def test_all_checks_pass_on_real_repo(mod):
    results = mod.run_checks()
    failed = [r.check_id for r in results if not r.ok]
    assert not failed, f"unexpected failures: {failed}"
    assert len(results) == 6


def test_report_schema_is_v1_and_consistent(mod):
    report = mod.build_report(mod.run_checks())
    assert report["schema_version"] == 1
    assert report["ok"] is True
    summary = report["summary"]
    assert summary["total"] == len(report["results"])
    assert summary["passed"] + summary["failed"] == summary["total"]
    assert summary["failed"] == 0
    # generated_at must be a parseable timezone-aware timestamp.
    from datetime import datetime

    parsed = datetime.fromisoformat(report["generated_at"])
    assert parsed.tzinfo is not None


def test_json_out_written_atomically(mod, tmp_path):
    out = tmp_path / "evidence.json"
    rc = mod.main(["--json-out", str(out)])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["summary"]["failed"] == 0
    # No temp residue left behind.
    assert not list(tmp_path.glob(".*tmp*"))
    assert not list(tmp_path.glob("*.tmp"))


# --- failure assertions via a synthetic empty checkout -----------------------

def test_missing_contract_files_fail(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    assert mod.check_litellm_config().ok is False
    assert mod.check_compose_profile().ok is False
    assert mod.check_env_example().ok is False
    assert mod.check_healthcheck_probe().ok is False


def test_litellm_config_missing_langfuse_callback_fails(mod, monkeypatch, tmp_path):
    cfg_dir = tmp_path / "ops" / "litellm"
    cfg_dir.mkdir(parents=True)
    # Valid routes but no langfuse success callback.
    (cfg_dir / "config.yaml").write_text(
        "model_list:\n"
        "  - model_name: tier-heavy\n"
        "  - model_name: tier-medium\n"
        "  - model_name: tier-lightweight\n"
        "  - model_name: anthropic-opus\n"
        "  - model_name: anthropic-sonnet\n"
        "  - model_name: anthropic-haiku\n"
        "  - model_name: openai-gpt5\n"
        "  - model_name: gemini-pro\n"
        "  - model_name: gemini-flash\n"
        "  - model_name: grok-4\n"
        "  - model_name: deepseek-chat\n"
        "  - model_name: moonshot-v1\n"
        "litellm_settings:\n"
        "  success_callback: []\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    result = mod.check_litellm_config()
    assert result.ok is False
    assert any("langfuse" in f for f in result.failures)


def test_compose_service_not_profile_gated_fails(mod, monkeypatch, tmp_path):
    (tmp_path / "docker-compose.dev.yml").write_text(
        "services:\n"
        "  clickhouse:\n"
        "    image: clickhouse\n"  # no profiles -> should fail
        "  langfuse-web:\n"
        "    profiles: [observability]\n"
        "  langfuse-worker:\n"
        "    profiles: [observability]\n"
        "  litellm-proxy:\n"
        "    profiles: [observability]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    result = mod.check_compose_profile()
    assert result.ok is False
    assert any("clickhouse" in f for f in result.failures)


def test_env_example_missing_key_fails(mod, monkeypatch, tmp_path):
    (tmp_path / ".env.example").write_text(
        "LITELLM_PROXY_URL=\nLANGFUSE_HOST=\n",  # missing several required keys
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    result = mod.check_env_example()
    assert result.ok is False
    assert any("LANGFUSE_SECRET_KEY" in f for f in result.failures)
