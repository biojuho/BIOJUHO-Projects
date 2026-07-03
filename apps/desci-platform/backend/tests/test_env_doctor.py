from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import env_doctor  # noqa: E402

SERVICE_ACCOUNT_JSON = json.dumps(
    {
        "project_id": "demo",
        "client_email": "firebase-admin@dsci-prod.iam.gserviceaccount.com",
        "private_key": "not-a-real-test-private-key",
    }
)


def _production_env() -> dict[str, str]:
    return {
        "ENV": "production",
        "GOOGLE_API_KEY": "real-google-key",
        "GOOGLE_APPLICATION_CREDENTIALS": "/run/secrets/firebase.json",
        "VITE_FIREBASE_API_KEY": "firebase-api-key",
        "VITE_FIREBASE_AUTH_DOMAIN": "project.firebaseapp.com",
        "VITE_FIREBASE_PROJECT_ID": "project-id",
        "VITE_FIREBASE_STORAGE_BUCKET": "project.appspot.com",
        "VITE_FIREBASE_MESSAGING_SENDER_ID": "sender-id",
        "VITE_FIREBASE_APP_ID": "firebase-app-id",
        "VITE_API_BASE_URL": "https://api.dsci-prod.io",
        "VITE_WALLET_CHAIN_ID": "0x13882",
        "VITE_DSCI_TOKEN_ADDRESS": "0x1234567890123456789012345678901234567890",
        "VITE_RESEARCH_PAPER_NFT_ADDRESS": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
        "ALLOWED_ORIGINS": "https://app.dsci-prod.io",
        "DESCI_FRONTEND_URL": "https://app.dsci-prod.io",
        "DATABASE_URL": "postgresql://desci_admin:s3cure-prod-db@railway.internal:5432/desci",
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
        "REDIS_URL": "rediss://redis:6379/0",
        "RABBITMQ_URL": "amqps://rabbitmq:5671/desci",
        "STRIPE_SECRET_KEY": "sk_live_real_checkout",
        "STRIPE_WEBHOOK_SECRET": "whsec_real_checkout",
        "STRIPE_PRICE_PRO_MONTHLY": "price_live_pro_monthly_real",
        "STRIPE_PRICE_PRO_YEARLY": "price_live_pro_yearly_real",
    }


def test_production_env_required_checks_pass() -> None:
    checks = env_doctor.run_checks(_production_env(), profile="production")

    failed = [check.id for check in checks if check.status == "fail"]

    assert failed == []


def test_production_env_rejects_template_connection_strings() -> None:
    env = _production_env()
    env["DATABASE_URL"] = "postgresql://user:password@host:5432/desci"
    env["REDIS_URL"] = "rediss://user:password@host:6379/0"
    env["RABBITMQ_URL"] = "amqps://user:password@host:5671/desci"

    checks = env_doctor.run_checks(env, profile="production")
    failed = {check.id for check in checks if check.status == "fail"}

    assert {"postgres", "redis", "rabbitmq"} <= failed


def test_production_example_is_not_mistaken_for_real_runtime_config() -> None:
    env = env_doctor.load_env(
        [Path(__file__).resolve().parents[2] / ".env.production.example"],
        include_process_env=False,
    )

    checks = env_doctor.run_checks(env, profile="production")
    failed = {check.id for check in checks if check.status == "fail"}

    assert {
        "llm",
        "frontend_firebase",
        "api_base",
        "frontend_wallet",
        "cors",
        "frontend_return_url",
        "postgres",
        "supabase",
        "redis",
        "rabbitmq",
        "stripe",
    } <= failed


def test_production_env_requires_stripe_price_ids_for_paid_checkout() -> None:
    env = _production_env()
    env.pop("STRIPE_PRICE_PRO_MONTHLY")
    env.pop("STRIPE_PRICE_PRO_YEARLY")

    checks = env_doctor.run_checks(env, profile="production")

    stripe_check = next(check for check in checks if check.id == "stripe")
    assert stripe_check.status == "fail"
    assert stripe_check.required is True
    assert stripe_check.keys == (
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_PRICE_PRO_MONTHLY",
        "STRIPE_PRICE_PRO_YEARLY",
    )


