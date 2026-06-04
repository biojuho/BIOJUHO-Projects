from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_STATE_DIR = WORKSPACE_ROOT / "var" / "dev-servers"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import dev_server_status as status_probe  # noqa: E402

PopenFactory = Callable[..., Any]
ProcessChecker = Callable[[int], bool]
Terminator = Callable[[int, float], None]
PortPidFinder = Callable[[int], list[int]]

STOPPED_STATUSES = {"stopped", "not_running", "not_managed", "already_ready"}


def load_validated_manifest(path: Path = status_probe.DEFAULT_MANIFEST) -> dict[str, Any]:
    payload = status_probe.load_manifest(path)
    errors = status_probe.validate_manifest(payload, workspace_root=WORKSPACE_ROOT)
    if errors:
        raise ValueError("\n".join(errors))
    return payload


def get_target(payload: dict[str, Any], target_id: str) -> dict[str, Any]:
    return status_probe.select_targets(payload, [target_id])[0]


def start_target(
    payload: dict[str, Any],
    target_id: str,
    *,
    state_dir: Path = DEFAULT_STATE_DIR,
    wait_ready: bool = False,
    wait_timeout: float = 30.0,
    poll_interval: float = 1.0,
    timeout: float = 2.0,
    reuse_ready: bool = True,
    start_dependencies: bool = False,
    append_logs: bool = False,
    fetcher: status_probe.FetchFn | None = None,
    popen_factory: PopenFactory = subprocess.Popen,
    process_checker: ProcessChecker | None = None,
    sleeper: status_probe.SleepFn = time.sleep,
    clock: status_probe.ClockFn = time.monotonic,
    _seen: set[str] | None = None,
) -> dict[str, Any]:
    process_checker = process_exists if process_checker is None else process_checker
    seen = set() if _seen is None else set(_seen)
    if target_id in seen:
        raise RuntimeError(f"dev-server dependency cycle includes {target_id}")
    seen.add(target_id)
    target = get_target(payload, target_id)
    state_dir.mkdir(parents=True, exist_ok=True)
    paths = state_paths(target_id, state_dir)
    existing = read_state_file(paths["state"])
    existing_pid = _state_pid(existing)
    existing_status = existing.get("status") if existing else None
    dependency_states = []
    if start_dependencies:
        for dependency_id in target.get("depends_on", []):
            dependency_state = start_target(
                payload,
                dependency_id,
                state_dir=state_dir,
                wait_ready=True,
                wait_timeout=wait_timeout,
                poll_interval=poll_interval,
                timeout=timeout,
                reuse_ready=True,
                start_dependencies=True,
                append_logs=append_logs,
                fetcher=fetcher,
                popen_factory=popen_factory,
                process_checker=process_checker,
                sleeper=sleeper,
                clock=clock,
                _seen=seen,
            )
            dependency_states.append(compact_dependency_state(dependency_state))
            last_status = dependency_state.get("last_status", {})
            if last_status.get("summary", {}).get("unready", 0):
                raise RuntimeError(f"dependency {dependency_id} did not become ready")

    if reuse_ready:
        current = status_probe.build_report(payload, target_ids=[target_id], timeout=timeout, fetcher=fetcher)
        if current["summary"]["unready"] == 0:
            state = base_state(target, paths)
            state.update(
                {
                    "status": "already_ready",
                    "managed": existing.get("managed", False) if existing else False,
                    "pid": existing_pid,
                    "checked_at": utc_now(),
                    "last_status": compact_status(current),
                }
            )
            if dependency_states:
                state["dependencies"] = dependency_states
            write_json_atomic(paths["state"], state)
            return state

    if existing_pid and existing_status not in STOPPED_STATUSES and process_checker(existing_pid):
        if reuse_ready and wait_ready:
            report = status_probe.wait_for_ready(
                payload,
                target_ids=[target_id],
                timeout=timeout,
                wait_timeout=wait_timeout,
                poll_interval=poll_interval,
                fetcher=fetcher,
                sleeper=sleeper,
                clock=clock,
            )
            state = base_state(target, paths)
            state.update(
                {
                    "status": "already_running_ready"
                    if report["summary"]["unready"] == 0
                    else "already_running_unready",
                    "managed": existing.get("managed", True) if existing else True,
                    "pid": existing_pid,
                    "checked_at": utc_now(),
                    "last_status": compact_status(report),
                    "wait": report["wait"],
                }
            )
            if dependency_states:
                state["dependencies"] = dependency_states
            write_json_atomic(paths["state"], state)
            return state
        raise RuntimeError(f"{target_id} is already managed with live pid {existing_pid}")

    cwd = (WORKSPACE_ROOT / target["cwd"]).resolve()
    if not cwd.is_dir():
        raise ValueError(f"target cwd does not exist: {target['cwd']}")

    state = base_state(target, paths)
    state.update(
        {
            "status": "started",
            "managed": True,
            "started_at": utc_now(),
        }
    )
    if dependency_states:
        state["dependencies"] = dependency_states
    log_mode = "ab" if append_logs else "wb"
    with paths["stdout"].open(log_mode) as stdout_handle, paths["stderr"].open(log_mode) as stderr_handle:
        header = f"\n[{state['started_at']}] starting {target_id}: {status_probe.format_command(target['command'])}\n"
        stdout_handle.write(header.encode("utf-8"))
        stdout_handle.flush()
        process = popen_factory(
            target["command"],
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            shell=False,
            **process_creation_kwargs(),
        )
        state["pid"] = int(process.pid)
    write_json_atomic(paths["state"], state)

    if wait_ready:
        report = status_probe.wait_for_ready(
            payload,
            target_ids=[target_id],
            timeout=timeout,
            wait_timeout=wait_timeout,
            poll_interval=poll_interval,
            fetcher=fetcher,
            sleeper=sleeper,
            clock=clock,
        )
        state["status"] = "ready" if report["summary"]["unready"] == 0 else "started_unready"
        state["last_status"] = compact_status(report)
        state["wait"] = report["wait"]
        write_json_atomic(paths["state"], state)

    return state


