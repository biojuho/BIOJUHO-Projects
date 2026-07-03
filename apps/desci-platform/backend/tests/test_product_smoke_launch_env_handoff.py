import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "product_smoke.py"


def load_product_smoke_module():
    script_dir = str(SCRIPT_PATH.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("product_smoke_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_launch_env_handoff_groups_required_and_optional_placeholders() -> None:
    product_smoke = load_product_smoke_module()
    launch_handoff = {
        "next_actions": [
            {
                "id": "auth",
                "required": True,
                "status": "fail",
                "required_env": ["GOOGLE_APPLICATION_CREDENTIALS", "FIREBASE_SERVICE_ACCOUNT_JSON"],
            },
            {
                "id": "stripe",
                "required": True,
                "status": "fail",
                "required_env": ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"],
            },
            {
                "id": "ipfs",
                "required": False,
                "status": "warn",
                "required_env": ["PINATA_JWT", "STRIPE_SECRET_KEY"],
            },
        ],
    }

    handoff = product_smoke.launch_env_handoff_report(launch_handoff)

    assert handoff == {
        "schema_version": 1,
        "status": "blocked",
        "secret_policy": "placeholder_only_no_secret_values",
        "required_action_ids": ["auth", "stripe"],
        "optional_action_ids": ["ipfs"],
        "required_env": [
            "GOOGLE_APPLICATION_CREDENTIALS",
            "FIREBASE_SERVICE_ACCOUNT_JSON",
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
        ],
        "optional_env": ["PINATA_JWT"],
        "operator_copy_lines": [
            "# DSCI launch env handoff",
            "# Replace placeholders in the target secret manager or runtime env.",
            "# Required before release",
            "GOOGLE_APPLICATION_CREDENTIALS=<set-secure-value>",
            "FIREBASE_SERVICE_ACCOUNT_JSON=<set-secure-value>",
            "STRIPE_SECRET_KEY=<set-secure-value>",
            "STRIPE_WEBHOOK_SECRET=<set-secure-value>",
            "# Optional before public launch hardening",
            "PINATA_JWT=<set-secure-value>",
        ],
    }
    assert not any("http" in line or "sk_" in line or "0x" in line for line in handoff["operator_copy_lines"])


def test_launch_env_handoff_reports_clear_when_no_actions_remain() -> None:
    product_smoke = load_product_smoke_module()

    handoff = product_smoke.launch_env_handoff_report({"next_actions": []})

    assert handoff["status"] == "clear"
    assert handoff["required_env"] == []
    assert handoff["optional_env"] == []
    assert handoff["operator_copy_lines"][-1] == "# No launch env blockers reported by product smoke."
