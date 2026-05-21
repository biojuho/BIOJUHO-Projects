from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import env_doctor  # noqa: E402


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
        "VITE_API_BASE_URL": "https://api.dsci.example",
        "ALLOWED_ORIGINS": "https://app.dsci.example",
        "DATABASE_URL": "postgresql://user:pass@db:5432/desci",
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
        "REDIS_URL": "rediss://redis:6379/0",
        "RABBITMQ_URL": "amqps://rabbitmq:5671/desci",
    }


def test_production_env_required_checks_pass() -> None:
    checks = env_doctor.run_checks(_production_env(), profile="production")

    failed = [check.id for check in checks if check.status == "fail"]

    assert failed == []


def test_production_env_rejects_placeholders() -> None:
    env = _production_env()
    env["GOOGLE_API_KEY"] = "your_google_api_key_here"
    env["SUPABASE_SERVICE_ROLE_KEY"] = "your_supabase_service_role_key"

    checks = env_doctor.run_checks(env, profile="production")
    failed = {check.id for check in checks if check.status == "fail"}

    assert {"llm", "supabase"} <= failed


def test_local_env_reports_warnings_without_failing() -> None:
    checks = env_doctor.run_checks({}, profile="local")

    assert not [check for check in checks if check.status == "fail"]
    assert {check.id for check in checks if check.status == "warn"} >= {"llm", "auth", "postgres"}
