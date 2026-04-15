import yaml
import glob
from pathlib import Path
import re

def refactor_setup():
    workflows_dir = Path(".github/workflows")
    for yml_file in workflows_dir.glob("*.yml"):
        content = yml_file.read_text(encoding="utf-8")
        
        # Remove astral block with name
        pattern_uv = re.compile(r"^[ \t]*-[ \t]*name:[^\n]*uv[^\n]*\n[ \t]*uses:[ \t]*astral-sh/setup-uv@v[0-9]+.*?(?=\n\n|\n[ \t]*-[ \t]+|\Z)", re.MULTILINE | re.DOTALL)
        content = pattern_uv.sub("", content)

        # Remove astral block without name
        pattern_uv2 = re.compile(r"^[ \t]*-[ \t]*uses:[ \t]*astral-sh/setup-uv@v[0-9]+.*?(?=\n\n|\n[ \t]*-[ \t]+|\Z)", re.MULTILINE | re.DOTALL)
        content = pattern_uv2.sub("", content)
        
        # Replace python block with with: python-version: (also may have architecture: or check-latest:)
        # Simplification: just capture the whole block until the next bullet.
        # The replacement will set python-version or just use default.
        
        def replace_python(match):
            indent = match.group(1)
            block = match.group(0)
            
            # extract version
            v_match = re.search(r"python-version:[ \t]*[\"']?([^\"'\n]+)[\"']?", block)
            version = v_match.group(1) if v_match else "3.13"
            
            return f"{indent}- uses: ./.github/actions/setup-python-uv\n{indent}  with:\n{indent}    python-version: '{version}'"
            
        pattern_python = re.compile(r"(^[ \t]*)-[ \t]*uses:[ \t]*actions/setup-python@v[0-9]+.*?(?=\n\n|\n[ \t]*-[ \t]+|\Z)", re.MULTILINE | re.DOTALL)
        content = pattern_python.sub(replace_python, content)

        # Cleanup whitespace
        content = re.sub(r"\n{3,}", "\n\n", content)
        
        yml_file.write_text(content, encoding="utf-8")
        print(f"Refactored {yml_file.name}")

if __name__ == "__main__":
    refactor_setup()