def compact_dependency_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_id": state["target_id"],
        "status": state["status"],
        "managed": state.get("managed"),
        "pid": state.get("pid"),
        "last_status": state.get("last_status"),
    }


def stop_target(
    target_id: str,
    *,
    state_dir: Path = DEFAULT_STATE_DIR,
    timeout: float = 5.0,
    process_checker: ProcessChecker | None = None,
    terminator: Terminator | None = None,
    port_pid_finder: PortPidFinder | None = None,
) -> dict[str, Any]:
    process_checker = process_exists if process_checker is None else process_checker
    terminator = terminate_process_tree if terminator is None else terminator
    port_pid_finder = find_listening_pids if port_pid_finder is None else port_pid_finder
    paths = state_paths(target_id, state_dir)
    state = read_state_file(paths["state"])
    if not state:
        raise RuntimeError(f"no managed state found for {target_id}")

    pid = _state_pid(state)
    managed = state.get("managed", True)
    if pid is None and not managed:
        state["status"] = "not_managed"
        state["checked_at"] = utc_now()
        write_json_atomic(paths["state"], state)
        return state

    stopped_pids: set[int] = set()
    if pid is not None and process_checker(pid):
        terminator(pid, timeout)
        stopped_pids.add(pid)

    port = _url_port(state.get("url"))
    listener_pids = port_pid_finder(port) if port is not None and managed else []
    for listener_pid in listener_pids:
        if listener_pid not in stopped_pids:
            terminator(listener_pid, timeout)
            stopped_pids.add(listener_pid)

    parent_alive = pid is not None and process_checker(pid)
    port_alive = bool(port_pid_finder(port)) if port is not None and managed else False
    if stopped_pids:
        state["status"] = "stop_requested" if parent_alive or port_alive else "stopped"
        state["stopped_at"] = utc_now()
    else:
        state["status"] = "not_running"
        state["checked_at"] = utc_now()
    write_json_atomic(paths["state"], state)
    return state


