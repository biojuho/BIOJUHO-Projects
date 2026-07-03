from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


AGRIGUARD_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = AGRIGUARD_ROOT / "backend"
WORKSPACE_ROOT = AGRIGUARD_ROOT.parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.mqtt_broker_provisioning import build_acl_file  # noqa: E402


IMAGE = "eclipse-mosquitto:2"
ACTIVE_SENSOR_ID = "sensor-active-1"
ACTIVE_PASSWORD = "active-secret"
DISABLED_SENSOR_ID = "sensor-disabled-1"
DISABLED_PASSWORD = "disabled-secret"
INTRUDER_SENSOR_ID = "sensor-intruder-1"
INTRUDER_PASSWORD = "intruder-secret"


@dataclass
class CommandResult:
    name: str
    returncode: int
    stdout: str
    stderr: str
    command: list[str]

    def to_summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "returncode": self.returncode,
            "stdout_tail": self.stdout[-500:],
            "stderr_tail": self.stderr[-500:],
            "command": _sanitize_command(self.command),
        }


def _sanitize_command(command: list[str]) -> list[str]:
    sanitized: list[str] = []
    hide_next = False
    for part in command:
        if hide_next:
            sanitized.append("<redacted>")
            hide_next = False
            continue
        sanitized.append(part)
        if part in {"-P", "--pw", "--password"}:
            hide_next = True
    return sanitized


def _run(name: str, command: list[str], *, timeout: int = 20, check: bool = False) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        result = CommandResult(
            name=name,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            command=command,
        )
    except subprocess.TimeoutExpired as exc:
        result = CommandResult(
            name=name,
            returncode=124,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else f"Timed out after {timeout}s",
            command=command,
        )

    if check and result.returncode != 0:
        raise RuntimeError(json.dumps(result.to_summary(), ensure_ascii=False))
    return result


