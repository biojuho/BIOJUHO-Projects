"""One-shot patcher: add `persist-credentials: false` to every actions/checkout step.

Idempotent — skips checkouts that already have the flag. Handles both bare
`- uses: actions/checkout@...` and `with:`-bearing variants.

Usage:
    python ops/scripts/apply_persist_credentials_false.py [--dry-run] [--self-test]

After running, verify with `uvx zizmor .github/workflows` — artipacked count
should drop to 0.
"""

from __future__ import annotations

import argparse
import io
import pathlib
import re
import sys

WORKFLOW_DIR = pathlib.Path(".github/workflows")
CHECKOUT_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<lead>- )?uses:[ \t]+actions/checkout@",
)


def patch_text(text: str) -> tuple[str, int]:
    """Return (new_text, num_steps_patched)."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    patched = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        m = CHECKOUT_RE.match(line)
        if not m:
            out.append(line)
            i += 1
            continue

        # Column where the `uses:` keyword starts.
        uses_col = len(m.group("indent")) + (2 if m.group("lead") else 0)
        sibling_indent = " " * uses_col
        nested_indent = " " * (uses_col + 2)
        uses_line_idx = len(out)
        out.append(line)
        i += 1

        # Scan subsequent lines belonging to this step.
        has_with = False
        has_pc_false = False
        with_block_open_idx: int | None = None
        while i < len(lines):
            nxt = lines[i]
            stripped = nxt.lstrip(" \t")
            if not stripped or stripped.startswith("#"):
                out.append(nxt)
                i += 1
                continue
            indent_len = len(nxt) - len(nxt.lstrip(" \t"))
            if indent_len < uses_col:
                # De-indented past the step.
                break
            if indent_len == uses_col:
                if stripped.startswith("with:"):
                    has_with = True
                    with_block_open_idx = len(out)
                    out.append(nxt)
                    i += 1
                    # Now scan keys inside with: (indent > uses_col).
                    while i < len(lines):
                        inner = lines[i]
                        inner_strip = inner.lstrip(" \t")
                        if not inner_strip or inner_strip.startswith("#"):
                            out.append(inner)
                            i += 1
                            continue
                        inner_indent = len(inner) - len(inner_strip)
                        if inner_indent <= uses_col:
                            break
                        if inner_strip.startswith("persist-credentials"):
                            has_pc_false = True
                        out.append(inner)
                        i += 1
                    break
                # Sibling key at uses_col (e.g., `name:` of next step).
                break
            # indent_len > uses_col — unexpected continuation; just pass through.
            out.append(nxt)
            i += 1

        if has_with and not has_pc_false and with_block_open_idx is not None:
            out.insert(
                with_block_open_idx + 1,
                f"{nested_indent}persist-credentials: false\n",
            )
            patched += 1
        elif not has_with:
            out.insert(
                uses_line_idx + 1,
                f"{sibling_indent}with:\n{nested_indent}persist-credentials: false\n",
            )
            patched += 1

    return "".join(out), patched


def patch_file(path: pathlib.Path, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    new_text, n = patch_text(text)
    if n and not dry_run and new_text != text:
        path.write_text(new_text, encoding="utf-8", newline="")
    return n


def _self_test() -> int:
    cases = [
        # bare list-item form
        (
            "jobs:\n  j:\n    steps:\n      - uses: actions/checkout@abc # v4\n      - run: echo hi\n",
            "jobs:\n  j:\n    steps:\n      - uses: actions/checkout@abc # v4\n        with:\n          persist-credentials: false\n      - run: echo hi\n",
        ),
        # continuation form (name: + uses:)
        (
            "      - name: Checkout\n        uses: actions/checkout@abc # v4\n      - run: echo hi\n",
            "      - name: Checkout\n        uses: actions/checkout@abc # v4\n        with:\n          persist-credentials: false\n      - run: echo hi\n",
        ),
        # existing with: block, missing flag
        (
            "      - uses: actions/checkout@abc # v4\n        with:\n          fetch-depth: 0\n      - run: echo hi\n",
            "      - uses: actions/checkout@abc # v4\n        with:\n          persist-credentials: false\n          fetch-depth: 0\n      - run: echo hi\n",
        ),
        # already has persist-credentials → no change
        (
            "      - uses: actions/checkout@abc # v4\n        with:\n          persist-credentials: false\n      - run: echo hi\n",
            "      - uses: actions/checkout@abc # v4\n        with:\n          persist-credentials: false\n      - run: echo hi\n",
        ),
    ]
    fail = 0
    for idx, (src, want) in enumerate(cases):
        got, _ = patch_text(src)
        if got != want:
            fail += 1
            buf = io.StringIO()
            buf.write(f"--- case {idx} FAIL ---\nWANT:\n{want!r}\nGOT:\n{got!r}\n")
            print(buf.getvalue(), file=sys.stderr)
    if fail:
        print(f"self-test: {fail}/{len(cases)} failed", file=sys.stderr)
        return 1
    print(f"self-test: {len(cases)}/{len(cases)} passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    total = 0
    for path in sorted(WORKFLOW_DIR.glob("*.yml")):
        n = patch_file(path, args.dry_run)
        if n:
            print(f"{'(dry) ' if args.dry_run else ''}{path}: +{n}")
            total += n
    for path in sorted(WORKFLOW_DIR.glob("*.yaml")):
        n = patch_file(path, args.dry_run)
        if n:
            print(f"{'(dry) ' if args.dry_run else ''}{path}: +{n}")
            total += n
    print(f"Total checkouts patched: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
