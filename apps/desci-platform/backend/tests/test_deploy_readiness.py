from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import deploy_readiness  # noqa: E402
import release_handoff  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVICE_ACCOUNT_JSON = json.dumps(
    {
        "project_id": "demo",
        "client_email": "firebase-admin@dsci-prod.iam.gserviceaccount.com",
        "private_key": "not-a-real-test-private-key",
    }
)


def _ready_env() -> dict[str, str]:
    return {
        "ENV": "production",
        "GOOGLE_API_KEY": "real-google-key",
        "FIREBASE_SERVICE_ACCOUNT_JSON": SERVICE_ACCOUNT_JSON,
        "DATABASE_URL": "railway-postgres-configured",
        "ALLOWED_ORIGINS": "https://app.dsci-prod.io",
        "DESCI_FRONTEND_URL": "https://app.dsci-prod.io",
        "REDIS_URL": "rediss://redis:6379/0",
        "RABBITMQ_URL": "amqps://rabbitmq:5671/desci",
        "STRIPE_SECRET_KEY": "stripe-secret-configured",
        "STRIPE_WEBHOOK_SECRET": "stripe-webhook-configured",
        "STRIPE_PRICE_PRO_MONTHLY": "price_live_pro_monthly_real",
        "STRIPE_PRICE_PRO_YEARLY": "price_live_pro_yearly_real",
        "VITE_API_BASE_URL": "https://api.dsci-prod.io",
        "VITE_FIREBASE_API_KEY": "firebase-api-key",
        "VITE_FIREBASE_AUTH_DOMAIN": "project.firebaseapp.com",
        "VITE_FIREBASE_PROJECT_ID": "project-id",
        "VITE_FIREBASE_STORAGE_BUCKET": "project.appspot.com",
        "VITE_FIREBASE_MESSAGING_SENDER_ID": "sender-id",
        "VITE_FIREBASE_APP_ID": "firebase-app-id",
        "VITE_WALLET_CHAIN_ID": "80002",
        "VITE_DSCI_TOKEN_ADDRESS": "0x1234567890123456789012345678901234567890",
        "VITE_RESEARCH_PAPER_NFT_ADDRESS": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
        "AMOY_RPC_URL": "https://polygon-amoy.drpc.org",
        "PRIVATE_KEY": "0x" + "1" * 64,
        "POLYGONSCAN_API_KEY": "polygonscan-key",
        "GITLEAKS_LICENSE": "gitleaks-license",
    }


def test_ready_env_passes_required_external_targets() -> None:
    checks = deploy_readiness.run_checks(_ready_env(), targets=("railway", "vercel", "amoy", "github"))

    failed = [check.id for check in checks if check.status == "fail"]

    assert failed == []


def test_placeholder_values_fail_required_checks() -> None:
    env = _ready_env()
    env["DATABASE_URL"] = "postgresql://example.com/desci"
    env["REDIS_URL"] = "rediss://example.com/0"
    env["PRIVATE_KEY"] = "your_wallet_private_key"
    env["GITLEAKS_LICENSE"] = ""

    checks = deploy_readiness.run_checks(env, targets=("railway", "amoy", "github"))
    failed = {check.id for check in checks if check.status == "fail"}

    assert {"railway_database", "railway_queue", "amoy_private_key", "github_gitleaks_license"} <= failed


def test_railway_stripe_requires_paid_checkout_launch_keys() -> None:
    env = _ready_env()
    env.pop("STRIPE_PRICE_PRO_MONTHLY")
    env.pop("STRIPE_PRICE_PRO_YEARLY")

    checks = deploy_readiness.run_checks(env, targets=("railway",))

    stripe_check = next(check for check in checks if check.id == "railway_stripe")
    assert stripe_check.status == "fail"
    assert stripe_check.required is True
    assert stripe_check.keys == (
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_PRICE_PRO_MONTHLY",
        "STRIPE_PRICE_PRO_YEARLY",
    )


def test_railway_requires_public_frontend_return_origin_for_stripe_redirects() -> None:
    env = _ready_env()
    env.pop("DESCI_FRONTEND_URL")

    checks = deploy_readiness.run_checks(env, targets=("railway",))

    return_url_check = next(check for check in checks if check.id == "railway_frontend_return_url")
    assert return_url_check.status == "fail"
    assert return_url_check.required is True
    assert return_url_check.keys == ("DESCI_FRONTEND_URL",)

    env["DESCI_FRONTEND_URL"] = "http://localhost:5173"
    checks = deploy_readiness.run_checks(env, targets=("railway",))

    return_url_check = next(check for check in checks if check.id == "railway_frontend_return_url")
    assert return_url_check.status == "fail"


