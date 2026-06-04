"""Install Git hooks from ops/hooks/ into Git's common hooks directory."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_SRC = REPO_ROOT / "ops" / "hooks"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install or verify repo Git hooks.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if installed hooks differ from the tracked ops/hooks files without writing",
    )
    args = parser.parse_args(argv)

    hooks_dst = resolve_hooks_dir()
    if hooks_dst is None:
        print("[skip] could not resolve Git hooks directory")
        return 1
    if args.check:
        return 0 if check_hooks(hooks_dst) else 1
    install_hooks(hooks_dst)
    return 0


def resolve_hooks_dir() -> Path | None:
    configured = _git_stdout(["config", "--path", "--get", "core.hooksPath"])
    if configured:
        hooks_path = Path(configured)
        if not hooks_path.is_absolute():
            hooks_path = (REPO_ROOT / hooks_path).resolve()
        return hooks_path

    return resolve_common_hooks_dir()


def resolve_common_hooks_dir() -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode == 0 and result.stdout.strip():
        git_common_dir = Path(result.stdout.strip())
        if not git_common_dir.is_absolute():
            git_common_dir = (REPO_ROOT / git_common_dir).resolve()
        return git_common_dir / "hooks"

    fallback = REPO_ROOT / ".git" / "hooks"
    return fallback if fallback.exists() else None


def install_hooks(hooks_dst: Path) -> None:
    hooks_dst.mkdir(parents=True, exist_ok=True)
    if not hooks_dst.exists():
        print(f"[skip] hooks directory not found at {hooks_dst}")
        return

    installed = 0
    for hook_file in _iter_hook_files():
        dst = hooks_dst / hook_file.name
        if hook_file.resolve() == dst.resolve():
            print(f"[ok] Hook source already active: {dst}")
            installed += 1
            continue
        _install_hook_file(hook_file, dst)
        print(f"[ok] Installed {hook_file.name} -> {dst}")
        installed += 1

    if installed:
        print(f"\n{installed} hook(s) installed.")
    else:
        print("No hooks found in ops/hooks/")


def check_hooks(hooks_dst: Path) -> bool:
    ok = True
    checked = 0
    for hook_file in _iter_hook_files():
        dst = hooks_dst / hook_file.name
        checked += 1
        if not dst.exists():
            print(f"[fail] Missing installed hook: {dst}")
            ok = False
            continue
        if not _installed_hook_matches(hook_file, dst):
            print(f"[fail] Installed hook is stale: {dst}")
            ok = False
            continue
        print(f"[ok] Hook is current: {dst}")

    if checked:
        print(f"\n{checked} hook(s) checked.")
    else:
        print("No hooks found in ops/hooks/")
    return ok and checked > 0


def _iter_hook_files() -> list[Path]:
    return [
        hook_file
        for hook_file in HOOKS_SRC.iterdir()
        if hook_file.is_file() and not hook_file.name.startswith(".") and not hook_file.name.endswith(".py")
    ]


def _install_hook_file(source: Path, destination: Path) -> None:
    destination.write_text(_normalized_hook_content(source), encoding="utf-8", newline="\n")
    shutil.copystat(source, destination)


def _installed_hook_matches(source: Path, destination: Path) -> bool:
    return _normalized_hook_content(destination) == _normalized_hook_content(source)


def _normalized_hook_content(source: Path) -> str:
    return source.read_text(encoding="utf-8").replace("\r\n", "\n")


def _git_stdout(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip() if result.returncode == 0 else ""


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
