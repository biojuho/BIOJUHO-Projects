import os
import glob
import re

workflow_dir = '.github/workflows'
files = glob.glob(os.path.join(workflow_dir, '*.yml'))

# Step 1: we replace the pip cache config from setup-python
def patch_setup_python_cache(content):
    # Match cache: pip and its dependency path
    content = re.sub(r'^\s*cache:\s*pip\s*\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*cache-dependency-path:.*?\n', '', content, flags=re.MULTILINE)
    return content

# Step 2: Inject setup-uv block before the first setup-python
def inject_setup_uv(content):
    if 'astral-sh/setup-uv' not in content and 'actions/setup-python' in content:
        # Prepend to the first setup-python
        content = re.sub(
            r'(\s+-\s+uses:\s*actions/setup-python@v\d+)',
            r'\n      - name: Install uv\n        uses: astral-sh/setup-uv@v5\n        with:\n          enable-cache: true\n\1',
            content, count=1
        )
    return content

# Step 3: Replace pip install -r requirements.txt with uv sync
def patch_pip_installs(content):
    # Remove lines running `--upgrade pip`
    content = re.sub(r'^\s*python -m pip install --upgrade pip\s*\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*pip install --upgrade pip\s*\n', '', content, flags=re.MULTILINE)
    
    # Replace the requirements installation. We will do this carefully.
    # Normally they look like: `pip install -r something/requirements.txt`
    content = re.sub(r'pip install -r [\w/]+/requirements\.txt', 'uv sync --all-packages', content)
    content = re.sub(r'pip install -r requirements\.txt', 'uv sync --all-packages', content)
    
    # Deduplicate `uv sync --all-packages` if it appears multiple times in a single run block
    # A simple way to do this at string level is just let it run multiple times (it's fast), 
    # but it's cleaner to deduplicate.
    
    # Remove pip install pytest, httpx etc. if they are part of uv sync
    content = re.sub(r'^\s*pip install pytest.*?\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*pip install httpx.*?\n', '', content, flags=re.MULTILINE)
    
    # `pip install ruff` -> just leave it or remove, since uv includes ruff if it's in pyproject.toml
    content = re.sub(r'^\s*pip install ruff.*?\n', '', content, flags=re.MULTILINE)
    
    return content

# Step 4: Add `uv run` in front of python and pytest calls
def patch_executable_runs(content):
    # Match: run: python main.py -> run: uv run python main.py
    # But only if it has not been patched
    content = re.sub(r'(run:\s*)python (.*\.py)', r'\1uv run python \2', content)
    content = re.sub(r'(run:\s*)pytest ', r'\1uv run pytest ', content)
    return content

results = []
for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    new_content = patch_setup_python_cache(new_content)
    new_content = inject_setup_uv(new_content)
    new_content = patch_pip_installs(new_content)
    new_content = patch_executable_runs(new_content)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        results.append(os.path.basename(filepath))

print(f"Updated {len(results)} workflows: {', '.join(results)}")