def test_reserved_example_domains_fail_required_checks() -> None:
    env = _ready_env()
    env["ALLOWED_ORIGINS"] = "https://app.dsci.example"
    env["VITE_API_BASE_URL"] = "https://api.example"
    env["DESCI_FRONTEND_URL"] = "https://app.example"

    checks = deploy_readiness.run_checks(env, targets=("railway", "vercel"))
    failed = {check.id for check in checks if check.status == "fail"}

    assert {"railway_cors", "railway_frontend_return_url", "vercel_api_base"} <= failed


def test_wildcard_and_localhost_cors_fail_required_checks() -> None:
    env = _ready_env()
    env["ALLOWED_ORIGINS"] = "*,http://localhost:5173"

    checks = deploy_readiness.run_checks(env, targets=("railway",))

    cors_check = next(check for check in checks if check.id == "railway_cors")
    assert cors_check.status == "fail"


def test_non_https_api_base_fails_required_checks() -> None:
    env = _ready_env()
    env["VITE_API_BASE_URL"] = "http://api.dsci-prod.io"

    checks = deploy_readiness.run_checks(env, targets=("vercel",))

    api_base_check = next(check for check in checks if check.id == "vercel_api_base")
    assert api_base_check.status == "fail"


def test_cors_origins_with_paths_or_queries_fail_required_checks() -> None:
    env = _ready_env()
    env["ALLOWED_ORIGINS"] = "https://app.dsci-prod.io/app,https://admin.dsci-prod.io?preview=true"

    checks = deploy_readiness.run_checks(env, targets=("railway",))

    cors_check = next(check for check in checks if check.id == "railway_cors")
    assert cors_check.status == "fail"


def test_api_origin_as_only_cors_origin_fails_required_checks() -> None:
    env = _ready_env()
    env["VITE_API_BASE_URL"] = "https://api.dsci-prod.io/v1"
    env["ALLOWED_ORIGINS"] = "https://api.dsci-prod.io"

    checks = deploy_readiness.run_checks(env, targets=("railway",))

    cors_check = next(check for check in checks if check.id == "railway_cors")
    assert cors_check.status == "fail"
    assert "API origin" in cors_check.remediation


def test_vercel_wallet_provider_requires_amoy_and_deployed_contract_addresses() -> None:
    env = _ready_env()
    env["VITE_WALLET_CHAIN_ID"] = "0x1"
    env["VITE_DSCI_TOKEN_ADDRESS"] = "0x0000000000000000000000000000000000000000"
    env["VITE_RESEARCH_PAPER_NFT_ADDRESS"] = "not-an-address"

    checks = deploy_readiness.run_checks(env, targets=("vercel",))
    failed = {check.id for check in checks if check.status == "fail"}

    assert {"vercel_wallet_network", "vercel_wallet_contracts"} <= failed


def test_vercel_wallet_rpc_override_rejects_malformed_or_non_https_urls() -> None:
    env = _ready_env()
    env["VITE_WALLET_RPC_URL"] = "https://polygon-amoy.drpc.org, http://localhost:8545"

    checks = deploy_readiness.run_checks(env, targets=("vercel",))

    wallet_rpc_check = next(check for check in checks if check.id == "vercel_wallet_rpc")
    assert wallet_rpc_check.status == "fail"
    assert "public HTTPS" in wallet_rpc_check.remediation


def test_railway_auth_requires_backend_credentials_not_project_id_only() -> None:
    env = _ready_env()
    env.pop("FIREBASE_SERVICE_ACCOUNT_JSON")
    env["FIREBASE_PROJECT_ID"] = "project-id"

    checks = deploy_readiness.run_checks(env, targets=("railway",))

    auth_check = next(check for check in checks if check.id == "railway_auth")
    assert auth_check.status == "fail"
    assert auth_check.keys == ("GOOGLE_APPLICATION_CREDENTIALS", "FIREBASE_SERVICE_ACCOUNT_JSON")


def test_railway_auth_rejects_incomplete_service_account_json() -> None:
    env = _ready_env()
    env["FIREBASE_SERVICE_ACCOUNT_JSON"] = json.dumps({"project_id": "demo"})

    checks = deploy_readiness.run_checks(env, targets=("railway",))

    auth_check = next(check for check in checks if check.id == "railway_auth")
    assert auth_check.status == "fail"
    assert "private_key" in auth_check.remediation