def test_production_env_requires_public_checkout_return_origin() -> None:
    env = _production_env()
    env.pop("DESCI_FRONTEND_URL")

    checks = env_doctor.run_checks(env, profile="production")

    return_url_check = next(check for check in checks if check.id == "frontend_return_url")
    assert return_url_check.status == "fail"
    assert return_url_check.required is True
    assert return_url_check.keys == ("DESCI_FRONTEND_URL",)

    env["DESCI_FRONTEND_URL"] = "http://localhost:5173"
    checks = env_doctor.run_checks(env, profile="production")

    return_url_check = next(check for check in checks if check.id == "frontend_return_url")
    assert return_url_check.status == "fail"


def test_production_env_rejects_placeholders() -> None:
    env = _production_env()
    env["GOOGLE_API_KEY"] = "your_google_api_key_here"
    env["SUPABASE_SERVICE_ROLE_KEY"] = "your_supabase_service_role_key"
    env["STRIPE_SECRET_KEY"] = "<set-secure-value>"
    env["STRIPE_PRICE_PRO_MONTHLY"] = "your_stripe_price_pro_monthly"

    checks = env_doctor.run_checks(env, profile="production")
    failed = {check.id for check in checks if check.status == "fail"}

    assert {"llm", "supabase", "stripe"} <= failed


def test_production_env_rejects_reserved_example_domains() -> None:
    env = _production_env()
    env["VITE_API_BASE_URL"] = "https://api.dsci.example"
    env["ALLOWED_ORIGINS"] = "https://app.example"
    env["DESCI_FRONTEND_URL"] = "https://app.example"

    checks = env_doctor.run_checks(env, profile="production")
    failed = {check.id for check in checks if check.status == "fail"}

    assert {"api_base", "cors", "frontend_return_url"} <= failed


def test_production_env_rejects_wildcard_and_local_cors_origins() -> None:
    env = _production_env()
    env["ALLOWED_ORIGINS"] = "*,http://localhost:5173"

    checks = env_doctor.run_checks(env, profile="production")

    cors_check = next(check for check in checks if check.id == "cors")
    assert cors_check.status == "fail"


def test_production_env_requires_https_api_base_url() -> None:
    env = _production_env()
    env["VITE_API_BASE_URL"] = "http://api.dsci-prod.io"

    checks = env_doctor.run_checks(env, profile="production")

    api_base_check = next(check for check in checks if check.id == "api_base")
    assert api_base_check.status == "fail"


def test_production_env_rejects_cors_origins_with_paths_or_queries() -> None:
    env = _production_env()
    env["ALLOWED_ORIGINS"] = "https://app.dsci-prod.io/app,https://admin.dsci-prod.io?preview=true"

    checks = env_doctor.run_checks(env, profile="production")

    cors_check = next(check for check in checks if check.id == "cors")
    assert cors_check.status == "fail"


def test_production_env_rejects_api_origin_as_only_cors_origin() -> None:
    env = _production_env()
    env["VITE_API_BASE_URL"] = "https://api.dsci-prod.io/v1"
    env["ALLOWED_ORIGINS"] = "https://api.dsci-prod.io"

    checks = env_doctor.run_checks(env, profile="production")

    cors_check = next(check for check in checks if check.id == "cors")
    assert cors_check.status == "fail"
    assert "API origin" in cors_check.remediation


def test_production_env_rejects_incomplete_frontend_wallet_provider_config() -> None:
    env = _production_env()
    env["VITE_WALLET_CHAIN_ID"] = "1"
    env["VITE_DSCI_TOKEN_ADDRESS"] = "0x0000000000000000000000000000000000000000"
    env["VITE_RESEARCH_PAPER_NFT_ADDRESS"] = "not-an-address"

    checks = env_doctor.run_checks(env, profile="production")

    wallet_check = next(check for check in checks if check.id == "frontend_wallet")
    assert wallet_check.status == "fail"
    assert "VITE_WALLET_CHAIN_ID" in wallet_check.keys