def stop_target_group(
    payload: dict[str, Any],
    target_id: str,
    *,
    include_dependencies: bool = False,
    state_dir: Path = DEFAULT_STATE_DIR,
    timeout: float = 5.0,
    process_checker: ProcessChecker | None = None,
    terminator: Terminator | None = None,
    port_pid_finder: PortPidFinder | None = None,
) -> dict[str, Any]:
    target_ids = [target_id]
    if include_dependencies:
        target_ids = stop_order_with_dependencies(payload, target_id)

    results = []
    for next_target_id in target_ids:
        try:
            state = stop_target(
                next_target_id,
                state_dir=state_dir,
                timeout=timeout,
                process_checker=process_checker,
                terminator=terminator,
                port_pid_finder=port_pid_finder,
            )
        except RuntimeError as exc:
            if not str(exc).startswith("no managed state found"):
                raise
            state = {
                "schema_version": 1,
                "target_id": next_target_id,
                "status": "not_managed",
                "checked_at": utc_now(),
                "error": str(exc),
            }
        results.append(compact_stop_state(state))

    stopped = sum(1 for result in results if result["status"] in STOPPED_STATUSES)
    return {
        "schema_version": 1,
        "target_id": target_id,
        "include_dependencies": include_dependencies,
        "stop_order": target_ids,
        "status": "stopped" if stopped == len(results) else "partial",
        "summary": {
            "total": len(results),
            "stopped": stopped,
            "remaining": len(results) - stopped,
        },
        "results": results,
        "checked_at": utc_now(),
    }


def stop_order_with_dependencies(payload: dict[str, Any], target_id: str) -> list[str]:
    order: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(next_target_id: str) -> None:
        if next_target_id in visiting:
            raise RuntimeError(f"dev-server dependency cycle includes {next_target_id}")
        if next_target_id in visited:
            return
        visiting.add(next_target_id)
        target = get_target(payload, next_target_id)
        order.append(next_target_id)
        for dependency_id in target.get("depends_on", []):
            visit(dependency_id)
        visiting.remove(next_target_id)
        visited.add(next_target_id)

    visit(target_id)
    return order


def compact_stop_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_id": state["target_id"],
        "status": state["status"],
        "managed": state.get("managed"),
        "pid": state.get("pid"),
        "error": state.get("error"),
    }


def tail_target(target_id: str, *, state_dir: Path = DEFAULT_STATE_DIR, lines: int = 40) -> dict[str, Any]:
    paths = state_paths(target_id, state_dir)
    return {
        "schema_version": 1,
        "target_id": target_id,
        "stdout_log": display_path(paths["stdout"]),
        "stderr_log": display_path(paths["stderr"]),
        "stdout": tail_file(paths["stdout"], lines),
        "stderr": tail_file(paths["stderr"], lines),
    }


def base_state(target: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "target_id": target["id"],
        "label": target["label"],
        "project": target["project"],
        "kind": target["kind"],
        "cwd": target["cwd"],
        "command": status_probe.format_command(target["command"]),
        "url": target["url"],
        "stdout_log": display_path(paths["stdout"]),
        "stderr_log": display_path(paths["stderr"]),
    }


def compact_status(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": report["generated_at"],
        "status": report["status"],
        "summary": report["summary"],
        "targets": [
            {
                "id": target["id"],
                "ok": target["ok"],
                "status_code": target["status_code"],
                "error": target["error"],
                "url": target["url"],
                "dependencies": target.get("dependencies", []),
            }
            for target in report["targets"]
        ],
    }


def state_paths(target_id: str, state_dir: Path = DEFAULT_STATE_DIR) -> dict[str, Path]:
    return {
        "state": state_dir / f"{target_id}.json",
        "stdout": state_dir / f"{target_id}.out.log",
        "stderr": state_dir / f"{target_id}.err.log",
    }


def read_state_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"state file must be an object: {path}")
    return payload


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        return f'","{pid}",' in result.stdout
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def terminate_process_tree(pid: int, timeout: float = 5.0) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        wait_for_process_exit(pid, timeout)
        if process_exists(pid):
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            wait_for_process_exit(pid, timeout)
        return

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + max(timeout, 0.0)
    while process_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    if process_exists(pid):
        os.killpg(pid, signal.SIGKILL)


def find_listening_pids(port: int) -> list[int]:
    if os.name == "nt":
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        pids: set[int] = set()
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[3].upper() == "LISTENING" and _address_matches_port(parts[1], port):
                try:
                    pids.add(int(parts[4]))
                except ValueError:
                    continue
        return sorted(pids)

    result = subprocess.run(
        ["lsof", f"-tiTCP:{port}", "-sTCP:LISTEN"],
        check=False,
        capture_output=True,
        text=True,
    )
    pids = []
    for line in result.stdout.splitlines():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            continue
    return sorted(set(pids))


def wait_for_process_exit(pid: int, timeout: float) -> None:
    deadline = time.monotonic() + max(timeout, 0.0)
    while process_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.1)