def test_railway_rejects_local_bypass_and_mock_flags_for_production() -> None:
    env = _ready_env()
    env["ALLOW_TEST_BYPASS"] = "true"
    env["ALLOW_DEV_AUTH_FALLBACK"] = "on"
    env["MOCK_MODE"] = "1"

    checks = deploy_readiness.run_checks(env, targets=("railway",))

    safety_check = next(check for check in checks if check.id == "railway_production_safety_flags")
    assert safety_check.status == "fail"
    assert safety_check.required is True
    assert safety_check.keys == ("ALLOW_TEST_BYPASS", "ALLOW_DEV_AUTH_FALLBACK", "MOCK_MODE")


def test_amoy_accepts_web3_rpc_fallback_and_ethplorer_key() -> None:
    env = {
        "WEB3_RPC_URL": "https://polygon-amoy.infura.io/v3/real-key",
        "PRIVATE_KEY": "2" * 64,
        "ETHERSCAN_API_KEY": "etherscan-key",
    }

    checks = deploy_readiness.run_checks(env, targets=("amoy",))
    failed = [check.id for check in checks if check.status == "fail"]
    funding = next(check for check in checks if check.id == "amoy_funding")

    assert failed == []
    assert funding.status == "warn"


def test_amoy_rejects_non_https_or_malformed_rpc_urls() -> None:
    env = {
        "AMOY_RPC_URL": "http://polygon-amoy.local",
        "WEB3_RPC_URL": "not-a-url",
        "PRIVATE_KEY": "2" * 64,
        "POLYGONSCAN_API_KEY": "polygonscan-key",
    }

    checks = deploy_readiness.run_checks(env, targets=("amoy",))

    rpc_check = next(check for check in checks if check.id == "amoy_rpc")
    assert rpc_check.status == "fail"
    assert "public HTTPS" in rpc_check.remediation


def test_parse_env_file_handles_export_and_quotes(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "export ENV=production\nVITE_API_BASE_URL=\"https://api.example\"\n# ignored\n",
        encoding="utf-8",
    )

    assert deploy_readiness.parse_env_file(env_file) == {
        "ENV": "production",
        "VITE_API_BASE_URL": "https://api.example",
    }


def test_production_example_is_not_mistaken_for_real_deployment_config() -> None:
    env = deploy_readiness.load_env(
        [PROJECT_ROOT / ".env.production.example"],
        include_process_env=False,
    )

    checks = deploy_readiness.run_checks(env, targets=("railway", "vercel", "amoy", "github"))
    failed = {check.id for check in checks if check.status == "fail"}

    assert {
        "railway_llm",
        "railway_database",
        "railway_cors",
        "railway_frontend_return_url",
        "railway_queue",
        "railway_stripe",
        "vercel_api_base",
        "vercel_firebase",
        "vercel_wallet_contracts",
        "amoy_rpc",
        "amoy_private_key",
        "amoy_explorer",
        "github_gitleaks_license",
    } <= failed


def test_deploy_readiness_json_report_has_operator_summary() -> None:
    checks = deploy_readiness.run_checks(_ready_env(), targets=("railway", "vercel", "amoy", "github"))
    payload = deploy_readiness.json_report_payload(checks, targets=("railway", "vercel", "amoy", "github"))

    assert payload["schema_version"] == 1
    assert payload["generated_at"]
    assert payload["ok"] is True
    assert payload["targets"] == ["railway", "vercel", "amoy", "github"]
    assert payload["summary"]["total"] == len(checks)
    assert payload["summary"]["failed"] == 0
    assert payload["summary"]["warnings"] == 1
    assert payload["summary"]["failed_checks"] == []
    assert payload["summary"]["warning_checks"] == ["amoy_funding"]
    assert any(group["owner"] == "Railway backend" for group in payload["owner_surface_summary"])


def test_deploy_readiness_json_report_groups_blockers_by_owner_surface() -> None:
    env = _ready_env()
    env.pop("FIREBASE_SERVICE_ACCOUNT_JSON")
    env["ALLOWED_ORIGINS"] = "http://localhost:5173"
    env.pop("STRIPE_SECRET_KEY")
    env.pop("STRIPE_WEBHOOK_SECRET")
    env.pop("STRIPE_PRICE_PRO_MONTHLY")
    env.pop("STRIPE_PRICE_PRO_YEARLY")

    checks = deploy_readiness.run_checks(env, targets=("railway",))
    payload = deploy_readiness.json_report_payload(checks, targets=("railway",))
    groups = {(group["owner"], group["surface"]): group for group in payload["owner_surface_summary"]}

    assert groups[("Firebase", "Backend authentication")]["failed_checks"] == ["railway_auth"]
    assert groups[("Stripe", "Paid checkout")]["failed_checks"] == ["railway_stripe"]
    assert groups[("Railway + Vercel", "CORS allowlist")]["required_env"] == ["ALLOWED_ORIGINS"]
    assert "STRIPE_SECRET_KEY" in groups[("Stripe", "Paid checkout")]["required_env"]


