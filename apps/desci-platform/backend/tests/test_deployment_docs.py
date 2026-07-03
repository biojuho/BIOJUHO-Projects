from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_operator_json_outputs_use_shared_atomic_writer() -> None:
    script_paths = [
        PROJECT_ROOT / "scripts" / "env_doctor.py",
        PROJECT_ROOT / "scripts" / "deploy_readiness.py",
        PROJECT_ROOT / "scripts" / "product_smoke.py",
        PROJECT_ROOT / "scripts" / "browser_smoke.py",
        PROJECT_ROOT / "scripts" / "release_gate.py",
        PROJECT_ROOT / "backend" / "scripts" / "ab_test_matching.py",
    ]

    helper = (PROJECT_ROOT / "scripts" / "evidence_io.py").read_text(encoding="utf-8")
    assert "def write_json_atomic" in helper
    assert ".tmp" in helper
    assert ".replace(" in helper

    for script_path in script_paths:
        source = script_path.read_text(encoding="utf-8")
        assert "--json-out" in source
        assert "from evidence_io import write_json_atomic" in source
        assert "write_json_atomic(" in source


def test_deployment_guide_names_live_contracts_and_preflight_commands() -> None:
    guide = (PROJECT_ROOT / "DEPLOYMENT_GUIDE.md").read_text(encoding="utf-8")
    package_json = (PROJECT_ROOT / "contracts" / "package.json").read_text(encoding="utf-8")

    for contract_name in ("DeSciToken", "ResearchPaperNFT", "DeSciDAO"):
        assert contract_name in guide

    assert "DSCIToken" not in guide
    assert "npm run deploy:amoy" in guide
    assert "deploy:amoy" in package_json
    assert "python scripts/deploy_readiness.py --target all" in guide
    assert "--json-out ../../var/desci-deploy-readiness-production.json" in guide
    assert "python scripts/deploy_readiness.py --target github" in guide
    for variable in ("VITE_WALLET_CHAIN_ID", "VITE_DSCI_TOKEN_ADDRESS", "VITE_RESEARCH_PAPER_NFT_ADDRESS"):
        assert variable in guide


