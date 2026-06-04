from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTROL_SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "dev_server_control.py"
MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "dev_server_targets.json"


def load_control_module():
    spec = importlib.util.spec_from_file_location("dev_server_control", CONTROL_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_start_target_spawns_manifest_command_and_writes_state(tmp_path: Path) -> None:
    control = load_control_module()
    payload = control.load_validated_manifest(MANIFEST_PATH)
    captured = {}
    (tmp_path / "dashboard-frontend.out.log").write_text("old run\n", encoding="utf-8")

    class FakeProcess:
        pid = 4242

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    state = control.start_target(
        payload,
        "dashboard-frontend",
        state_dir=tmp_path,
        reuse_ready=False,
        popen_factory=fake_popen,
        process_checker=lambda _pid: False,
    )

    written = json.loads((tmp_path / "dashboard-frontend.json").read_text(encoding="utf-8"))
    assert state["status"] == "started"
    assert written["pid"] == 4242
    assert written["managed"] is True
    assert captured["command"] == payload["targets"][1]["command"]
    assert captured["kwargs"]["cwd"] == str(PROJECT_ROOT / "apps" / "dashboard")
    assert captured["kwargs"]["shell"] is False
    stdout_log = (tmp_path / "dashboard-frontend.out.log").read_text(encoding="utf-8")
    assert "starting dashboard-frontend" in stdout_log
    assert "old run" not in stdout_log


def test_start_target_reuses_already_ready_target_without_spawning(tmp_path: Path) -> None:
    control = load_control_module()
    payload = control.load_validated_manifest(MANIFEST_PATH)

    def fake_popen(_command, **_kwargs):
        raise AssertionError("ready targets should not spawn a duplicate process")

    state = control.start_target(
        payload,
        "dashboard-api",
        state_dir=tmp_path,
        fetcher=lambda _url, _timeout: (200, 3, '{"workspace_smoke":{}}', None),
        popen_factory=fake_popen,
    )

    assert state["status"] == "already_ready"
    assert state["managed"] is False
    assert state["pid"] is None
    assert state["last_status"]["summary"] == {"total": 1, "ready": 1, "unready": 0}


def test_start_target_can_start_dependencies_before_frontend(tmp_path: Path) -> None:
    control = load_control_module()
    payload = control.load_validated_manifest(MANIFEST_PATH)
    commands = []
    next_pid = {"value": 5000}
    probes = {"api": 0, "frontend": 0}

    class FakeProcess:
        def __init__(self, pid: int) -> None:
            self.pid = pid

    def fake_popen(command, **_kwargs):
        commands.append(command)
        next_pid["value"] += 1
        return FakeProcess(next_pid["value"])

    def fetcher(url: str, _timeout: float):
        if "8080" in url:
            probes["api"] += 1
            if probes["api"] == 1:
                return None, 1, None, "offline"
            return 200, 2, '{"workspace_smoke":{}}', None
        if "5173" in url:
            probes["frontend"] += 1
            if probes["frontend"] == 1:
                return None, 1, None, "offline"
            return 200, 2, "AI Projects Dashboard", None
        raise AssertionError(f"unexpected URL: {url}")

    state = control.start_target(
        payload,
        "dashboard-frontend",
        state_dir=tmp_path,
        wait_ready=True,
        start_dependencies=True,
        fetcher=fetcher,
        popen_factory=fake_popen,
        process_checker=lambda _pid: False,
        sleeper=lambda _seconds: None,
    )

    assert commands == [payload["targets"][0]["command"], payload["targets"][1]["command"]]
    assert state["status"] == "ready"
    assert state["dependencies"][0]["target_id"] == "dashboard-api"
    assert state["last_status"]["summary"] == {"total": 1, "ready": 1, "unready": 0}


def test_start_target_refuses_existing_live_managed_pid(tmp_path: Path) -> None:
    control = load_control_module()
    payload = control.load_validated_manifest(MANIFEST_PATH)
    (tmp_path / "dashboard-api.json").write_text(
        json.dumps({"schema_version": 1, "target_id": "dashboard-api", "status": "started", "pid": 1111}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="already managed"):
        control.start_target(
            payload,
            "dashboard-api",
            state_dir=tmp_path,
            reuse_ready=False,
            process_checker=lambda _pid: True,
        )


def test_stop_target_requests_termination_and_marks_stopped(tmp_path: Path) -> None:
    control = load_control_module()
    (tmp_path / "dashboard-api.json").write_text(
        json.dumps({"schema_version": 1, "target_id": "dashboard-api", "status": "started", "pid": 2222}),
        encoding="utf-8",
    )
    alive = {"value": True}
    terminated = []

    def process_checker(_pid: int) -> bool:
        return alive["value"]

    def terminator(pid: int, timeout: float) -> None:
        terminated.append((pid, timeout))
        alive["value"] = False

    state = control.stop_target(
        "dashboard-api",
        state_dir=tmp_path,
        timeout=2.5,
        process_checker=process_checker,
        terminator=terminator,
    )

    assert terminated == [(2222, 2.5)]
    assert state["status"] == "stopped"
    assert "stopped_at" in state


def test_stop_target_falls_back_to_managed_listener_port(tmp_path: Path) -> None:
    control = load_control_module()
    (tmp_path / "dashboard-frontend.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "target_id": "dashboard-frontend",
                "status": "not_running",
                "managed": True,
                "pid": 3333,
                "url": "http://127.0.0.1:5173/",
            }
        ),
        encoding="utf-8",
    )
    listeners = {"pids": [4444]}
    terminated = []

    def port_pid_finder(port: int) -> list[int]:
        assert port == 5173
        return list(listeners["pids"])

    def terminator(pid: int, _timeout: float) -> None:
        terminated.append(pid)
        listeners["pids"] = [value for value in listeners["pids"] if value != pid]

    state = control.stop_target(
        "dashboard-frontend",
        state_dir=tmp_path,
        process_checker=lambda _pid: False,
        terminator=terminator,
        port_pid_finder=port_pid_finder,
    )

    assert terminated == [4444]
    assert state["status"] == "stopped"


def test_tail_target_returns_recent_stdout_and_stderr(tmp_path: Path) -> None:
    control = load_control_module()
    (tmp_path / "dashboard-api.out.log").write_text("one\ntwo\nthree\n", encoding="utf-8")
    (tmp_path / "dashboard-api.err.log").write_text("red\nblue\n", encoding="utf-8")

    result = control.tail_target("dashboard-api", state_dir=tmp_path, lines=2)

    assert result["stdout"] == ["two", "three"]
    assert result["stderr"] == ["red", "blue"]