def test_deploy_readiness_print_report_groups_actions_by_surface(capsys) -> None:
    env = _ready_env()
    env.pop("FIREBASE_SERVICE_ACCOUNT_JSON")
    env["ALLOWED_ORIGINS"] = "http://localhost:5173"

    checks = deploy_readiness.run_checks(env, targets=("railway",))

    deploy_readiness.print_report(checks)

    output = capsys.readouterr().out
    assert "[deploy-readiness] ACTION BY SURFACE" in output
    assert "Firebase / Backend authentication: 1 failed, 0 warning(s)" in output
    assert "railway_auth" in output
    assert "Railway + Vercel / CORS allowlist: 1 failed, 0 warning(s)" in output


def test_deploy_readiness_writes_json_report(tmp_path: Path) -> None:
    checks = deploy_readiness.run_checks(_ready_env(), targets=("railway", "vercel", "amoy", "github"))
    payload = deploy_readiness.json_report_payload(checks, targets=("railway", "vercel", "amoy", "github"))
    report_path = tmp_path / "reports" / "deploy-readiness.json"

    deploy_readiness.write_json_report(report_path, payload)

    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == 1
    assert written["generated_at"]
    assert written["ok"] is True
    assert written["summary"]["warning_checks"] == ["amoy_funding"]
    assert not (report_path.parent / "deploy-readiness.json.tmp").exists()


def test_deploy_readiness_replaces_existing_json_report_atomically(tmp_path: Path) -> None:
    checks = deploy_readiness.run_checks(_ready_env(), targets=("railway", "vercel", "amoy", "github"))
    payload = deploy_readiness.json_report_payload(checks, targets=("railway", "vercel", "amoy", "github"))
    report_path = tmp_path / "reports" / "deploy-readiness.json"
    report_path.parent.mkdir()
    report_path.write_text('{"old": true}', encoding="utf-8")

    deploy_readiness.write_json_report(report_path, payload)

    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == 1
    assert "old" not in written
    assert not (report_path.parent / "deploy-readiness.json.tmp").exists()


def test_deploy_readiness_source_report_records_env_inputs(tmp_path: Path) -> None:
    env_file = tmp_path / "deploy.env"
    env_file.write_text("ENV=production\n", encoding="utf-8")

    report = deploy_readiness.env_source_report([env_file, tmp_path / "contracts.env"], include_process_env=True)

    assert report["include_process_env"] is True
    assert report["env_files"][0]["path"] == str(env_file)
    assert report["env_files"][0]["resolved_path"] == str(env_file.resolve())
    assert report["env_files"][0]["exists"] is True
    assert report["env_files"][1]["exists"] is False


def _product_smoke_handoff_payload(actions: list[dict[str, object]], *, ok: bool = False) -> dict[str, object]:
    return {
        "schema_version": 1,
        "ok": ok,
        "launch_handoff": {
            "release_decision": "no-go" if not ok else "go",
            "operator_phase": "blocked" if not ok else "launch-ready",
            "readiness_status": "blocked" if not ok else "ready",
            "summary": {"blocker_count": sum(1 for action in actions if action.get("required") is True)},
            "score": {"overall_percent": 57, "required_percent": 50},
            "launch_blockers": [str(action["id"]) for action in actions if action.get("required") is True],
            "next_actions": actions,
        },
        "failures": ["launch: release decision is no-go"] if not ok else [],
    }


