"""Security cleanup contract tests for CI gates and documented env settings."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_security_quality_gate_does_not_mask_hard_gate_failures() -> None:
    workflow = _read(".github/workflows/security-quality-gate.yml")

    masked_hard_gate_patterns = [
        r"^\s*pip-audit\b.*\|\|\s*true\b",
        r"^\s*npm audit\b.*\|\|\s*true\b",
        r"^\s*ruff check\b.*\|\|\s*true\b",
        r"^\s*bandit\b.*\|\|\s*true\b",
    ]
    for pattern in masked_hard_gate_patterns:
        assert re.search(pattern, workflow, flags=re.MULTILINE) is None

    assert "Dependency Audit: FAILED (non-blocking)" not in workflow
    assert "Dependency audit failed. Fix vulnerable packages before merging." in workflow


def test_security_quality_gate_waits_for_expected_jobs() -> None:
    workflow = _read(".github/workflows/security-quality-gate.yml")
    match = re.search(r"needs:\s*\[([^\]]+)\]", workflow)

    assert match is not None
    needs = {item.strip() for item in match.group(1).split(",")}
    assert {
        "secret-scan",
        "dependency-scan",
        "security-contracts",
        "qa-review",
        "smoke-test",
    } <= needs
    assert "Security contract tests failed." in workflow


def test_security_env_examples_document_fail_closed_defaults() -> None:
    agriguard = _read("apps/AgriGuard/backend/.env.example")
    assert "ADMIN_PASSWORD=" in agriguard
    assert "ADMIN_PASSWORD=change_me" not in agriguard
    assert "ALLOW_TEST_BYPASS=false" in agriguard

    for path in [
        "apps/AgriGuard/backend/.env.example",
        "apps/desci-platform/.env.example",
        "apps/desci-platform/biolinker/.env.example",
    ]:
        env_example = _read(path)
        assert "# ALLOW_DEV_AUTH_FALLBACK=true" in env_example
        assert re.search(
            r"^ALLOW_DEV_AUTH_FALLBACK\s*=\s*true\b",
            env_example,
            flags=re.MULTILINE,
        ) is None

    dailynews = _read("automation/DailyNews/.env.example")
    assert "SUBSCRIBE_ALLOWED_ORIGINS=" in dailynews
    assert "SUBSCRIBE_RATE_LIMIT_PER_MINUTE=60" in dailynews

    canva = _read("mcp/canva-mcp/.env.example")
    assert "CANVA_MCP_ALLOWED_ORIGINS=" in canva


def test_security_env_names_are_used_by_runtime_code() -> None:
    source_env_pairs = [
        ("apps/AgriGuard/backend/admin.py", "ADMIN_PASSWORD"),
        ("apps/AgriGuard/backend/auth.py", "ALLOW_DEV_AUTH_FALLBACK"),
        ("apps/desci-platform/backend/auth.py", "ALLOW_DEV_AUTH_FALLBACK"),
        ("apps/desci-platform/biolinker/services/auth.py", "ALLOW_DEV_AUTH_FALLBACK"),
        (
            "automation/DailyNews/src/antigravity_mcp/apps/subscribe_api.py",
            "SUBSCRIBE_ALLOWED_ORIGINS",
        ),
        ("mcp/canva-mcp/src/server/server.ts", "CANVA_MCP_ALLOWED_ORIGINS"),
        ("mcp/canva-mcp/src/server/worker.ts", "CANVA_MCP_ALLOWED_ORIGINS"),
    ]

    for source, env_name in source_env_pairs:
        assert env_name in _read(source)
