"""One-shot pyright triage — lists unused imports in packages/shared source."""
import re
from pathlib import Path

lines = Path("var/pyright-full.txt").read_text(encoding="utf-8").splitlines()
cur_file = None
results: dict[str, list[str]] = {}
file_re = re.compile(r"^(d:\\AI project\\packages\\shared\\[^\n]+\.py)$")

SKIP_SUBSTRINGS = ("\\tests\\", "\\test_utils\\")

for line in lines:
    m = file_re.match(line.rstrip())
    if m:
        cur_file = m.group(1)
        continue
    if cur_file and "reportUnusedImport" in line:
        if any(s in cur_file for s in SKIP_SUBSTRINGS):
            continue
        results.setdefault(cur_file, []).append(line.strip())

for path, warns in sorted(results.items(), key=lambda kv: -len(kv[1])):
    print(f"{len(warns):3}  {path}")
    for w in warns[:3]:
        print("    ", w[:140])
print()
print(f"Total files: {len(results)}")
print(f"Total warnings: {sum(len(v) for v in results.values())}")
