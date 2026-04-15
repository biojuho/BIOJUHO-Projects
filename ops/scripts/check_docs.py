import ast
from pathlib import Path

def check_docs():
    ops = Path("ops/scripts")
    missing = []
    
    # Check all remaining valid python files in ops/scripts after cleanup
    for p in ops.glob("*.py"):
        if p.name.startswith("_") or p.name in ('cleanup_scripts.py', 'check_docs.py'):
            continue
            
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
            if not ast.get_docstring(tree):
                missing.append(p.name)
        except Exception as e:
            print(f"Error parsing {p.name}: {e}")
            
    print("MISSING_DOCSTRINGS:", missing)

if __name__ == "__main__":
    check_docs()