def _write_smoke_files(work_dir: Path) -> dict[str, str]:
    config_dir = work_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    acl_path = config_dir / "aclfile"
    passwd_path = config_dir / "passwd"
    conf_path = config_dir / "mosquitto.conf"

    acl_path.write_text(build_acl_file([ACTIVE_SENSOR_ID]), encoding="utf-8")
    passwd_path.write_text(
        "\n".join(
            [
                f"{ACTIVE_SENSOR_ID}:{ACTIVE_PASSWORD}",
                f"{DISABLED_SENSOR_ID}:{DISABLED_PASSWORD}",
                f"{INTRUDER_SENSOR_ID}:{INTRUDER_PASSWORD}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    conf_path.write_text(
        "\n".join(
            [
                "listener 1883 0.0.0.0",
                "allow_anonymous false",
                "password_file /mosquitto/config/passwd",
                "acl_file /mosquitto/config/aclfile",
                "persistence false",
                "log_dest stdout",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "config_dir": str(config_dir),
        "acl_path": str(acl_path),
        "passwd_path": str(passwd_path),
        "conf_path": str(conf_path),
    }


def _docker_available(timeout: int) -> CommandResult:
    return _run("docker_info", ["docker", "info", "--format", "{{.ServerVersion}}"], timeout=timeout)


def _docker_run(
    *,
    name: str,
    config_dir: Path,
    timeout: int,
) -> CommandResult:
    return _run(
        "start_broker",
        [
            "docker",
            "run",
            "--rm",
            "-d",
            "--name",
            name,
            "-v",
            f"{config_dir}:/mosquitto/config",
            IMAGE,
            "mosquitto",
            "-c",
            "/mosquitto/config/mosquitto.conf",
        ],
        timeout=timeout,
    )


def _client_publish(
    *,
    container_name: str,
    username: str,
    password: str,
    topic: str,
    payload: str,
    timeout: int,
) -> CommandResult:
    return _run(
        f"publish:{username}:{topic}",
        [
            "docker",
            "exec",
            container_name,
            "mosquitto_pub",
            "-h",
            "127.0.0.1",
            "-p",
            "1883",
            "-V",
            "mqttv5",
            "-q",
            "1",
            "-u",
            username,
            "-P",
            password,
            "-t",
            topic,
            "-m",
            payload,
        ],
        timeout=timeout,
    )


def _publish_output(result: CommandResult) -> str:
    return f"{result.stdout}\n{result.stderr}".lower()


def _publish_allowed(result: CommandResult) -> bool:
    return result.returncode == 0 and "not authorized" not in _publish_output(result)


def _publish_denied(result: CommandResult) -> bool:
    output = _publish_output(result)
    return result.returncode != 0 or "not authorized" in output or "not authorised" in output


def _wait_for_broker(container_name: str, timeout: int) -> CommandResult:
    deadline = time.monotonic() + timeout
    last_result: CommandResult | None = None
    while time.monotonic() < deadline:
        last_result = _client_publish(
            container_name=container_name,
            username=ACTIVE_SENSOR_ID,
            password=ACTIVE_PASSWORD,
            topic=f"agriguard/sensors/{ACTIVE_SENSOR_ID}",
            payload='{"temperature":4.2}',
            timeout=8,
        )
        if _publish_allowed(last_result):
            return last_result
        time.sleep(1)
    if last_result is not None:
        return last_result
    return CommandResult("wait_for_broker", 124, "", "Broker did not become ready", [])


def _run_live_smoke(work_dir: Path, *, docker_timeout: int, keep_work_dir: bool) -> dict[str, Any]:
    paths = _write_smoke_files(work_dir)
    config_dir = Path(paths["config_dir"])
    suffix = uuid.uuid4().hex[:12]
    container_name = f"agriguard-mqtt-broker-{suffix}"
    command_results: list[CommandResult] = []
    status = "internal_error"
    passed = False

    try:
        command_results.append(_docker_available(docker_timeout))
        if command_results[-1].returncode != 0:
            status = "docker_unavailable"
        else:
            command_results.append(
                _run(
                    "hash_password_file",
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--user",
                        "0:0",
                        "-v",
                        f"{config_dir}:/mosquitto/config",
                        IMAGE,
                        "mosquitto_passwd",
                        "-U",
                        "/mosquitto/config/passwd",
                    ],
                    timeout=docker_timeout,
                )
            )
            if command_results[-1].returncode != 0:
                status = "password_hash_failed"
            else:
                command_results.append(
                    _docker_run(name=container_name, config_dir=config_dir, timeout=docker_timeout)
                )
                if command_results[-1].returncode != 0:
                    status = "broker_start_failed"
                else:
                    command_results.append(_wait_for_broker(container_name, timeout=30))
                    allowed_publish_ok = _publish_allowed(command_results[-1])

                    denied_topic = _client_publish(
                        container_name=container_name,
                        username=ACTIVE_SENSOR_ID,
                        password=ACTIVE_PASSWORD,
                        topic=f"agriguard/sensors/{DISABLED_SENSOR_ID}",
                        payload='{"temperature":9.1}',
                        timeout=10,
                    )
                    command_results.append(denied_topic)

                    disabled_publish = _client_publish(
                        container_name=container_name,
                        username=DISABLED_SENSOR_ID,
                        password=DISABLED_PASSWORD,
                        topic=f"agriguard/sensors/{DISABLED_SENSOR_ID}",
                        payload='{"temperature":9.1}',
                        timeout=10,
                    )
                    command_results.append(disabled_publish)

                    intruder_publish = _client_publish(
                        container_name=container_name,
                        username=INTRUDER_SENSOR_ID,
                        password=INTRUDER_PASSWORD,
                        topic=f"agriguard/sensors/{INTRUDER_SENSOR_ID}",
                        payload='{"temperature":9.1}',
                        timeout=10,
                    )
                    command_results.append(intruder_publish)

                    passed = (
                        allowed_publish_ok
                        and _publish_denied(denied_topic)
                        and _publish_denied(disabled_publish)
                        and _publish_denied(intruder_publish)
                    )
                    status = "passed" if passed else "acl_behavior_failed"
    finally:
        cleanup_timeout = max(30, docker_timeout)
        command_results.append(_run("broker_logs", ["docker", "logs", container_name], timeout=cleanup_timeout))
        command_results.append(_run("remove_broker", ["docker", "rm", "-f", container_name], timeout=cleanup_timeout))

    return _summary(status, passed, paths, command_results, keep_work_dir=keep_work_dir)


def _summary(
    status: str,
    passed: bool,
    paths: dict[str, str],
    command_results: list[CommandResult],
    *,
    keep_work_dir: bool,
) -> dict[str, Any]:
    return {
        "status": status,
        "passed": passed,
        "active_sensor_id": ACTIVE_SENSOR_ID,
        "disabled_sensor_id": DISABLED_SENSOR_ID,
        "intruder_sensor_id": INTRUDER_SENSOR_ID,
        "work_dir": str(Path(paths["config_dir"]).parent),
        "keep_work_dir": keep_work_dir,
        "paths": paths,
        "commands": [result.to_summary() for result in command_results if result.command],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an AgriGuard Mosquitto ACL publish smoke.")
    parser.add_argument("--work-dir", type=Path, default=None, help="Directory for temporary Mosquitto config files.")
    parser.add_argument("--dry-run", action="store_true", help="Write config files and print summary without Docker.")
    parser.add_argument("--keep-work-dir", action="store_true", help="Do not remove generated temporary files.")
    parser.add_argument("--docker-timeout", type=int, default=60, help="Per-command Docker timeout in seconds.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    temp_parent = WORKSPACE_ROOT / ".smoke-tmp"
    temp_parent.mkdir(parents=True, exist_ok=True)
    root = args.work_dir or Path(tempfile.mkdtemp(prefix="agriguard-mqtt-acl-", dir=temp_parent))
    root.mkdir(parents=True, exist_ok=True)

    try:
        paths = _write_smoke_files(root)
        if args.dry_run:
            summary = _summary("dry_run", True, paths, [], keep_work_dir=True)
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 0

        summary = _run_live_smoke(root, docker_timeout=args.docker_timeout, keep_work_dir=args.keep_work_dir)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0 if summary["passed"] else 2
    finally:
        should_remove = not args.keep_work_dir and not args.dry_run
        if should_remove:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
