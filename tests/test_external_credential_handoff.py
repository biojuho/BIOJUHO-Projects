from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "external_credential_handoff.py"
REGISTRY_PATH = PROJECT_ROOT / "ops" / "references" / "external_credential_boundaries.json"


def load_module():
    spec = importlib.util.spec_from_file_location("external_credential_handoff", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_handoff_lists_required_env_without_secret_values() -> None:
    handoff_module = load_module()

    handoff = handoff_module.build_handoff(
        REGISTRY_PATH,
        env={
            "CANVA_CLIENT_ID": "client-id-secret-value",
            "CANVA_CLIENT_SECRET": "client-secret-value",
            "TELEGRAM_BOT_TOKEN": "telegram-token-value",
        },
    )

    serialized = json.dumps(handoff)
    assert handoff["boundary_count"] >= 5
    assert "CANVA_CLIENT_ID" in {item["name"] for item in handoff["required_env"]}
    assert "verification_sequence" in handoff
    assert "client-id-secret-value" not in serialized
    assert "client-secret-value" not in serialized
    assert "telegram-token-value" not in serialized


def test_markdown_and_env_template_are_operator_actionable() -> None:
    handoff_module = load_module()
    handoff = handoff_module.build_handoff(REGISTRY_PATH, env={})

    markdown = handoff_module.format_markdown(handoff)
    env_template = handoff_module.format_env_template(handoff)

    assert "External Credential Handoff" in markdown
    assert "Secret values: not emitted" in markdown
    assert "cd mcp/canva-mcp && npm run doctor:canva" in markdown
    assert "CANVA_CLIENT_SECRET=" in env_template
    assert "TELEGRAM_CHAT_ID=" in env_template


def test_cli_writes_redacted_handoff_package(tmp_path: Path) -> None:
    handoff_module = load_module()
    json_out = tmp_path / "handoff.json"
    markdown_out = tmp_path / "handoff.md"
    env_template_out = tmp_path / "handoff.env.example"

    exit_code = handoff_module.main(
        [
            "--registry",
            str(REGISTRY_PATH),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
            "--env-template-out",
            str(env_template_out),
        ]
    )

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["status"] == "operator_action_required"
    assert payload["missing_required_env_count"] >= 1
    assert "External Credential Handoff" in markdown_out.read_text(encoding="utf-8")
    assert "CANVA_CLIENT_ID=" in env_template_out.read_text(encoding="utf-8")
