"""Fix patch targets to use dynamic module resolution."""
import os
import re

TEST_DIR = r"d:\AI project\automation\getdaytrends\tests"

# Pattern: patch("getdaytrends.core.pipeline.xxx" or patch("getdaytrends.core.pipeline_steps.xxx"
# Need to change to patch target that matches at runtime
# Since conftest puts pkg_root on sys.path, 'core.pipeline' module is available as 'core.pipeline'
# But when getdaytrends is editable installed, it's also 'getdaytrends.core.pipeline'
# Solution: use the module's __name__ attribute to build patch path

PATCH_PATTERN = re.compile(
    r'patch\("getdaytrends\.core\.(pipeline(?:_steps)?)\.([\w]+)"'
)

def replace_patch(match):
    module = match.group(1)
    func = match.group(2)
    return f'patch(f"{{_step_collect.__module__.rsplit(\'.\', 1)[0]}}.{module}.{func}"' if func == "collect_trends" else f'patch("getdaytrends.core.{module}.{func}"'

# Actually this is getting too complex. Just revert to bare core.pipeline for patch targets too.
# The conftest.py already puts pkg_root on sys.path[0], so core.pipeline should resolve.

for fname in sorted(os.listdir(TEST_DIR)):
    if not fname.endswith(".py"):
        continue
    fpath = os.path.join(TEST_DIR, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    new_content = content.replace(
        '"getdaytrends.core.pipeline_steps.', '"core.pipeline_steps.'
    ).replace(
        '"getdaytrends.core.pipeline.', '"core.pipeline.'
    ).replace(
        '"getdaytrends.tap.', '"tap.'
    )
    
    if new_content != content:
        with open(fpath, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)
        count = content.count('"getdaytrends.core.') + content.count('"getdaytrends.tap.')
        print(f"Reverted patch targets: {fname} ({count} changes)")

print("Done!")
