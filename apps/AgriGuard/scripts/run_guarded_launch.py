from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
DEFAULT_OUTPUT_PREFIX = "agriguard-guarded-launch"


def _default_app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workspace_root(app_root: Path) -> Path:
    if app_root.parent.name == "apps":
        return app_root.parents[1]
    return app_root.parent


def _default_env_file(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-launch-operator.env.template"


def _artifact_paths(output_dir: Path, output_prefix: str) -> dict[str, Path]:
    prefix = output_dir / output_prefix
    return {
        "env_validation_json": prefix.with_name(f"{prefix.name}-env-validation.json"),
        "env_validation_markdown": prefix.with_name(f"{prefix.name}-env-validation.md"),
        "preflight_json": prefix.with_name(f"{prefix.name}-preflight.json"),
        "launch_report_json": prefix.with_name(f"{prefix.name}-launch-report.json"),
        "operator_packet_json": prefix.with_name(f"{prefix.name}-operator-packet.json"),
        "operator_packet_markdown": prefix.with_name(f"{prefix.name}-operator-packet.md"),
        "operator_env_template": prefix.with_name(f"{prefix.name}.env.template"),
        "readiness_summary_json": prefix.with_name(f"{prefix.name}-readiness-summary.json"),
        "readiness_summary_markdown": prefix.with_name(f"{prefix.name}-readiness-summary.md"),
    }


def _build_launch_command(
    *,
    app_root: Path,
    env_file: Path,
    artifact_paths: dict[str, Path],
    compose_files: list[Path],
    services: list[str],
    run_browser_smoke: bool,
) -> list[str]:
    command = [
        sys.executable,
        str(app_root / "scripts" / "launch_compose.py"),
    ]
    for compose_file in compose_files:
        command.extend(["--compose-file", str(compose_file)])
    for service in services:
        command.extend(["--service", service])
    command.extend(
        [
            "--env-file",
            str(env_file),
            "--validate-env-file-shape",
            "--env-validation-json-out",
            str(artifact_paths["env_validation_json"]),
            "--env-validation-markdown-out",
            str(artifact_paths["env_validation_markdown"]),
            "--json-out",
            str(artifact_paths["preflight_json"]),
            "--launch-report-json",
            str(artifact_paths["launch_report_json"]),
            "--operator-packet-json",
            str(artifact_paths["operator_packet_json"]),
            "--operator-packet-markdown",
            str(artifact_paths["operator_packet_markdown"]),
            "--operator-env-template",
            str(artifact_paths["operator_env_template"]),
            "--readiness-summary-json",
            str(artifact_paths["readiness_summary_json"]),
            "--readiness-summary-markdown",
            str(artifact_paths["readiness_summary_markdown"]),
        ]
    )
    if run_browser_smoke:
        command.append("--run-browser-smoke")
    return command


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the canonical AgriGuard guarded compose launch with env-shape validation and readiness artifacts."
    )
    parser.add_argument("--app-root", type=Path, default=_default_app_root(), help="AgriGuard app root.")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Operator env file to validate before strict preflight. Defaults to var/agriguard-launch-operator.env.template.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for launch, packet, validation, and readiness artifacts. Defaults to workspace var/.",
    )
    parser.add_argument(
        "--output-prefix",
        default=DEFAULT_OUTPUT_PREFIX,
        help=f"Artifact filename prefix. Defaults to {DEFAULT_OUTPUT_PREFIX}.",
    )
    parser.add_argument(
        "--compose-file",
        type=Path,
        action="append",
        default=[],
        help="Compose file path passed through to launch_compose.py. Can be repeated.",
    )
    parser.add_argument(
        "--service",
        action="append",
        default=[],
        help="Compose service passed through to launch_compose.py. Can be repeated.",
    )
    parser.add_argument(
        "--no-browser-smoke",
        action="store_true",
        help="Skip the post-compose aggregate browser smoke suite.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the delegated launch_compose.py command plan.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, command_runner: CommandRunner = subprocess.run) -> int:
    args = parse_args(argv)
    app_root = args.app_root.resolve()
    output_dir = args.output_dir.resolve() if args.output_dir else (_workspace_root(app_root) / "var")
    env_file = args.env_file.resolve() if args.env_file else _default_env_file(app_root)
    compose_files = [compose_file.resolve() for compose_file in args.compose_file]
    artifact_paths = _artifact_paths(output_dir, args.output_prefix)
    command = _build_launch_command(
        app_root=app_root,
        env_file=env_file,
        artifact_paths=artifact_paths,
        compose_files=compose_files,
        services=args.service,
        run_browser_smoke=not args.no_browser_smoke,
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "command": command,
                    "app_root": str(app_root),
                    "env_file": str(env_file),
                    "output_dir": str(output_dir),
                    "output_prefix": args.output_prefix,
                    "run_browser_smoke": not args.no_browser_smoke,
                    "artifacts": {key: str(value) for key, value in artifact_paths.items()},
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    completed = command_runner(command, cwd=app_root, text=True)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
