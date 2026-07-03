from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
AGRIGUARD_ROOT = BACKEND_DIR.parent
SMOKE_SCRIPT = AGRIGUARD_ROOT / "scripts" / "smoke_mqtt_broker_acl.py"


def test_mqtt_broker_acl_smoke_dry_run_writes_strict_config(tmp_path):
    work_dir = tmp_path / "mqtt-acl-smoke"

    result = subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT), "--dry-run", "--work-dir", str(work_dir)],
        cwd=AGRIGUARD_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "dry_run"
    assert payload["passed"] is True
    assert "active-secret" not in result.stdout
    assert "disabled-secret" not in result.stdout
    assert "intruder-secret" not in result.stdout

    conf_path = Path(payload["paths"]["conf_path"])
    acl_path = Path(payload["paths"]["acl_path"])
    passwd_path = Path(payload["paths"]["passwd_path"])
    assert conf_path.exists()
    assert acl_path.exists()
    assert passwd_path.exists()

    conf = conf_path.read_text(encoding="utf-8")
    assert "allow_anonymous false" in conf
    assert "password_file /mosquitto/config/passwd" in conf
    assert "acl_file /mosquitto/config/aclfile" in conf

    acl = acl_path.read_text(encoding="utf-8")
    assert "user sensor-active-1" in acl
    assert "topic write agriguard/sensors/sensor-active-1" in acl
    assert "sensor-disabled-1" not in acl
    assert "sensor-intruder-1" not in acl

    passwd = passwd_path.read_text(encoding="utf-8")
    assert "sensor-active-1:active-secret" in passwd
    assert "sensor-disabled-1:disabled-secret" in passwd
    assert "sensor-intruder-1:intruder-secret" in passwd
