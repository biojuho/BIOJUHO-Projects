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
OPERATOR_CHECKLIST_JSON_PATH = (
    PROJECT_ROOT / "docs" / "reports" / "2026-06" / "EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.json"
)
OPERATOR_CHECKLIST_MARKDOWN_PATH = (
    PROJECT_ROOT / "docs" / "reports" / "2026-06" / "EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.md"
)


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
    hosted = next(
        item for item in handoff["boundaries"] if item["id"] == "hosted_agent_runtime_credentials"
    )
    assert [item["name"] for item in hosted["operator_consent_items"]] == [
        "hosted_agent_toolbox_mcp",
        "hosted_agent_tracing_runtime",
    ]
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
    assert "Consent items: `2`" in markdown
    assert "hosted_agent_toolbox_mcp" in markdown
    assert "CANVA_CLIENT_SECRET=" in env_template
    assert "TELEGRAM_CHAT_ID=" in env_template


def test_unblock_queue_prioritizes_operator_actions() -> None:
    handoff_module = load_module()
    handoff = handoff_module.build_handoff(REGISTRY_PATH, env={})

    queue_ids = [item["boundary_id"] for item in handoff["unblock_queue"]]
    canva = handoff["unblock_queue"][0]
    github = next(item for item in handoff["unblock_queue"] if item["boundary_id"] == "github_source_refresh_rate_limit_token")
    hosted = next(item for item in handoff["unblock_queue"] if item["boundary_id"] == "hosted_agent_runtime_credentials")

    assert queue_ids[0] == "canva_oauth_and_openapi_tool_execution"
    assert queue_ids.index("github_source_refresh_rate_limit_token") < queue_ids.index("hosted_agent_runtime_credentials")
    assert queue_ids.index("otel_collector_endpoint_and_credentials") < queue_ids.index("hosted_agent_runtime_credentials")
    assert canva["rank"] == 1
    assert "CANVA_CLIENT_SECRET" in canva["env_names"]
    assert github["env_names"] == ["GITHUB_TOKEN", "GH_TOKEN"]
    assert "python ops/scripts/github_source_freshness.py" in github["verify_after_unblock"][0]
    assert [item["name"] for item in hosted["operator_consent_items"]] == [
        "hosted_agent_toolbox_mcp",
        "hosted_agent_tracing_runtime",
    ]


def test_env_template_follows_unblock_queue_order() -> None:
    handoff_module = load_module()
    handoff = handoff_module.build_handoff(REGISTRY_PATH, env={})
    env_template = handoff_module.format_env_template(handoff)

    assert "# Queue rank: 1" in env_template
    assert env_template.index("CANVA_CLIENT_SECRET=") < env_template.index("GITHUB_TOKEN=")
    assert env_template.index("GITHUB_TOKEN=") < env_template.index("TELEGRAM_BOT_TOKEN=")
    assert env_template.index("TELEGRAM_CHAT_ID=") < env_template.index("OTEL_EXPORTER_OTLP_ENDPOINT=")
    assert env_template.index("OTEL_EXPORTER_OTLP_ENDPOINT=") < env_template.index("HOSTED_AGENT_RUNTIME_APPROVED=")
    assert env_template.index("HOSTED_AGENT_RUNTIME_APPROVED=") < env_template.index("OPENAI_API_KEY=")


def test_operator_checklist_matches_live_readiness_without_secret_values() -> None:
    handoff_module = load_module()
    handoff = handoff_module.build_handoff(
        REGISTRY_PATH,
        env={
            "CANVA_CLIENT_ID": "client-id-secret-value",
            "GITHUB_TOKEN": "github-token-value",
            "TELEGRAM_BOT_TOKEN": "telegram-token-value",
        },
    )

    checklist = handoff_module.build_operator_checklist(handoff)
    serialized = json.dumps(checklist)
    by_id = {item["boundary_id"]: item for item in checklist["items"]}

    assert checklist["summary"]["blocked"] >= 1
    assert by_id["canva_oauth_and_openapi_tool_execution"]["live_status"] == "blocked_missing_required_env"
    assert by_id["github_source_refresh_rate_limit_token"]["live_status"] == "ready_for_execution"
    assert by_id["hosted_agent_runtime_credentials"]["live_status"] == "blocked_operator_approval"
    assert by_id["hosted_agent_runtime_credentials"]["ready_to_execute"] is False
    assert by_id["hosted_agent_runtime_credentials"]["blocked_reason"] == (
        "missing operator approval marker: HOSTED_AGENT_RUNTIME_APPROVED"
    )
    assert by_id["hosted_agent_runtime_credentials"]["operator_consent_items"][0]["name"] == (
        "hosted_agent_toolbox_mcp"
    )
    assert any(
        step["id"] == "operator_approval_marker"
        for step in by_id["hosted_agent_runtime_credentials"]["checklist"]
    )
    assert any(
        step["id"] == "operator_consent_items" and step["state"] == "blocked"
        for step in by_id["hosted_agent_runtime_credentials"]["checklist"]
    )
    assert "ready_to_execute" in serialized
    assert "client-id-secret-value" not in serialized
    assert "github-token-value" not in serialized
    assert "telegram-token-value" not in serialized


def test_operator_checklist_markdown_is_actionable() -> None:
    handoff_module = load_module()
    checklist = handoff_module.build_operator_checklist(
        handoff_module.build_handoff(REGISTRY_PATH, env={})
    )

    markdown = handoff_module.format_operator_checklist_markdown(checklist)

    assert "External Credential Operator Checklist" in markdown
    assert "Secret values: not emitted" in markdown
    assert "blocked_missing_required_env" in markdown
    assert "blocked_missing_optional_env" in markdown
    assert "blocked_operator_approval" in markdown
    assert "HOSTED_AGENT_RUNTIME_APPROVED" in markdown
    assert "Operator consent items: hosted_agent_toolbox_mcp, hosted_agent_tracing_runtime" in markdown
    assert "cd mcp/canva-mcp && npm run doctor:canva" in markdown


def test_cli_writes_redacted_handoff_package(tmp_path: Path) -> None:
    handoff_module = load_module()
    json_out = tmp_path / "handoff.json"
    markdown_out = tmp_path / "handoff.md"
    env_template_out = tmp_path / "handoff.env.example"
    operator_checklist_json_out = tmp_path / "operator-checklist.json"
    operator_checklist_markdown_out = tmp_path / "operator-checklist.md"

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
            "--operator-checklist-json-out",
            str(operator_checklist_json_out),
            "--operator-checklist-markdown-out",
            str(operator_checklist_markdown_out),
        ]
    )

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    checklist = json.loads(operator_checklist_json_out.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["status"] == "operator_action_required"
    assert payload["missing_required_env_count"] >= 1
    assert checklist["summary"]["next_boundary_id"] == "canva_oauth_and_openapi_tool_execution"
    assert "External Credential Handoff" in markdown_out.read_text(encoding="utf-8")
    assert "CANVA_CLIENT_ID=" in env_template_out.read_text(encoding="utf-8")
    assert "External Credential Operator Checklist" in operator_checklist_markdown_out.read_text(encoding="utf-8")


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
            "--check-operator-checklist-json",
            str(OPERATOR_CHECKLIST_JSON_PATH),
            "--check-operator-checklist-markdown",
            str(OPERATOR_CHECKLIST_MARKDOWN_PATH),
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
