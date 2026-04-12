"""Fix imports to use try/except pattern for both editable and regular installs."""
import os
import re

TEST_DIR = r"d:\AI project\automation\getdaytrends\tests"

# Pattern: from getdaytrends.core.pipeline import X
# Replace with:
# try:
#     from getdaytrends.core.pipeline import X
# except (ImportError, ModuleNotFoundError):
#     from core.pipeline import X

PATTERN = re.compile(
    r'^(\s*)from getdaytrends\.core\.(pipeline(?:_steps)?)\s+import\s+(.+)$',
    re.MULTILINE
)

def replace_import(match):
    indent = match.group(1)
    module = match.group(2)
    names = match.group(3)
    return (
        f"{indent}try:\n"
        f"{indent}    from getdaytrends.core.{module} import {names}\n"
        f"{indent}except (ImportError, ModuleNotFoundError):\n"
        f"{indent}    from core.{module} import {names}"
    )

for fname in sorted(os.listdir(TEST_DIR)):
    if not fname.endswith(".py"):
        continue
    fpath = os.path.join(TEST_DIR, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    new_content = PATTERN.sub(replace_import, content)
    
    if new_content != content:
        with open(fpath, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)
        count = len(PATTERN.findall(content))
        print(f"Updated: {fname} ({count} imports wrapped with try/except)")

print("Done!")
