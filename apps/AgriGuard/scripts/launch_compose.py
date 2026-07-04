from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _default_app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workspace_root(app_root: Path) -> Path:
    if app_root.parent.name == "apps":
        return app_root.parents[1]
    return app_root.parent


def _default_json_out(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-launch-env-preflight-compose-launch.json"


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


def _build_compose_command(app_root: Path, services: list[str], *, build: bool) -> list[str]:
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
    command.extend(services)
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
    parser.add_argument("--dry-run", action="store_true", help="Print the command plan without running preflight or compose.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, command_runner: CommandRunner = subprocess.run) -> int:
    args = parse_args(argv)
    app_root = args.app_root.resolve()
    json_out = args.json_out.resolve() if args.json_out else _default_json_out(app_root)
    preflight_command = _build_preflight_command(app_root, json_out, args.env_file)
    compose_command = _build_compose_command(app_root, args.service, build=not args.no_build)

    if args.dry_run:
        plan = {
            "status": "dry_run",
            "preflight_command": preflight_command,
            "compose_command": compose_command,
            "will_run_compose_after_preflight": True,
        }
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    preflight_result = command_runner(preflight_command, cwd=app_root, text=True)
    if preflight_result.returncode != 0:
        print("AgriGuard launch preflight failed; docker compose up was not run.", file=sys.stderr)
        return preflight_result.returncode

    compose_result = command_runner(compose_command, cwd=app_root, text=True)
    return compose_result.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
