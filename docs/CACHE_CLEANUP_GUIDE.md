# Python Cache Cleanup Guide

**Last Updated**: 2026-03-24

## Overview

Python creates cache files to speed up imports and execution. Over time, these can accumulate and cause issues.

## What Gets Cached?

- `__pycache__/` - Compiled bytecode directories
- `*.pyc` - Compiled Python files
- `*.pyo` - Optimized Python files
- `.pytest_cache/` - Pytest cache
- `.mypy_cache/` - MyPy type checking cache

## When to Clean Cache

Clean cache if you experience:
- Import errors after updating packages
- Stale code execution (old code running despite edits)
- Git diff showing binary files
- Disk space issues

## Cleanup Methods

### Method 1: Git Clean (Recommended)
```bash
# Remove all gitignored files including caches (CAREFUL!)
git clean -fdX

# Preview what would be deleted
git clean -ndX
```

**Pros**: Fast, respects .gitignore
**Cons**: Also removes .env files if gitignored (backup first!)

### Method 2: Find + Delete (Selective)
```bash
# Windows (PowerShell)
Get-ChildItem -Path . -Include __pycache__,.pytest_cache -Recurse -Force | Remove-Item -Recurse -Force

# Linux/macOS
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type d -name .pytest_cache -exec rm -rf {} +
find . -name "*.pyc" -delete
```

**Pros**: Surgical, only removes cache
**Cons**: Slower for large projects

### Method 3: Python Script (Safe)
```bash
# Use the provided script
python scripts/clean_python_cache.py --dry-run  # Preview
python scripts/clean_python_cache.py            # Execute
```

**Pros**: Safe, excludes node_modules/.venv
**Cons**: May be slow on large projects

### Method 4: Manual Cleanup (Project-Specific)
```bash
# getdaytrends
cd getdaytrends
rm -rf __pycache__ .pytest_cache
find . -name "*.pyc" -delete

# DailyNews
cd DailyNews
rm -rf __pycache__ .pytest_cache
find . -name "*.pyc" -delete

# Repeat for other projects...
```

## Automated Cleanup

### Pre-commit Hook
Add to `.pre-commit-config.yaml`:
```yaml
  - repo: local
    hooks:
      - id: clean-pycache
        name: Clean Python cache
        entry: bash -c 'find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true'
        language: system
        pass_filenames: false
```

### Git Post-Checkout Hook
```bash
# .git/hooks/post-checkout
#!/bin/bash
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
```

## .gitignore Configuration

Ensure `.gitignore` includes:
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.pytest_cache/
.mypy_cache/
.coverage
htmlcov/
```

Already configured in this project's root `.gitignore`.

## Disk Space Savings

Typical cache size in this workspace:
- Small project (< 100 files): ~1-5 MB
- Medium project (100-500 files): ~5-20 MB
- Large project (> 500 files): ~20-100 MB

Total potential savings: **50-200 MB**

## Troubleshooting

### "Permission Denied" Error
**Windows**:
```powershell
# Run PowerShell as Administrator
Remove-Item -Path __pycache__ -Recurse -Force
```

**Linux/macOS**:
```bash
sudo find . -type d -name __pycache__ -exec rm -rf {} +
```

### Cache Recreates Immediately
**Normal behavior**. Python recreates `__pycache__` on next import. This is expected and improves performance.

### Git Still Showing Cache Files
```bash
# Remove from Git tracking
git rm -r --cached **/__pycache__

# Commit the removal
git commit -m "chore: Remove Python cache from Git"
```

## Best Practices

### ✅ Do
- Clean cache before major refactoring
- Clean cache after updating Python version
- Add cache directories to `.gitignore`
- Use virtual environments (isolates cache)

### ❌ Don't
- Manually edit `.pyc` files
- Commit cache files to Git
- Delete cache in production without testing
- Clean cache while Python processes are running

## Performance Impact

Cleaning cache:
- First run after cleanup: **Slower** (needs to recompile)
- Subsequent runs: **Same speed** (cache rebuilt)
- Disk I/O: **Reduced** (fewer files)

## Related Commands

```bash
# Check cache size
du -sh **/__pycache__ .pytest_cache .mypy_cache

# List all cache directories
find . -type d -name __pycache__ -o -name .pytest_cache

# Clean specific project
cd getdaytrends && rm -rf $(find . -type d -name __pycache__)
```

## CI/CD Integration

### GitHub Actions
```yaml
- name: Clean Python cache
  run: |
    find . -type d -name __pycache__ -exec rm -rf {} + || true
```

### Pre-deployment
```bash
# In deployment script
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type d -name .pytest_cache -exec rm -rf {} +
```

## FAQ

**Q: Will cleaning cache break my code?**
A: No. Python recreates cache automatically on next import.

**Q: Should I clean cache before committing?**
A: No need - cache is gitignored. Clean if experiencing import issues.

**Q: Can I disable Python cache?**
A: Yes, but not recommended:
```bash
export PYTHONDONTWRITEBYTECODE=1  # Disables .pyc generation
```

**Q: Why is my cache so large?**
A: Large projects with many dependencies accumulate cache. Normal behavior.

---

**Maintenance**: Run cache cleanup monthly or when experiencing issues.
**Automation**: Consider adding to monthly maintenance tasks in TASKS.md.
