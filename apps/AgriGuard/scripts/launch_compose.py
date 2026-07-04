from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
DEFAULT_COMPOSE_BROWSER_BASE_URL = "http://127.0.0.1"
DEFAULT_COMPOSE_BROWSER_API_URL = "http://127.0.0.1:8002"


def _default_app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workspace_root(app_root: Path) -> Path:
    if app_root.parent.name == "apps":
        return app_root.parents[1]
    return app_root.parent


def _default_json_out(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-launch-env-preflight-compose-launch.json"


def _default_browser_smoke_json_out(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-browser-smoke-suite-compose-launch.json"


def _default_browser_smoke_output_dir(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-browser-smoke-suite-compose-launch"


def _build_preflight_command(app_root: Path, json_out: Path, env_files: list[Path]) -> list[str]:
    command = [
        sys.executable,
        str(app_root / "scripts" / "launch_env_preflight.py"),
        "--check-docker",
        "--json-out",
        str(json_out),
    ]
    for env_file in env_files:
        command.extend(["--env-file", str(env_file)])
    return command


def _build_compose_command(app_root: Path, services: list[str], *, build: bool, wait: bool) -> list[str]:
    command = [
        "docker",
        "compose",
        "-f",
        str(app_root / "docker-compose.yml"),
        "up",
        "-d",
    ]
    if build:
        command.append("--build")
    if wait:
        command.append("--wait")
    command.extend(services)
    return command


def _build_browser_smoke_command(
    app_root: Path,
    *,
    base_url: str,
    api_url: str,
    json_out: Path,
    output_dir: Path,
    timeout_ms: int,
    mobile: bool,
) -> list[str]:
    command = [
        sys.executable,
        str(app_root / "scripts" / "run_browser_smoke_suite.py"),
        "--base-url",
        base_url,
        "--api-url",
        api_url,
        "--json-out",
        str(json_out),
        "--output-dir",
        str(output_dir),
        "--timeout-ms",
        str(timeout_ms),
    ]
    if mobile:
        command.append("--mobile")
    return command


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AgriGuard compose launch behind strict preflight.")
    parser.add_argument("--app-root", type=Path, default=_default_app_root(), help="AgriGuard app root.")
    parser.add_argument(
        "--env-file",
        action="append",
        type=Path,
        default=[],
        help="Optional env file passed to launch_env_preflight.py. May be repeated.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Preflight JSON output path. Defaults to workspace var/agriguard-launch-env-preflight-compose-launch.json.",
    )
    parser.add_argument(
        "--service",
        action="append",
        default=[],
        help="Optional compose service to launch. May be repeated. Defaults to all services.",
    )
    parser.add_argument("--no-build", action="store_true", help="Do not pass --build to docker compose up.")
    parser.add_argument(
        "--run-browser-smoke",
        action="store_true",
        help="After compose starts successfully, run the aggregate browser smoke suite.",
    )
    parser.add_argument(
        "--no-compose-wait",
        action="store_true",
        help="Do not pass --wait to docker compose up when --run-browser-smoke is enabled.",
    )
    parser.add_argument(
        "--browser-base-url",
        default=DEFAULT_COMPOSE_BROWSER_BASE_URL,
        help=f"Frontend base URL for post-compose browser smoke. Defaults to {DEFAULT_COMPOSE_BROWSER_BASE_URL}.",
    )
    parser.add_argument(
        "--browser-api-url",
        default=DEFAULT_COMPOSE_BROWSER_API_URL,
        help=f"Backend API URL for post-compose browser smoke. Defaults to {DEFAULT_COMPOSE_BROWSER_API_URL}.",
    )
    parser.add_argument(
        "--browser-smoke-json-out",
        type=Path,
        default=None,
        help="Post-compose browser smoke JSON output path.",
    )
    parser.add_argument(
        "--browser-smoke-output-dir",
        type=Path,
        default=None,
        help="Post-compose browser smoke artifact directory.",
    )
    parser.add_argument("--browser-smoke-timeout-ms", type=int, default=30_000)
    parser.add_argument("--browser-smoke-mobile", action="store_true", help="Run post-compose browser smoke mobile variants.")
    parser.add_argument("--dry-run", action="store_true", help="Print the command plan without running preflight or compose.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, command_runner: CommandRunner = subprocess.run) -> int:
    args = parse_args(argv)
    app_root = args.app_root.resolve()
    json_out = args.json_out.resolve() if args.json_out else _default_json_out(app_root)
    browser_smoke_json_out = (
        args.browser_smoke_json_out.resolve()
        if args.browser_smoke_json_out
        else _default_browser_smoke_json_out(app_root)
    )
    browser_smoke_output_dir = (
        args.browser_smoke_output_dir.resolve()
        if args.browser_smoke_output_dir
        else _default_browser_smoke_output_dir(app_root)
    )
    preflight_command = _build_preflight_command(app_root, json_out, args.env_file)
    compose_command = _build_compose_command(
        app_root,
        args.service,
        build=not args.no_build,
        wait=args.run_browser_smoke and not args.no_compose_wait,
    )
    browser_smoke_command = (
        _build_browser_smoke_command(
            app_root,
            base_url=args.browser_base_url,
            api_url=args.browser_api_url,
            json_out=browser_smoke_json_out,
            output_dir=browser_smoke_output_dir,
            timeout_ms=args.browser_smoke_timeout_ms,
            mobile=args.browser_smoke_mobile,
        )
        if args.run_browser_smoke
        else None
    )

    if args.dry_run:
        plan = {
            "status": "dry_run",
            "preflight_command": preflight_command,
            "compose_command": compose_command,
            "browser_smoke_command": browser_smoke_command,
            "will_run_compose_after_preflight": True,
            "will_run_browser_smoke_after_compose": args.run_browser_smoke,
        }
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    preflight_result = command_runner(preflight_command, cwd=app_root, text=True)
    if preflight_result.returncode != 0:
        print("AgriGuard launch preflight failed; docker compose up was not run.", file=sys.stderr)
        return preflight_result.returncode

    compose_result = command_runner(compose_command, cwd=app_root, text=True)
    if compose_result.returncode != 0 or browser_smoke_command is None:
        return compose_result.returncode

    browser_smoke_result = command_runner(browser_smoke_command, cwd=app_root, text=True)
    return browser_smoke_result.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
