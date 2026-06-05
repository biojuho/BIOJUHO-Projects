# AutoResearch Worktree Hook Shim

Date: 2026-06-05

## Problem

The linked worktrees share the common hook path at `D:\AI project\.git\hooks\pre-push`. The previous installer copied the full tracked `ops/hooks/pre-push` script into that shared path. During a push, another worktree can refresh the common hook while the long pytest gate is still running, leaving Git's shell to read a changed or truncated tail of the hook file.

Observed failure:

```text
D:/AI project/.git/hooks/pre-push: line 135: unexpected EOF while looking for matching `''
```

The installed hook passed a syntax check before execution, which points to a runtime overwrite race rather than a static syntax defect.

## Change

- `ops/hooks/install_hooks.py` now installs a short, stable shim into the common hook directory.
- The shim delegates to `ops/hooks/pre-push` in the active worktree with `exec sh "$hook_path" "$@"`.
- Hook checks compare the installed common hook against the stable shim, not against the long worktree-specific source script.
- The installer treats a worktree-local active hook source as current when `core.hooksPath` points directly at `ops/hooks`.
- `.gitattributes` now keeps the hook source, hook installer, and hook tests LF-normalized.

## Verification

```text
python -m pytest tests/test_pre_push_hook.py -q --tb=line
8 passed in 1.10s
```

```text
python ops\hooks\install_hooks.py
python ops\hooks\install_hooks.py --check
[ok] Hook is current: D:\AI project\.git\hooks\pre-push
```

```text
C:\Program Files\Git\usr\bin\sh.exe -n D:/AI project/.git/hooks/pre-push
installed_sh_n_exit=0

C:\Program Files\Git\usr\bin\sh.exe -n ops/hooks/pre-push
source_sh_n_exit=0
```