def test_operations_runbook_tracks_release_gate_external_readiness() -> None:
    runbook = (PROJECT_ROOT / "OPERATIONS_RUNBOOK.md").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "DEPLOYMENT_GUIDE.md").read_text(encoding="utf-8")
    release_gate = (PROJECT_ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")
    env_doctor = (PROJECT_ROOT / "scripts" / "env_doctor.py").read_text(encoding="utf-8")
    deploy_readiness = (PROJECT_ROOT / "scripts" / "deploy_readiness.py").read_text(encoding="utf-8")

    for option in (
        "--external-readiness",
        "--external-target",
        "--external-evidence-dir",
        "--env-evidence-dir",
        "--env-file",
        "--json-out",
    ):
        assert option in release_gate
        assert option in runbook
        assert option in readme
        assert option in guide

    for target in ("railway", "vercel", "amoy", "github"):
        assert f"`--external-target {target}`" in runbook

    assert "python scripts/deploy_readiness.py --target all" in runbook
    assert "--json-out ../../var/desci-deploy-readiness-production.json" in runbook
    assert "desci-env-doctor-release-gate.json" in release_gate
    assert "desci-env-doctor-release-gate.json" in runbook
    assert "desci-env-doctor-release-gate.json" in readme
    assert "desci-env-doctor-release-gate.json" in guide
    assert "desci-deploy-readiness-release-gate.json" in release_gate
    assert "desci-deploy-readiness-release-gate.json" in runbook
    assert "desci-deploy-readiness-release-gate.json" in readme
    assert "desci-deploy-readiness-release-gate.json" in guide
    for field in ("schema_version", "generated_at"):
        assert field in env_doctor
        assert field in deploy_readiness
        assert field in runbook
        assert field in readme
        assert field in guide
    for field in ("sources", "env_files", "include_process_env"):
        assert field in env_doctor
        assert field in deploy_readiness
        assert field in runbook
        assert field in readme
        assert field in guide
    for field in ("VITE_WALLET_CHAIN_ID", "VITE_DSCI_TOKEN_ADDRESS", "VITE_RESEARCH_PAPER_NFT_ADDRESS", "DESCI_FRONTEND_URL"):
        assert field in env_doctor
        assert field in deploy_readiness
        assert field in runbook
        assert field in readme
        assert field in guide


def test_operations_docs_track_release_gate_parent_timeouts() -> None:
    runbook = (PROJECT_ROOT / "OPERATIONS_RUNBOOK.md").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "DEPLOYMENT_GUIDE.md").read_text(encoding="utf-8")
    release_gate = (PROJECT_ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")

    for option in (
        "--backend-test-timeout",
        "--contract-step-timeout",
        "--frontend-step-timeout",
        "--frontend-test-timeout",
        "--preflight-step-timeout",
        "--runtime-smoke-timeout",
    ):
        assert option in release_gate
        assert option in runbook
        assert option in readme
        assert option in guide

    for step in (
        "env-doctor",
        "deploy-readiness",
        "compose-config",
        "backend-tests",
        "frontend-lint",
        "frontend-typecheck",
        "frontend-build",
        "frontend-bundle",
        "frontend-tests",
        "product-smoke",
        "browser-smoke",
    ):
        assert step in release_gate
        assert step in runbook
        assert step in readme
        assert step in guide
    for step in ("contracts-build", "contracts-tests", "contracts-deploy-core", "contracts-deploy-nft"):
        assert step in release_gate
    for document in (runbook, readme, guide):
        assert "Contract build/test/deploy steps" in document.replace("\n", " ")

    assert "DEFAULT_BACKEND_TEST_TIMEOUT_SECONDS = 600.0" in release_gate
    assert "DEFAULT_CONTRACT_STEP_TIMEOUT_SECONDS = 600.0" in release_gate
    assert "DEFAULT_FRONTEND_STEP_TIMEOUT_SECONDS = 600.0" in release_gate
    assert "DEFAULT_FRONTEND_TEST_TIMEOUT_SECONDS = 600.0" in release_gate
    assert "DEFAULT_PREFLIGHT_STEP_TIMEOUT_SECONDS = 600.0" in release_gate
    assert "DEFAULT_RUNTIME_SMOKE_TIMEOUT_SECONDS = 600.0" in release_gate
    assert "DESCI_VITEST_TIMEOUT_MS" in release_gate
    assert "timeout_seconds" in release_gate
    for document in (runbook, readme, guide):
        normalized_document = document.replace("\n", " ")
        assert "600-second default" in document
        assert "return code `124`" in normalized_document
        assert "command_argv" in document
        assert "timeout_seconds" in document
        assert "shorter child timeout" in normalized_document
        assert "Runtime `product-smoke` and `browser-smoke` steps" in normalized_document
        assert "Use parent timeout options with `0`" in normalized_document
        assert "`--runtime-browser-timeout` is a child browser-smoke timeout" in normalized_document
        assert "Use any timeout option with `0`" not in normalized_document


def test_operations_docs_track_release_approval_handoff_summary() -> None:
    runbook = (PROJECT_ROOT / "OPERATIONS_RUNBOOK.md").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "DEPLOYMENT_GUIDE.md").read_text(encoding="utf-8")
    release_gate = (PROJECT_ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")

    for marker in (
        "--release-approval-handoff",
        "release_approval_handoff_summary",
        "release-approval-handoff",
        "ready_for_job_summary",
        "missing_sections",
        "unsafe_marker_count",
    ):
        assert marker in release_gate
        assert marker in runbook
        assert marker in readme
        assert marker in guide

    for document in (runbook, readme, guide):
        normalized_document = document.replace("\n", " ")
        assert "RELEASE_APPROVAL_OPERATOR_HANDOFF" in document
        assert "RELEASE_APPROVAL_OPERATOR_HANDOFF_MACHINE.md" in document
        assert "GITHUB_STEP_SUMMARY" in document
        assert "var/release-approval-handoff-artifact-index-machine.json" in document
        assert "var/release-approval-handoff-artifact-index-summary.md" in document
        assert "var/desci-release-gate-release-approval-handoff-machine.json" in document
        assert "var/release-approval-check-machine.json" in document
        assert "var/session-bootstrap-release-approval-machine.json" in document
        assert "var/workspace-smoke-workspace-release-approval-machine.json" in document
        assert "upload_before_fail_closed" in document
        assert "all_required_artifacts_present" in document
        assert "missing_artifact_count" in document
        assert "missing_artifacts" in document
        assert "sha256" in document
        assert "artifact-index summary" in document
        assert "if-no-files-found: error" in document
        assert "retention-days: 30" in document
        assert "fails closed" in normalized_document
        assert "does not make expected external blockers pass" in normalized_document
        assert "first inspect `var/desci-release-gate-release-approval-handoff-machine.json`" in normalized_document
        assert "artifact upload runs before the final fail-closed step" in normalized_document


def test_operations_runbook_tracks_release_gate_runtime_smoke() -> None:
    runbook = (PROJECT_ROOT / "OPERATIONS_RUNBOOK.md").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "DEPLOYMENT_GUIDE.md").read_text(encoding="utf-8")
    api_spec = (PROJECT_ROOT / "API_SPEC.md").read_text(encoding="utf-8")
    release_gate = (PROJECT_ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")
    product_smoke = (PROJECT_ROOT / "scripts" / "product_smoke.py").read_text(encoding="utf-8")
    browser_smoke = (PROJECT_ROOT / "scripts" / "browser_smoke.py").read_text(encoding="utf-8")

    for option in (
        "--runtime-smoke",
        "--runtime-smoke-strict-ready",
        "--runtime-api",
        "--runtime-frontend",
        "--runtime-evidence-dir",
        "--runtime-smoke-step",
        "--runtime-browser-trace-on-failure-dir",
        "--runtime-browser-only-check",
        "--runtime-browser-timeout",
    ):
        assert option in release_gate
        assert option in runbook
        assert option in readme
        assert option in guide

    assert "desci-product-smoke-release-gate.json" in release_gate
    assert "desci-browser-smoke-release-gate.json" in release_gate
    assert "artifact_summary" in release_gate
    assert "artifact_summary" in runbook
    assert "artifact_summary" in readme
    assert "artifact_summary" in guide
    assert "python_command" in release_gate
    assert "python_command" in runbook
    assert "python_command" in readme
    assert "python_command" in guide
    assert "command_argv" in release_gate
    assert "command_argv" in runbook
    assert "command_argv" in readme
    assert "command_argv" in guide
    assert "launch_handoff" in release_gate
    assert "launch_handoff" in product_smoke
    assert "launch_handoff" in runbook
    assert "launch_handoff" in readme
    assert "launch_handoff" in guide
    assert "launch_handoff_summary" in release_gate
    assert "launch_handoff_summary" in runbook
    assert "launch_handoff_summary" in readme
    assert "launch_handoff_summary" in guide
    assert "ready_launch_action_coverage" in product_smoke
    assert "ready_launch_action_coverage" in api_spec
    assert "ready_launch_action_coverage" in runbook
    assert "ready_launch_action_coverage" in readme
    assert "ready_launch_action_coverage" in guide
    assert "ready_launch_action_coverage_summary" in release_gate
    assert "ready_launch_action_coverage_summary" in api_spec
    assert "ready_launch_action_coverage_summary" in runbook
    assert "ready_launch_action_coverage_summary" in readme
    assert "ready_launch_action_coverage_summary" in guide
    for field in (
        "ready_only_action_ids",
        "launch_only_action_ids",
        "ready_only_required_env",
        "launch_only_required_env",
    ):
        assert field in product_smoke
    for marker in ("ready-only", "launch-only"):
        assert marker in api_spec
        assert marker in runbook
        assert marker in readme
        assert marker in guide
    assert "shape and decision consistency" in runbook.replace("\n", " ")
    assert "shape and decision consistency" in readme.replace("\n", " ")
    assert "shape and decision consistency" in guide.replace("\n", " ")
    assert "requires the child `launch_handoff` object" in runbook
    assert "requires the child `launch_handoff` object" in readme
    assert "requires the child `launch_handoff` object" in guide
    assert "launch_control" in browser_smoke
    assert "launch_control" in runbook
    assert "launch_control" in readme
    assert "launch_control" in guide
    assert "browser_launch_control_summary" in release_gate
    assert "browser_launch_control_summary" in runbook
    assert "browser_launch_control_summary" in readme
    assert "browser_launch_control_summary" in guide
    for field in ("evidence_source", "api_mocked", "mocked_endpoints"):
        assert field in browser_smoke
        assert field in runbook
        assert field in readme
        assert field in guide
    for field in ("json_launch_release_decision", "json_launch_operator_phase", "json_launch_readiness_status"):
        assert field in release_gate
        assert field in runbook
        assert field in readme
        assert field in guide
    assert "validation_skipped: true" in runbook
    assert "validation_skipped: true" in readme
    assert "validation_skipped: true" in guide
    assert "validation_skip_reason: dry_run" in runbook
    assert "validation_skip_reason: dry_run" in readme
    assert "validation_skip_reason: dry_run" in guide
    assert "stale files" in runbook
    assert "stale files" in readme
    assert "stale files" in guide
    assert "validation_failures" in release_gate
    assert "validation_failures" in runbook
    assert "validation_failures" in readme
    assert "validation_failures" in guide
    assert "validation_failed_artifact_paths" in release_gate
    assert "validation_failed_artifact_paths" in runbook
    assert "validation_failed_artifact_paths" in readme
    assert "validation_failed_artifact_paths" in guide
    assert "simulated LLM" in runbook
    assert "simulated LLM" in readme
    assert "simulated LLM" in guide
    assert "ALLOW_TEST_BYPASS" in runbook
    assert "ALLOW_TEST_BYPASS" in readme
    assert "ALLOW_TEST_BYPASS" in guide
    assert "ALLOW_DEV_AUTH_FALLBACK" in runbook
    assert "ALLOW_DEV_AUTH_FALLBACK" in readme
    assert "ALLOW_DEV_AUTH_FALLBACK" in guide
    assert "FIREBASE_PROJECT_ID" in runbook
    assert "FIREBASE_PROJECT_ID" in readme
    assert "FIREBASE_PROJECT_ID" in guide
    assert "not enough" in runbook
    assert "not backend token-verification credentials" in readme
    assert "not backend token-verification credentials" in guide
    assert "existing mounted" in runbook
    assert "existing mounted" in readme
    assert "existing mounted" in guide
    for field in ("project_id", "client_email", "private_key"):
        assert field in runbook
        assert field in readme
        assert field in guide
    assert "MOCK_MODE=true" in runbook
    assert "MOCK_MODE=true" in readme
    assert "MOCK_MODE=true" in guide
    assert "Web3 readiness" in runbook
    assert "Web3 readiness" in readme
    assert "Web3 readiness" in guide
    assert "ALLOWED_ORIGINS" in runbook
    assert "ALLOWED_ORIGINS" in readme
    assert "ALLOWED_ORIGINS" in guide
    assert "wildcard" in runbook
    assert "wildcard" in readme
    assert "wildcard" in guide
    assert "localhost" in runbook
    assert "localhost" in readme
    assert "localhost" in guide
    assert "public `https://` origins without paths" in runbook
    assert "public `https://` origins without paths" in readme
    assert "public `https://` origins without paths" in guide
    assert "VITE_API_BASE_URL" in runbook
    assert "VITE_API_BASE_URL" in readme
    assert "VITE_API_BASE_URL" in guide
    assert "using the API" in runbook
    assert "using the API" in readme
    assert "using the API" in guide
    assert "trimming whitespace" in runbook
    assert "trimming whitespace" in readme
    assert "trimming whitespace" in guide
    assert "loaded before logging" in runbook
    assert "loaded before logging" in readme
    assert "loaded before logging" in guide
    assert '"schema_version": 1' in release_gate
    assert "schema_version: 1" in runbook
    assert "schema_version: 1" in readme
    assert "schema_version: 1" in guide
    assert "--print-report-schema" in release_gate
    assert "--print-report-schema" in runbook
    assert "--print-report-schema" in readme
    assert "--print-report-schema" in guide
    assert "JSON Schema draft 2020-12" in runbook
    assert "JSON Schema draft 2020-12" in readme
    assert "JSON Schema draft 2020-12" in guide
    assert "per-step result fields" in runbook
    assert "per-step result fields" in readme
    assert "per-step result fields" in guide
    for field in ("returncode", "command_argv", "failures"):
        assert field in release_gate
        assert field in runbook
        assert field in readme
        assert field in guide
    assert "Parent and child `--json-out` reports" in runbook
    assert "Parent and child `--json-out` reports" in readme
    assert "Parent and child `--json-out` reports" in guide
    assert "atomically replaced" in runbook
    assert "atomically replaced" in readme
    assert "atomically replaced" in guide
    assert "previous valid handoff report" in runbook.replace("\n", " ")
    assert "previous valid handoff report" in readme.replace("\n", " ")
    assert "previous valid handoff report" in guide.replace("\n", " ")
    assert "json_schema_version" in release_gate
    assert "json_schema_version" in runbook
    assert "json_schema_version" in readme
    assert "json_schema_version" in guide
    for field in ("schema_versioned", "schema_unversioned"):
        assert field in release_gate
        assert field in runbook
        assert field in readme
        assert field in guide
    for field in ("json_warning_count", "has_warnings"):
        assert field in release_gate
        assert field in runbook
        assert field in readme
        assert field in guide
    for field in ("json_trace_artifact_count", "has_trace_artifacts", "json_trace_artifact_paths"):
        assert field in release_gate
        assert field in runbook
        assert field in readme
        assert field in guide
    for field in (
        "json_trace_artifact_resolved_paths",
        "json_trace_artifact_existing_count",
        "json_trace_artifact_missing_count",
        "has_missing_trace_artifacts",
        "json_trace_artifact_missing_paths",
    ):
        assert field in release_gate
        assert field in runbook
        assert field in readme
        assert field in guide
    assert "json_trace_artifact_checks" in release_gate
    assert "json_trace_artifact_checks" in runbook
    assert "json_trace_artifact_checks" in readme
    assert "json_trace_artifact_checks" in guide
    assert "browser_trace_artifact_summary" in release_gate
    assert "browser_trace_artifact_summary" in runbook
    assert "browser_trace_artifact_summary" in readme
    assert "browser_trace_artifact_summary" in guide
    for field in (
        "trace_artifact_count",
        "existing_count",
        "missing_count",
        "trace_artifact_paths",
        "resolved_paths",
        "missing_paths",
        "checks",
        "trace_viewer_commands",
    ):
        assert field in release_gate
        assert field in runbook
        assert field in readme
        assert field in guide
    assert "npx playwright show-trace" in runbook
    assert "npx playwright show-trace" in readme
    assert "npx playwright show-trace" in guide
    assert "notices-discovery-biolinker-handoff" in browser_smoke
    assert "notices-discovery-biolinker-handoff" in runbook
    assert "notices-discovery-biolinker-handoff" in readme
    assert "notices-discovery-biolinker-handoff" in guide
    assert "--runtime-browser-expect-dev-auth" in release_gate
    assert "--runtime-browser-expect-dev-auth" in runbook
    assert "--runtime-browser-expect-dev-auth" in readme
    assert "--runtime-browser-expect-dev-auth" in guide
    for field in ("json_missing_env_file_count", "has_missing_env_files", "json_missing_env_files"):
        assert field in release_gate
        assert field in runbook
        assert field in readme
        assert field in guide
    for field in ("json_failed_checks", "json_warning_checks"):
        assert field in release_gate
        assert field in runbook
        assert field in readme
        assert field in guide
    assert "artifact_paths" in release_gate
    assert "artifact_paths" in runbook
    assert "artifact_paths" in readme
    assert "artifact_paths" in guide
    assert "preflight summary does not match checks" in release_gate
    assert "pass/fail/warn status" in release_gate
    assert "sources.include_process_env must be a boolean" in release_gate
    assert "sources.env_files entries must include non-empty path, resolved_path, and exists" in release_gate
    assert "sources.env_files must exist" in release_gate
    assert "summary counts match" in runbook
    assert "summary counts match" in readme
    assert "summary counts match" in guide
    assert "pass/fail/warn" in runbook
    assert "pass/fail/warn" in readme
    assert "pass/fail/warn" in guide
    assert "non-empty" in runbook
    assert "non-empty" in readme
    assert "non-empty" in guide
    assert "must exist" in runbook
    assert "must exist" in readme
    assert "must exist" in guide
    for field in ("path", "resolved_path", "exists"):
        assert field in runbook
        assert field in readme
        assert field in guide
    for field in ("generated_at", "api", "frontend"):
        assert field in release_gate
        assert field in product_smoke
        assert field in browser_smoke or field == "api"
        assert field in runbook
        assert field in readme
        assert field in guide
    for field in ("json_generated_at", "json_api", "json_frontend"):
        assert field in release_gate
        assert field in runbook
        assert field in readme
        assert field in guide
    for field in ("json_check_total", "json_check_passed", "json_check_failed", "json_failed_checks"):
        assert field in release_gate
        assert field in runbook
        assert field in readme
        assert field in guide
    for field in ("json_check_warnings", "json_warning_checks"):
        assert field in release_gate
        assert field in runbook
        assert field in readme
        assert field in guide
    for field in (
        "json_profile",
        "json_targets",
        "json_env_file_count",
        "json_missing_env_file_count",
        "json_missing_env_files",
        "json_include_process_env",
    ):
        assert field in release_gate
        assert field in runbook
        assert field in readme
        assert field in guide
    assert "--json-out ../../var/desci-release-gate-runtime.json" in readme
    assert "--json-out ../../var/desci-release-gate-runtime.json" in guide


def test_runtime_smoke_docs_capture_json_evidence() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    runbook = (PROJECT_ROOT / "OPERATIONS_RUNBOOK.md").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "DEPLOYMENT_GUIDE.md").read_text(encoding="utf-8")
    product_smoke = (PROJECT_ROOT / "scripts" / "product_smoke.py").read_text(encoding="utf-8")
    browser_smoke = (PROJECT_ROOT / "scripts" / "browser_smoke.py").read_text(encoding="utf-8")

    assert "--json-out" in product_smoke
    assert "write_json_report" in product_smoke
    assert "--json-out" in browser_smoke
    assert "write_json_report" in browser_smoke
    assert "login-validation" in browser_smoke
    assert "login-validation interaction evidence" in runbook
    assert "--trace-on-failure-dir" in browser_smoke
    assert "--trace-on-failure-dir ../../var/desci-browser-traces" in runbook
    assert "--trace-on-failure-dir ../../var/desci-browser-traces" in readme
    assert "--trace-on-failure-dir ../../var/desci-browser-traces" in guide
    assert "trace_artifacts" in browser_smoke
    assert "trace_artifacts" in runbook
    assert "trace_path" in browser_smoke
    assert "trace_path" in runbook
    assert "python scripts/product_smoke.py --strict-ready" in readme
    assert "--json-out ../../var/desci-product-smoke-local.json" in readme
    assert "--json-out ../../var/desci-product-smoke-local.json" in runbook
    assert "--json-out ../../var/desci-product-smoke-production.json" in runbook
    assert "--json-out ../../var/desci-browser-smoke-local.json" in runbook
    assert "--json-out ../../var/desci-browser-smoke-production.json" in runbook
    assert "schema_version: 1" in runbook
    assert "schema_version" in product_smoke
    assert "schema_version" in browser_smoke
    assert "check-level `failures` arrays" in runbook


