"""Install Git hooks from ops/hooks/ into .git/hooks/."""

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_SRC = REPO_ROOT / "ops" / "hooks"
HOOKS_DST = REPO_ROOT / ".git" / "hooks"


def main() -> None:
    if not HOOKS_DST.exists():
        print(f"[skip] .git/hooks not found at {HOOKS_DST}")
        return

    installed = 0
    for hook_file in HOOKS_SRC.iterdir():
        if hook_file.name.startswith(".") or hook_file.name.endswith(".py"):
            continue
        dst = HOOKS_DST / hook_file.name
        shutil.copy2(hook_file, dst)
        print(f"[ok] Installed {hook_file.name} -> {dst}")
        installed += 1

    if installed:
        print(f"\n{installed} hook(s) installed.")
    else:
        print("No hooks found in ops/hooks/")


if __name__ == "__main__":
    main()
