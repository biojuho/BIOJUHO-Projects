"""Install Git hooks from ops/hooks/ into Git's common hooks directory."""

import subprocess
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_SRC = REPO_ROOT / "ops" / "hooks"


def main() -> None:
    hooks_dst = resolve_hooks_dir()
    if hooks_dst is None:
        print("[skip] could not resolve Git hooks directory")
        return
    install_hooks(hooks_dst)


def resolve_hooks_dir() -> Path | None:
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
    for hook_file in HOOKS_SRC.iterdir():
        if not hook_file.is_file() or hook_file.name.startswith(".") or hook_file.name.endswith(".py"):
            continue
        dst = hooks_dst / hook_file.name
        shutil.copy2(hook_file, dst)
        print(f"[ok] Installed {hook_file.name} -> {dst}")
        installed += 1

    if installed:
        print(f"\n{installed} hook(s) installed.")
    else:
        print("No hooks found in ops/hooks/")


if __name__ == "__main__":
    main()
