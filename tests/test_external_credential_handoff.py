from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "external_credential_handoff.py"
REGISTRY_PATH = PROJECT_ROOT / "ops" / "references" / "external_credential_boundaries.json"
HANDOFF_JSON_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.json"
HANDOFF_MARKDOWN_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.md"
HANDOFF_ENV_TEMPLATE_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.env.example"


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
    assert "unblock_queue" in handoff
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
    assert "Prioritized Unblock Queue" in markdown
    assert "cd mcp/canva-mcp && npm run doctor:canva" in markdown
    assert "mcp_otel_collector_handoff.py" in markdown
    assert "CANVA_CLIENT_SECRET=" in env_template
    assert "TELEGRAM_CHAT_ID=" in env_template


def test_unblock_queue_prioritizes_operator_actions() -> None:
    handoff_module = load_module()
    handoff = handoff_module.build_handoff(REGISTRY_PATH, env={})

    queue_ids = [item["boundary_id"] for item in handoff["unblock_queue"]]
    canva = handoff["unblock_queue"][0]
    github = next(item for item in handoff["unblock_queue"] if item["boundary_id"] == "github_source_refresh_rate_limit_token")

    assert queue_ids[0] == "canva_oauth_and_openapi_tool_execution"
    assert queue_ids.index("github_source_refresh_rate_limit_token") < queue_ids.index("hosted_agent_runtime_credentials")
    assert queue_ids.index("otel_collector_endpoint_and_credentials") < queue_ids.index("hosted_agent_runtime_credentials")
    assert canva["rank"] == 1
    assert "CANVA_CLIENT_SECRET" in canva["env_names"]
    assert github["env_names"] == ["GITHUB_TOKEN", "GH_TOKEN"]
    assert "python ops/scripts/github_source_freshness.py" in github["verify_after_unblock"][0]


def test_env_template_follows_unblock_queue_order() -> None:
    handoff_module = load_module()
    handoff = handoff_module.build_handoff(REGISTRY_PATH, env={})
    env_template = handoff_module.format_env_template(handoff)

    assert "# Queue rank: 1" in env_template
    assert env_template.index("CANVA_CLIENT_SECRET=") < env_template.index("GITHUB_TOKEN=")
    assert env_template.index("GITHUB_TOKEN=") < env_template.index("TELEGRAM_BOT_TOKEN=")
    assert env_template.index("TELEGRAM_CHAT_ID=") < env_template.index("OTEL_EXPORTER_OTLP_ENDPOINT=")
    assert env_template.index("OTEL_EXPORTER_OTLP_ENDPOINT=") < env_template.index("OPENAI_API_KEY=")


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


def test_checked_in_handoff_artifacts_match_registry() -> None:
    handoff_module = load_module()

    exit_code = handoff_module.main(
        [
            "--registry",
            str(REGISTRY_PATH),
            "--check-json",
            str(HANDOFF_JSON_PATH),
            "--check-markdown",
            str(HANDOFF_MARKDOWN_PATH),
            "--check-env-template",
            str(HANDOFF_ENV_TEMPLATE_PATH),
        ]
    )

    assert exit_code == 0


def test_cli_check_rejects_stale_markdown(tmp_path: Path) -> None:
    handoff_module = load_module()
    stale_markdown = tmp_path / "stale.md"
    stale_markdown.write_text("# stale handoff\n", encoding="utf-8")

    exit_code = handoff_module.main(
        [
            "--registry",
            str(REGISTRY_PATH),
            "--check-markdown",
            str(stale_markdown),
        ]
    )

    assert exit_code == 1