def test_frontend_vitest_split_runner_has_worker_startup_fallback() -> None:
    runner = (PROJECT_ROOT / "frontend" / "scripts" / "run-vitest-split.mjs").read_text(encoding="utf-8")

    assert "isWorkerStartupFailure" in runner
    assert "[vitest-pool-runner]: Timeout waiting for worker to respond" in runner
    assert "worker startup failed; retrying with vmThreads + isolate" in runner
    assert '"--pool=vmThreads"' in runner
    assert '"--no-isolate"' in runner


def test_public_docs_use_current_product_identity() -> None:
    api_spec = (PROJECT_ROOT / "API_SPEC.md").read_text(encoding="utf-8")
    backend_main = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "DEPLOYMENT_GUIDE.md").read_text(encoding="utf-8")
    runbook = (PROJECT_ROOT / "OPERATIONS_RUNBOOK.md").read_text(encoding="utf-8")

    for document in (api_spec, backend_main, readme, guide, runbook):
        assert "DSCI-DecentBio" in document

    assert '"service": "DSCI-DecentBio"' in api_spec
    assert '"service": "DSCI-DecentBio"' in backend_main
    assert '"service": "BioLinker"' not in api_spec
    assert '"service": "BioLinker"' not in backend_main
    assert "??" not in guide
