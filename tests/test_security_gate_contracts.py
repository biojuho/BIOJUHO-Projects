"""Security cleanup contract tests for CI gates and documented env settings."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

HIGH_RISK_SECRET_PATTERNS = {
    "openai-api-key": re.compile(r"sk-(?:live|test|proj)-[A-Za-z0-9_-]{20,}"),
    "github-token": re.compile(r"(?:ghp|github_pat)_[A-Za-z0-9_]{20,}"),
    "slack-token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    "aws-access-key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "google-api-key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "private-key-block": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "web3-private-key": re.compile(r"PRIVATE_KEY=0x[0-9a-fA-F]{64}"),
    "gitleaks-license": re.compile(r"GITLEAKS_LICENSE=[A-Za-z0-9._-]{16,}"),
}

TEXT_SCAN_SUFFIXES = {
    ".bat",
    ".cfg",
    ".css",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _tracked_text_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    paths: list[Path] = []
    for item in result.stdout.split(b"\0"):
        if not item:
            continue
        relative_path = item.decode("utf-8")
        if any(relative_path.endswith(suffix) for suffix in TEXT_SCAN_SUFFIXES):
            paths.append(ROOT / relative_path)
    return paths


def test_github_workflows_are_valid_yaml() -> None:
    workflow_paths = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

    assert workflow_paths
    for path in workflow_paths:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict), path


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
    assert "npm audit --omit=dev --audit-level=high" in workflow
    assert "Full npm audit found development dependency findings" in workflow


def test_security_quality_gate_has_pr_comment_permissions() -> None:
    workflow = _read(".github/workflows/security-quality-gate.yml")

    assert re.search(r"^permissions:\n(?:  .+\n)+", workflow, flags=re.MULTILINE) is not None
    assert re.search(r"^\s+issues:\s*write\b", workflow, flags=re.MULTILINE)
    assert re.search(r"^\s+pull-requests:\s*write\b", workflow, flags=re.MULTILINE)
    assert "continue-on-error: true" in workflow


def test_qa_review_scans_changed_python_files_only() -> None:
    workflow = _read(".github/workflows/security-quality-gate.yml")

    assert "changed-python-files.txt" in workflow
    assert "ruff check --select=E,F,W,I,N,UP,S,B" in workflow
    assert '"${PY_FILES[@]}"' in workflow
    assert 'bandit "${PY_FILES[@]}" -f json -o bandit-report.json -ll' in workflow
    assert "ruff check --select=E,F,W,I,N,UP,S,B --output-format=github ." not in workflow
    assert "bandit -r ." not in workflow


def test_qa_review_excludes_pytest_assert_rule_in_test_files() -> None:
    """S101 (assert) is the standard pytest pattern — must be ignored in test files."""
    workflow = _read(".github/workflows/security-quality-gate.yml")

    assert "--per-file-ignores='tests/**:S101'" in workflow
    assert "--per-file-ignores='**/test_*.py:S101'" in workflow
    assert "--per-file-ignores='**/conftest.py:S101'" in workflow


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


def test_security_quality_gate_hard_fails_workspace_smoke_contracts() -> None:
    workflow = _read(".github/workflows/security-quality-gate.yml")

    assert "uv run python -m pytest tests/test_workspace_smoke.py -q --tb=short || true" not in workflow
    assert "uv pip install --system -e" not in workflow
    assert "uv run --with pytest python -m pytest tests/test_workspace_smoke.py -q --tb=short" in workflow
    assert "Smoke Test: FAILED (non-blocking)" not in workflow
    assert "Smoke tests failed. Fix workspace quality gate regressions before merging." in workflow


def test_workspace_smoke_workflow_runs_canonical_full_gate() -> None:
    workflow = _read(".github/workflows/workspace-smoke.yml")

    assert "uv run python ops/scripts/run_workspace_smoke.py --scope all --json-out smoke-all.json" in workflow
    assert (
        "uv run pytest tests/test_workspace_regressions.py tests/test_workspace_smoke.py "
        "tests/test_auto_research_status.py -q --tb=short"
    ) in workflow
    assert "actions/upload-artifact@" in workflow
    assert "name: workspace-smoke-report" in workflow
    assert "path: smoke-all.json" in workflow
    assert "Smoke report was not generated." in workflow
    assert "Failed: {failed}" in workflow
    assert "run_workspace_smoke.py --scope all" not in workflow.replace(
        "uv run python ops/scripts/run_workspace_smoke.py --scope all --json-out smoke-all.json",
        "",
    )
    assert "run_workspace_smoke.py --scope all --json-out smoke-all.json || true" not in workflow


def test_agriguard_qr_kpi_release_workflow_archives_signed_evidence() -> None:
    workflow = _read(".github/workflows/agriguard-qr-kpi-release-evidence.yml")
    parsed = yaml.safe_load(workflow)
    jobs = parsed["jobs"]
    fast_job = jobs["release-evidence-fast"]
    postgres_job = jobs["release-evidence-postgres"]
    fast_job_text = yaml.safe_dump(fast_job, sort_keys=False)
    postgres_job_text = yaml.safe_dump(postgres_job, sort_keys=False)

    assert "workflow_dispatch:" in workflow
    assert "AGRIGUARD_QR_KPI_MANIFEST_HMAC_KEY: ${{ secrets.AGRIGUARD_QR_KPI_MANIFEST_HMAC_KEY }}" in workflow
    assert "run_qr_kpi_fixture_evidence.py" in workflow
    assert "include_postgres:" in workflow
    assert fast_job["if"] == "${{ !inputs.include_postgres }}"
    assert postgres_job["if"] == "${{ inputs.include_postgres }}"
    assert fast_job["environment"] == "automation-ops"
    assert postgres_job["environment"] == "automation-ops"
    assert fast_job["env"]["AGRIGUARD_QR_KPI_MANIFEST_HMAC_KEY"] == "${{ secrets.AGRIGUARD_QR_KPI_MANIFEST_HMAC_KEY }}"
    assert postgres_job["env"]["AGRIGUARD_QR_KPI_MANIFEST_HMAC_KEY"] == "${{ secrets.AGRIGUARD_QR_KPI_MANIFEST_HMAC_KEY }}"
    assert "services" not in fast_job
    assert "postgres" in postgres_job["services"]
    assert (
        "image: postgres:17@sha256:0027bef26712baaee437a4ea48fdf3d2d2e2bc5f0d81615374408ca320f3c7e3"
        in postgres_job_text
    )
    assert "--health-cmd pg_isready" in postgres_job_text
    assert "uv run python apps/AgriGuard/backend/scripts/run_migrations.py" in postgres_job_text
    assert "--pg-load" in workflow
    assert "--pg-analyze" in workflow
    assert "--pg-benchmark" in workflow
    assert "--live-explain" in workflow
    assert "--require-index-use" in workflow
    assert "--pg-load" not in fast_job_text
    assert "--pg-analyze" not in fast_job_text
    assert "--pg-benchmark" not in fast_job_text
    assert "--live-explain" not in fast_job_text
    assert "run_migrations.py" not in fast_job_text
    assert "--history-jsonl-out \"var/${QR_KPI_OUTPUT_PREFIX}.history.jsonl\"" in workflow
    assert "run_qr_kpi_release_evidence.py" in workflow
    assert "--release-profile \"$QR_KPI_RELEASE_PROFILE\"" in workflow
    assert "--history-jsonl \"var/${QR_KPI_OUTPUT_PREFIX}.history.jsonl\"" in workflow
    assert "--skip-signature" in workflow
    summary_renderer = "apps/AgriGuard/backend/scripts/render_qr_kpi_release_evidence_summary.py"
    post_download_verifier = "apps/AgriGuard/backend/scripts/verify_qr_kpi_release_evidence_directory.py"
    assert workflow.count(summary_renderer) == 4
    assert summary_renderer in fast_job_text
    assert summary_renderer in postgres_job_text
    for job in (fast_job, postgres_job):
        named_steps = {step["name"]: step for step in job["steps"] if "name" in step}
        evidence_summary = named_steps["Append evidence summary"]["run"]
        final_consumer_summary = named_steps["Append final consumer validation summary"]["run"]
        post_download_handoff = named_steps["Verify post-download evidence handoff"]["run"]

        assert summary_renderer in evidence_summary
        assert summary_renderer in final_consumer_summary
        assert "--metadata-json-out \"var/${QR_KPI_OUTPUT_PREFIX}.summary-metadata.json\"" in evidence_summary
        assert "--metadata-json-out" not in final_consumer_summary
        assert "--final-consumer-summary-only" not in evidence_summary
        assert "--final-consumer-summary-only" in final_consumer_summary
        assert post_download_verifier in post_download_handoff
        assert "--evidence-dir var" in post_download_handoff
        assert "--json-out \"var/${QR_KPI_OUTPUT_PREFIX}.post-download-verification.json\"" in post_download_handoff
        assert "--markdown-out \"var/${QR_KPI_OUTPUT_PREFIX}.post-download-verification.md\"" in post_download_handoff
    assert workflow.count("--metadata-json-out \"var/${QR_KPI_OUTPUT_PREFIX}.summary-metadata.json\"") == 2
    metadata_validator = "apps/AgriGuard/backend/scripts/validate_qr_kpi_release_summary_metadata.py"
    assert workflow.count(metadata_validator) == 2
    assert metadata_validator in fast_job_text
    assert metadata_validator in postgres_job_text
    assert workflow.count("--json-out \"var/${QR_KPI_OUTPUT_PREFIX}.summary-metadata.validation.json\"") == 2
    metadata_validation_verifier = (
        "apps/AgriGuard/backend/scripts/verify_qr_kpi_release_summary_metadata_validation.py"
    )
    assert workflow.count(metadata_validation_verifier) == 2
    assert metadata_validation_verifier in fast_job_text
    assert metadata_validation_verifier in postgres_job_text
    assert workflow.count("--json-out \"var/${QR_KPI_OUTPUT_PREFIX}.summary-metadata.validation.audit.json\"") == 2
    metadata_readiness_gate = "apps/AgriGuard/backend/scripts/check_qr_kpi_release_summary_metadata_ready.py"
    assert workflow.count(metadata_readiness_gate) == 2
    assert metadata_readiness_gate in fast_job_text
    assert metadata_readiness_gate in postgres_job_text
    assert workflow.count("--json-out \"var/${QR_KPI_OUTPUT_PREFIX}.summary-metadata.ready.json\"") == 2
    assert workflow.count(post_download_verifier) == 2
    assert post_download_verifier in fast_job_text
    assert post_download_verifier in postgres_job_text
    assert workflow.count("Verify post-download evidence handoff") == 2
    assert workflow.count("--json-out \"var/${QR_KPI_OUTPUT_PREFIX}.post-download-verification.json\"") == 2
    assert workflow.count("--markdown-out \"var/${QR_KPI_OUTPUT_PREFIX}.post-download-verification.md\"") == 2
    post_download_command = (
        "apps/AgriGuard/backend/scripts/verify_qr_kpi_release_evidence_directory.py \\\n"
        "            --evidence-dir var \\\n"
        "            --output-prefix \"$QR_KPI_OUTPUT_PREFIX\" \\\n"
        "            --base-dir ."
    )
    assert workflow.count(post_download_command) == 2
    post_download_summary = "apps/AgriGuard/backend/scripts/summarize_qr_kpi_post_download_verification.py"
    assert workflow.count(post_download_summary) == 2
    assert post_download_summary in fast_job_text
    assert post_download_summary in postgres_job_text
    assert workflow.count("Append post-download verification summary") == 2
    assert workflow.count("\"var/${QR_KPI_OUTPUT_PREFIX}.post-download-verification.json\"") >= 4
    assert workflow.count("--if-exists") == 2
    assert fast_job_text.index(metadata_readiness_gate) < fast_job_text.index(post_download_verifier)
    assert postgres_job_text.index(metadata_readiness_gate) < postgres_job_text.index(post_download_verifier)
    assert fast_job_text.index(post_download_verifier) < fast_job_text.index(post_download_summary)
    assert postgres_job_text.index(post_download_verifier) < postgres_job_text.index(post_download_summary)
    assert fast_job_text.index(post_download_summary) < fast_job_text.index("actions/upload-artifact@")
    assert postgres_job_text.index(post_download_summary) < postgres_job_text.index("actions/upload-artifact@")
    assert workflow.count("--artifact-name \"agriguard-qr-kpi-release-evidence-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}\"") == 2
    assert workflow.count("--artifact-retention-days 30") == 2
    assert workflow.count("--fail-on-manifest-coverage") == 2
    assert "--fail-on-external-manifest-inputs" not in workflow
    assert "summary.write(\"## AgriGuard QR KPI Release Evidence" not in workflow
    assert "actions/upload-artifact@330a01c490aca151604b8cf639adc76d48f6c5d4" in workflow
    assert "id: release-names" in workflow
    assert "output_file.write(f\"output_prefix={output_prefix}\\n\")" in workflow
    assert "path: |\n            var/${{ steps.release-names.outputs.output_prefix }}.*" in workflow
    assert "if-no-files-found: error" in workflow
    assert "persist-credentials: false" in workflow


def test_desci_platform_quality_workflow_covers_all_workspace_scopes() -> None:
    workflow = _read(".github/workflows/desci-platform-quality.yml")

    assert "scope: [workspace, desci, agriguard, mcp, getdaytrends, cie]" in workflow
    for watched_path in (
        "automation/content-intelligence/**",
        "mcp/canva-mcp/**",
        "mcp/desci-research-mcp/**",
        "mcp/telegram-mcp/**",
        "ops/scripts/release_approval_check.py",
        "ops/scripts/run_release_approval_gate_machine.ps1",
        "ops/scripts/write_release_approval_handoff_artifact_index.py",
    ):
        assert watched_path in workflow

    assert "npm ci --prefix apps/desci-platform/contracts" in workflow
    assert "npm ci --prefix apps/AgriGuard/contracts" in workflow
    assert "npm ci --prefix mcp/canva-mcp" in workflow
    assert "run_workspace_smoke.py --scope \"$MATRIX_SCOPE\"" in workflow
    assert "workspace-smoke-${{ matrix.scope }}" in workflow
    assert "smoke-${{ matrix.scope }}.json" in workflow


def test_desci_platform_quality_workflow_has_manual_release_approval_handoff() -> None:
    workflow = _read(".github/workflows/desci-platform-quality.yml")
    artifact_index_script = _read("ops/scripts/write_release_approval_handoff_artifact_index.py")

    assert "release_approval_handoff:" in workflow
    assert "type: boolean" in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.release_approval_handoff" in workflow
    assert "Release Approval Handoff" in workflow
    assert "run_release_approval_gate_machine.ps1" in workflow
    assert "-PythonCommand \"uv run python\"" in workflow
    assert "RELEASE_APPROVAL_OPERATOR_HANDOFF_MACHINE.md" in workflow
    assert "Write release approval handoff artifact index" in workflow
    assert "write_release_approval_handoff_artifact_index.py" in workflow
    assert "var/release-approval-handoff-artifact-index-machine.json" in workflow
    assert "var/release-approval-handoff-artifact-index-summary.md" in workflow
    assert "--markdown-summary-out var/release-approval-handoff-artifact-index-summary.md" in workflow
    assert "--append-github-step-summary" in workflow
    assert "first_decision_artifact" in artifact_index_script
    assert "upload_before_fail_closed" in artifact_index_script
    assert "all_required_artifacts_present" in artifact_index_script
    assert "missing_artifact_count" in artifact_index_script
    assert "sha256_file" in artifact_index_script
    assert "sha256_short" in artifact_index_script
    assert "render_markdown_summary" in artifact_index_script
    assert "GITHUB_STEP_SUMMARY" in artifact_index_script
    assert "WRAPPER_EXIT_CODE" in workflow
    assert "RELEASE_GATE_HANDOFF_EXIT_CODE" in workflow
    assert "var/workspace-smoke-workspace-release-approval-machine.json" in workflow
    assert "var/release-approval-check-machine.json" in workflow
    assert "desci-release-gate-release-approval-handoff-machine.json" in workflow
    assert "Validate handoff through DeSci release gate" in workflow
    assert "--release-approval-handoff ../../docs/reports/2026-06/RELEASE_APPROVAL_OPERATOR_HANDOFF_MACHINE.md" in workflow
    assert "--json-out var/desci-release-gate-release-approval-handoff-machine.json" in workflow
    assert "steps.release-approval-wrapper.outputs.exit_code" in workflow
    assert "steps.desci-release-gate-handoff.outputs.exit_code" in workflow
    assert "Upload release approval handoff artifacts" in workflow
    assert "Fail closed on release approval handoff errors" in workflow
    assert "var/session-bootstrap-release-approval-machine.json" in workflow
    assert "release-approval-handoff-${{ github.run_id }}-${{ github.run_attempt }}" in workflow
    assert "if-no-files-found: error" in workflow
    assert "retention-days: 30" in workflow
    assert workflow.index("Write release approval handoff artifact index") < workflow.index(
        "Upload release approval handoff artifacts"
    )
    assert workflow.index("Upload release approval handoff artifacts") < workflow.index(
        "Fail closed on release approval handoff errors"
    )
    assert "continue-on-error: true" not in workflow


def test_tracked_text_files_do_not_contain_live_secret_patterns() -> None:
    findings: list[str] = []
    for path in _tracked_text_files():
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative_path = path.relative_to(ROOT).as_posix()
        for name, pattern in HIGH_RISK_SECRET_PATTERNS.items():
            for match in pattern.finditer(text):
                line_number = text.count("\n", 0, match.start()) + 1
                findings.append(f"{relative_path}:{line_number}: {name}")

    assert findings == []


def test_security_env_examples_document_fail_closed_defaults() -> None:
    agriguard = _read("apps/AgriGuard/backend/.env.example")
    assert "ADMIN_PASSWORD=" in agriguard
    assert "ADMIN_PASSWORD=change_me" not in agriguard
    assert "ALLOW_TEST_BYPASS=false" in agriguard

    for path in [
        "apps/AgriGuard/backend/.env.example",
        "apps/desci-platform/.env.example",
        "apps/desci-platform/backend/.env.example",
    ]:
        env_example = _read(path)
        assert "# ALLOW_DEV_AUTH_FALLBACK=true" in env_example
        assert (
            re.search(
                r"^ALLOW_DEV_AUTH_FALLBACK\s*=\s*true\b",
                env_example,
                flags=re.MULTILINE,
            )
            is None
        )

    dailynews = _read("automation/DailyNews/.env.example")
    assert "SUBSCRIBE_ALLOWED_ORIGINS=" in dailynews
    assert "SUBSCRIBE_RATE_LIMIT_PER_MINUTE=60" in dailynews

    canva = _read("mcp/canva-mcp/.env.example")
    assert "CANVA_MCP_ALLOWED_ORIGINS=" in canva


def test_security_env_names_are_used_by_runtime_code() -> None:
    source_env_pairs = [
        ("apps/AgriGuard/backend/admin.py", "ADMIN_PASSWORD"),
        ("apps/AgriGuard/backend/auth.py", "ALLOW_DEV_AUTH_FALLBACK"),
        ("apps/desci-platform/backend/services/auth.py", "ALLOW_DEV_AUTH_FALLBACK"),
        (
            "automation/DailyNews/src/antigravity_mcp/apps/subscribe_api.py",
            "SUBSCRIBE_ALLOWED_ORIGINS",
        ),
        ("mcp/canva-mcp/src/server/server.ts", "CANVA_MCP_ALLOWED_ORIGINS"),
        ("mcp/canva-mcp/src/server/worker.ts", "CANVA_MCP_ALLOWED_ORIGINS"),
    ]

    for source, env_name in source_env_pairs:
        assert env_name in _read(source)