def process_creation_kwargs() -> dict[str, Any]:
    if os.name == "nt":
        flags = 0
        for name in ("CREATE_NEW_PROCESS_GROUP", "CREATE_NO_WINDOW"):
            flags |= int(getattr(subprocess, name, 0))
        return {"creationflags": flags}
    return {"start_new_session": True}


def tail_file(path: Path, lines: int) -> list[str]:
    if not path.exists():
        return []
    selected = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return selected[-max(lines, 0) :]


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(path)


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _state_pid(state: dict[str, Any] | None) -> int | None:
    if not state:
        return None
    pid = state.get("pid")
    return pid if isinstance(pid, int) else None


def _url_port(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    return parsed.port


def _address_matches_port(address: str, port: int) -> bool:
    return address.endswith(f":{port}") or address.endswith(f".{port}")


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="Start, stop, and inspect manifest-backed local dev servers.")
    parser.add_argument("--manifest", type=Path, default=status_probe.DEFAULT_MANIFEST)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--json-out", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--target", required=True)
    start_parser.add_argument("--wait-ready", action="store_true")
    start_parser.add_argument("--wait-timeout", type=float, default=30.0)
    start_parser.add_argument("--poll-interval", type=float, default=1.0)
    start_parser.add_argument("--timeout", type=float, default=2.0)
    start_parser.add_argument("--no-reuse-ready", action="store_true")
    start_parser.add_argument("--no-start-dependencies", action="store_true")
    start_parser.add_argument("--append-logs", action="store_true")

    stop_parser = subparsers.add_parser("stop")
    stop_parser.add_argument("--target", required=True)
    stop_parser.add_argument("--timeout", type=float, default=5.0)
    stop_parser.add_argument("--include-dependencies", action="store_true")

    tail_parser = subparsers.add_parser("tail")
    tail_parser.add_argument("--target", required=True)
    tail_parser.add_argument("--lines", type=int, default=40)

    args = parser.parse_args(argv)

    try:
        if args.command == "start":
            payload = load_validated_manifest(args.manifest)
            result = start_target(
                payload,
                args.target,
                state_dir=args.state_dir,
                wait_ready=args.wait_ready,
                wait_timeout=args.wait_timeout,
                poll_interval=args.poll_interval,
                timeout=args.timeout,
                reuse_ready=not args.no_reuse_ready,
                start_dependencies=not args.no_start_dependencies,
                append_logs=args.append_logs,
            )
            if args.json_out:
                write_json_atomic(args.json_out, result)
            _print_start_result(result)
            if args.wait_ready and result.get("last_status", {}).get("summary", {}).get("unready", 0):
                return 1
            return 0
        if args.command == "stop":
            if args.include_dependencies:
                payload = load_validated_manifest(args.manifest)
                result = stop_target_group(
                    payload,
                    args.target,
                    include_dependencies=True,
                    state_dir=args.state_dir,
                    timeout=args.timeout,
                )
            else:
                result = stop_target(args.target, state_dir=args.state_dir, timeout=args.timeout)
            if args.json_out:
                write_json_atomic(args.json_out, result)
            if args.include_dependencies:
                summary = result["summary"]
                print(
                    f"dev server group {result['status']}: {args.target} "
                    f"stopped={summary['stopped']}/{summary['total']}"
                )
                return 0 if result["status"] == "stopped" else 1
            print(f"dev server {result['status']}: {args.target}")
            return 0 if result["status"] in STOPPED_STATUSES or result["status"] == "stopped" else 1
        if args.command == "tail":
            result = tail_target(args.target, state_dir=args.state_dir, lines=args.lines)
            if args.json_out:
                write_json_atomic(args.json_out, result)
            print(f"==> {result['stdout_log']}")
            print("\n".join(result["stdout"]))
            print(f"==> {result['stderr_log']}", file=sys.stderr)
            print("\n".join(result["stderr"]), file=sys.stderr)
            return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"dev server control failed: {exc}", file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled command: {args.command}")


def _print_start_result(result: dict[str, Any]) -> None:
    if result["status"] == "already_ready":
        print(f"dev server already ready: {result['target_id']}")
        return
    wait = result.get("wait")
    wait_suffix = f", attempts={wait['attempts']}" if wait else ""
    pid = result.get("pid")
    print(f"dev server {result['status']}: {result['target_id']} pid={pid}{wait_suffix}")


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
