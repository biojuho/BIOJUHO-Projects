"""Fix bare patch targets 'core.pipeline.*' -> 'getdaytrends.core.pipeline.*' in test files."""
import os
import re

TEST_DIR = r"d:\AI project\automation\getdaytrends\tests"

# Patterns to fix (patch targets in strings)
REPLACEMENTS = [
    # core.pipeline.xxx -> getdaytrends.core.pipeline.xxx
    (r'"core\.pipeline\.', '"getdaytrends.core.pipeline.'),
    (r"'core\.pipeline\.", "'getdaytrends.core.pipeline."),
    # core.pipeline_steps.xxx -> getdaytrends.core.pipeline_steps.xxx
    (r'"core\.pipeline_steps\.', '"getdaytrends.core.pipeline_steps.'),
    (r"'core\.pipeline_steps\.", "'getdaytrends.core.pipeline_steps."),
]

for fname in sorted(os.listdir(TEST_DIR)):
    if not fname.endswith(".py"):
        continue
    fpath = os.path.join(TEST_DIR, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    new_content = content
    for pattern, replacement in REPLACEMENTS:
        new_content = re.sub(pattern, replacement, new_content)
    
    if new_content != content:
        with open(fpath, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)
        # Count changes
        changes = sum(1 for p, _ in REPLACEMENTS for _ in re.finditer(p, content))
        print(f"Updated patch targets: {fname} ({changes} changes)")

print("Done!")
