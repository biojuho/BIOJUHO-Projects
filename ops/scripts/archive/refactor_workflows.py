import yaml
import glob
from pathlib import Path
import re

def refactor_workflows():
    workflows_dir = Path(".github/workflows")
    for yml_file in workflows_dir.glob("*.yml"):
        content = yml_file.read_text(encoding="utf-8")
        
        # S1-1: Replace setup blocks with the new composite action
        # This replaces astral-sh/setup-uv + actions/setup-python
        
        # We need a regex that matches both setups, they can appear in any order.
        # But generally they are sequential. Let's just create a more generic replacement.
        # It's tricky to do multi-line yaml replacement perfectly with regex.
        # We will look for setup-python@v5 and setup-uv@v5 strings.
        
        lines = content.split('\n')
        new_lines = []
        skip_lines = 0
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Bare command lint (S1-2)
            # Find exact "run: python " or "run: pytest "
            # Exclude bootstrap_legacy_paths.py and python - <<'PY'
            if "run: python " in line and "bootstrap_legacy_paths.py" not in line and "python - <<" not in line:
                line = line.replace("run: python ", "run: uv run python ")
            elif "run: pytest " in line:
                line = line.replace("run: pytest ", "run: uv run pytest ")
            elif "run: python3 " in line and "bootstrap_legacy_paths" not in line:
                line = line.replace("run: python3 ", "run: uv run python3 ")
                
            new_lines.append(line)
            i += 1
            
        yml_file.write_text("\n".join(new_lines), encoding="utf-8")
        print(f"Refactored bare commands in {yml_file.name}")

if __name__ == "__main__":
    refactor_workflows()