def test_release_handoff_maps_product_actions_to_deploy_surfaces() -> None:
    product_payload = _product_smoke_handoff_payload(
        [
            {
                "id": "auth",
                "required": True,
                "status": "fail",
                "remediation": "Set Firebase backend credentials.",
                "required_env": ["GOOGLE_APPLICATION_CREDENTIALS", "FIREBASE_SERVICE_ACCOUNT_JSON"],
            },
            {
                "id": "stripe",
                "required": True,
                "status": "fail",
                "remediation": "Set Stripe checkout keys.",
                "required_env": [
                    "STRIPE_SECRET_KEY",
                    "STRIPE_WEBHOOK_SECRET",
                    "STRIPE_PRICE_PRO_MONTHLY",
                    "STRIPE_PRICE_PRO_YEARLY",
                ],
            },
        ]
    )
    env = _ready_env()
    env.pop("FIREBASE_SERVICE_ACCOUNT_JSON")
    env.pop("STRIPE_SECRET_KEY")
    env.pop("STRIPE_WEBHOOK_SECRET")
    env.pop("STRIPE_PRICE_PRO_MONTHLY")
    env.pop("STRIPE_PRICE_PRO_YEARLY")
    checks = deploy_readiness.run_checks(env, targets=("railway", "vercel"))
    deploy_payload = deploy_readiness.json_report_payload(checks, targets=("railway", "vercel"))

    payload = release_handoff.build_handoff(product_payload, deploy_payload)
    checklist = {item["id"]: item for item in payload["operator_checklist"]}

    assert payload["ok"] is False
    assert payload["release_decision"] == "no-go"
    assert checklist["auth"]["coverage"] == "covered"
    assert {surface["id"] for surface in checklist["auth"]["deploy_surfaces"]} == {"railway_auth", "vercel_firebase"}
    assert checklist["stripe"]["coverage"] == "covered"
    assert {surface["id"] for surface in checklist["stripe"]["deploy_surfaces"]} == {
        "railway_frontend_return_url",
        "railway_stripe",
    }
    assert payload["coverage"]["missing_required_coverage"] == []


def test_release_handoff_keeps_product_only_optional_actions_visible() -> None:
    product_payload = _product_smoke_handoff_payload(
        [
            {
                "id": "grobid",
                "required": False,
                "status": "warn",
                "remediation": "Set GROBID_ENABLED=true and GROBID_URL.",
                "required_env": ["GROBID_ENABLED", "GROBID_URL"],
            }
        ],
        ok=True,
    )
    checks = deploy_readiness.run_checks(_ready_env(), targets=("railway", "vercel"))
    deploy_payload = deploy_readiness.json_report_payload(checks, targets=("railway", "vercel"))

    payload = release_handoff.build_handoff(product_payload, deploy_payload)
    item = payload["operator_checklist"][0]

    assert item["coverage"] == "product_only"
    assert item["deploy_surfaces"][0]["owner"] == "Product runtime"
    assert payload["coverage"]["product_only_actions"] == ["grobid"]
    assert payload["coverage"]["missing_required_coverage"] == []


def test_release_handoff_lists_failed_deploy_checks_not_owned_by_product_actions() -> None:
    product_payload = _product_smoke_handoff_payload([], ok=True)
    env = _ready_env()
    env["DATABASE_URL"] = "postgresql://example.com/desci"
    checks = deploy_readiness.run_checks(env, targets=("railway",))
    deploy_payload = deploy_readiness.json_report_payload(checks, targets=("railway",))

    payload = release_handoff.build_handoff(product_payload, deploy_payload)

    assert "railway_database" in {action["id"] for action in payload["deploy_only_actions"]}
    assert payload["deploy_readiness_ok"] is False
    assert payload["ok"] is False


def test_release_handoff_cli_writes_json_report(tmp_path: Path, capsys) -> None:
    product_payload = _product_smoke_handoff_payload(
        [
            {
                "id": "auth",
                "required": True,
                "status": "fail",
                "remediation": "Set Firebase credentials.",
                "required_env": ["FIREBASE_SERVICE_ACCOUNT_JSON"],
            }
        ]
    )
    env = _ready_env()
    env.pop("FIREBASE_SERVICE_ACCOUNT_JSON")
    checks = deploy_readiness.run_checks(env, targets=("railway",))
    deploy_payload = deploy_readiness.json_report_payload(checks, targets=("railway",))
    product_path = tmp_path / "product.json"
    deploy_path = tmp_path / "deploy.json"
    output_path = tmp_path / "handoff.json"
    product_path.write_text(json.dumps(product_payload), encoding="utf-8")
    deploy_path.write_text(json.dumps(deploy_payload), encoding="utf-8")

    code = release_handoff.main(
        [
            "--product-smoke-json",
            str(product_path),
            "--deploy-readiness-json",
            str(deploy_path),
            "--json-out",
            str(output_path),
        ]
    )

    output = capsys.readouterr().out
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert code == 1
    assert "[release-handoff] PRODUCT ACTION CHECKLIST" in output
    assert written["schema_version"] == 1
    assert written["sources"]["product_smoke_json"] == str(product_path)
    assert not (output_path.parent / "handoff.json.tmp").exists()