def test_production_env_rejects_malformed_frontend_wallet_rpc_override() -> None:
    env = _production_env()
    env["VITE_WALLET_RPC_URL"] = "https://polygon-amoy.drpc.org,not-a-url"

    checks = env_doctor.run_checks(env, profile="production")

    wallet_check = next(check for check in checks if check.id == "frontend_wallet")
    assert wallet_check.status == "fail"
    assert "VITE_WALLET_RPC_URL" in wallet_check.keys
    assert "public HTTPS" in wallet_check.remediation


def test_production_env_rejects_project_id_only_for_backend_auth() -> None:
    env = _production_env()
    env.pop("GOOGLE_APPLICATION_CREDENTIALS")
    env["FIREBASE_PROJECT_ID"] = "project-id"

    checks = env_doctor.run_checks(env, profile="production")

    auth_check = next(check for check in checks if check.id == "auth")
    assert auth_check.status == "fail"
    assert "FIREBASE_SERVICE_ACCOUNT_JSON" in auth_check.keys


def test_production_env_rejects_local_bypass_and_mock_flags() -> None:
    env = _production_env()
    env["ALLOW_TEST_BYPASS"] = "true"
    env["ALLOW_DEV_AUTH_FALLBACK"] = "1"
    env["MOCK_MODE"] = "yes"

    checks = env_doctor.run_checks(env, profile="production")

    safety_check = next(check for check in checks if check.id == "production_safety_flags")
    assert safety_check.status == "fail"
    assert safety_check.required is True
    assert safety_check.keys == ("ALLOW_TEST_BYPASS", "ALLOW_DEV_AUTH_FALLBACK", "MOCK_MODE")


def test_production_env_accepts_complete_service_account_json_for_backend_auth() -> None:
    env = _production_env()
    env.pop("GOOGLE_APPLICATION_CREDENTIALS")
    env["FIREBASE_SERVICE_ACCOUNT_JSON"] = SERVICE_ACCOUNT_JSON

    checks = env_doctor.run_checks(env, profile="production")

    auth_check = next(check for check in checks if check.id == "auth")
    assert auth_check.status == "pass"


def test_production_env_rejects_incomplete_service_account_json_for_backend_auth() -> None:
    env = _production_env()
    env.pop("GOOGLE_APPLICATION_CREDENTIALS")
    env["FIREBASE_SERVICE_ACCOUNT_JSON"] = json.dumps({"project_id": "demo"})

    checks = env_doctor.run_checks(env, profile="production")

    auth_check = next(check for check in checks if check.id == "auth")
    assert auth_check.status == "fail"


def test_production_env_does_not_accept_web3_mock_mode_as_config() -> None:
    env = _production_env()
    env["MOCK_MODE"] = "true"

    checks = env_doctor.run_checks(env, profile="production")

    web3_check = next(check for check in checks if check.id == "web3")
    assert web3_check.status == "warn"
    assert "production" in web3_check.remediation


def test_production_env_accepts_real_web3_contract_config() -> None:
    env = _production_env()
    env.update(
        {
            "MOCK_MODE": "true",
            "WEB3_RPC_URL": "https://polygon-amoy.infura.io/v3/test-key",
            "DSCI_CONTRACT_ADDRESS": "0x1234567890123456789012345678901234567890",
        }
    )

    checks = env_doctor.run_checks(env, profile="production")

    web3_check = next(check for check in checks if check.id == "web3")
    assert web3_check.status == "pass"


def test_production_env_rejects_non_https_or_malformed_web3_rpc_url() -> None:
    env = _production_env()
    env.update(
        {
            "WEB3_RPC_URL": "http://polygon-amoy.local",
            "DSCI_CONTRACT_ADDRESS": "0x1234567890123456789012345678901234567890",
        }
    )

    checks = env_doctor.run_checks(env, profile="production")

    web3_check = next(check for check in checks if check.id == "web3")
    assert web3_check.status == "warn"
    assert "WEB3_RPC_URL" in web3_check.keys


def test_production_env_rejects_malformed_web3_contract_addresses() -> None:
    env = _production_env()
    env.update(
        {
            "WEB3_RPC_URL": "https://polygon-amoy.infura.io/v3/test-key",
            "DSCI_CONTRACT_ADDRESS": "not-an-address",
        }
    )

    checks = env_doctor.run_checks(env, profile="production")

    web3_check = next(check for check in checks if check.id == "web3")
    assert web3_check.status == "warn"


def test_env_doctor_json_report_has_operator_summary() -> None:
    checks = env_doctor.run_checks(_production_env(), profile="production")
    payload = env_doctor.json_report_payload(checks, profile="production")

    assert payload["schema_version"] == 1
    assert payload["generated_at"]
    assert payload["ok"] is True
    assert payload["profile"] == "production"
    assert payload["summary"]["total"] == len(checks)
    assert payload["summary"]["failed"] == 0
    assert payload["summary"]["warnings"] == 2
    assert payload["summary"]["failed_checks"] == []
    assert set(payload["summary"]["warning_checks"]) == {"ipfs", "web3"}


def test_env_doctor_writes_json_report(tmp_path: Path) -> None:
    checks = env_doctor.run_checks(_production_env(), profile="production")
    payload = env_doctor.json_report_payload(checks, profile="production")
    report_path = tmp_path / "reports" / "env-doctor.json"

    env_doctor.write_json_report(report_path, payload)

    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == 1
    assert written["generated_at"]
    assert written["ok"] is True
    assert written["summary"]["warnings"] == 2
    assert not (report_path.parent / "env-doctor.json.tmp").exists()


def test_env_doctor_replaces_existing_json_report_atomically(tmp_path: Path) -> None:
    checks = env_doctor.run_checks(_production_env(), profile="production")
    payload = env_doctor.json_report_payload(checks, profile="production")
    report_path = tmp_path / "reports" / "env-doctor.json"
    report_path.parent.mkdir()
    report_path.write_text('{"old": true}', encoding="utf-8")

    env_doctor.write_json_report(report_path, payload)

    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == 1
    assert "old" not in written
    assert not (report_path.parent / "env-doctor.json.tmp").exists()


def test_env_source_report_records_env_files_and_process_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.production"
    env_file.write_text("ENV=production\n", encoding="utf-8")

    report = env_doctor.env_source_report([env_file, tmp_path / "missing.env"], include_process_env=False)

    assert report["include_process_env"] is False
    assert report["env_files"][0]["path"] == str(env_file)
    assert report["env_files"][0]["resolved_path"] == str(env_file.resolve())
    assert report["env_files"][0]["exists"] is True
    assert report["env_files"][1]["exists"] is False


def test_local_env_reports_warnings_without_failing() -> None:
    checks = env_doctor.run_checks({}, profile="local")

    assert not [check for check in checks if check.status == "fail"]
    assert {check.id for check in checks if check.status == "warn"} >= {"llm", "auth", "postgres"}


def test_local_env_web3_passes_in_mock_mode() -> None:
    checks = env_doctor.run_checks({"MOCK_MODE": "true"}, profile="local")

    web3_check = next(check for check in checks if check.id == "web3")
    assert web3_check.status == "pass"


def test_local_env_web3_accepts_dao_only_contract_configuration() -> None:
    checks = env_doctor.run_checks(
        {
            "WEB3_RPC_URL": "https://polygon-amoy.infura.io/v3/test-key",
            "DESCI_DAO_CONTRACT_ADDRESS": "0x1234567890123456789012345678901234567890",
        },
        profile="local",
    )

    web3_check = next(check for check in checks if check.id == "web3")
    assert web3_check.status == "pass"
