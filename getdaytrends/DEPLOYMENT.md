# 🚀 getdaytrends Production Deployment Guide

**Last Updated**: 2026-03-23
**Version**: v4.0 (Refactored) + Auto PYTHONPATH

---

## ✅ Pre-Deployment Checklist

### Code Validation
- [x] **Import paths verified**: All `core.pipeline` imports work correctly
- [x] **Tests passed**: 33 tests passed (config: 21, models: 12)
- [x] **Main.py executable**: Confirmed with `--help` flag
- [x] **One-shot dry-run verified**: Completed successfully on Python 3.14.2
- [x] **Entrypoint reduced**: main.py is now 305 lines (down from 1,435 pre-refactor)
- [x] **Auto PYTHONPATH**: main.py now sets paths automatically ✨
- [x] **Python 3.14 shutdown fix**: Clean exit after dry-run / one-shot execution

### Environment Requirements
- **Python**: 3.13.3+ (tested on 3.14.2)
- **Working Directory**: ✅ **Can run from anywhere!** (auto PYTHONPATH)
- **PYTHONPATH**: ✅ **No longer required!** (automatic setup in main.py)

---

## 🔧 Deployment Methods

### Method 1: Direct Execution (Simplest) ⭐ NEW

**You can now run from anywhere!** main.py automatically sets up paths.

```bash
# From getdaytrends directory (works now!)
cd getdaytrends
python main.py --one-shot

# From project root (also works)
cd "D:\AI 프로젝트"
python getdaytrends/main.py --one-shot

# From any directory with full path (also works)
python "D:\AI 프로젝트\getdaytrends\main.py" --one-shot
```

### Method 2: Systemd Service (Linux Production)

Create `/etc/systemd/system/getdaytrends.service`:

```ini
[Unit]
Description=X Trend Auto Tweet Generator
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/AI 프로젝트/getdaytrends
# No PYTHONPATH needed - main.py sets it automatically!
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable getdaytrends
sudo systemctl start getdaytrends
sudo systemctl status getdaytrends
```

### Method 3: Docker (Isolated Environment)

**Dockerfile** (already present at `getdaytrends/Dockerfile`):

```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r getdaytrends/requirements.txt

# No PYTHONPATH needed - main.py sets it automatically!

# Run from getdaytrends directory
WORKDIR /app/getdaytrends
CMD ["python", "main.py"]
```

Build and run from the workspace root:
```bash
docker build -f getdaytrends/Dockerfile -t getdaytrends:latest .
docker run -d --name getdaytrends \
  --env-file .env \
  getdaytrends:latest
```

---

## 🧪 Validation Tests

### 1. Main.py Execution Test (Simplest)
```bash
cd getdaytrends
python main.py --help
```

**Expected Output**: Usage information displayed

### 2. Unit Tests
```bash
cd "D:\AI 프로젝트"
python -m pytest getdaytrends/tests/test_config.py -v
python -m pytest getdaytrends/tests/test_models.py -v
```

**Expected**: All tests pass (33 total)

### 3. Dry Run Test
```bash
cd getdaytrends
python main.py --dry-run --limit 3
```

**Expected**: Collects 3 trends, analyzes them, but doesn't save

### 4. Windows Scheduler Smoke Test
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\getdaytrends\run_scheduled_getdaytrends.ps1 -DryRun -Limit 1 -Country korea
```

**Expected**: Completes with exit code `0` and writes UTF-8 logs under `getdaytrends\logs\scheduler\`

### 5. Local Deployment Validator
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\getdaytrends\validate_local_deployment.ps1 -Country korea -Limit 1
```

**Expected**: Verifies `.env`, core tests, QA regression, scheduler dry-run, and scheduled task health

---

## 📂 File Structure (Post-Refactoring)

```
getdaytrends/
├── main.py                  # 305 lines - CLI + scheduler + auto PYTHONPATH
├── core/
│   ├── __init__.py          # Public API exports
│   └── pipeline.py          # 873 lines - Pipeline orchestration
├── scraper.py               # Multi-source trend collection
├── analyzer.py              # Viral scoring + clustering
├── generator.py             # Tweet/content generation
├── db.py                    # SQLite/PostgreSQL transactions
├── storage.py               # Notion/Sheets storage
├── config.py                # App configuration
├── models.py                # Pydantic data models
├── alerts.py                # Telegram/Discord notifications
├── tests/                   # 22 test files
│   ├── test_config.py       # 21 tests ✅
│   ├── test_models.py       # 12 tests ✅
│   └── ...
└── REFACTORING.md           # Refactoring details
```

---

## 🔑 Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Required
GEMINI_API_KEY=your_gemini_key
GOOGLE_API_KEY=your_google_key

# Optional
OPENAI_API_KEY=your_openai_key
NOTION_API_TOKEN=your_notion_token
TELEGRAM_BOT_TOKEN=your_telegram_token
DATABASE_URL=postgresql://user:pass@host/db  # For production
```

---

## 🚨 Common Issues & Solutions

### ✅ Issue 1: `ModuleNotFoundError: No module named 'shared'` - FIXED!

**Status**: ✅ **Resolved** (as of 2026-03-23)

main.py now automatically sets PYTHONPATH, so you can run from anywhere!

```bash
# All of these work now:
cd getdaytrends && python main.py  # ✅ Works!
cd "D:\AI 프로젝트" && python getdaytrends/main.py  # ✅ Works!
python "D:\AI 프로젝트\getdaytrends\main.py"  # ✅ Works!
```

**Note**: This only applies to running `main.py` directly. For pytest or direct imports, still run from project root.

### ✅ Issue 2: Python 3.14 one-shot exit failed during shutdown - FIXED!

**Status**: ✅ **Resolved** (as of 2026-03-23)

Some environments patch the event loop in a way that caused shutdown to fail after the pipeline had already completed. The entrypoint now uses a safer async runner, and this command exits cleanly:

```bash
python getdaytrends/main.py --one-shot --dry-run --limit 1 --country korea
```

### Issue 3: Tests fail with import errors

**Cause**: pytest not running from project root

**Solution**:
```bash
cd "D:\AI 프로젝트"
python -m pytest getdaytrends/tests/  # ✅
```

### Issue 4: Windows Task Scheduler action is split at `D:\AI`

**Cause**: A legacy task action was registered with an unquoted path containing spaces, so Task Scheduler stored `Execute=d:\AI` and split the rest into arguments.

**Solution**:
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\getdaytrends\setup_scheduled_task.ps1 -NonInteractive
```

**Notes**:
- Non-admin shells fall back to `GetDayTrends_CurrentUser`
- Admin-owned legacy `GetDayTrends` may need elevated cleanup before the original task name can be reused
- The scheduler runner now lives in `getdaytrends\run_scheduled_getdaytrends.ps1`

---

## 📊 Performance Metrics

### Refactoring Impact
- **Code reduction**: main.py 1,435 → 305 lines
- **Current main.py size**: 305 lines
- **Modularity**: Improved - pipeline logic now in dedicated module
- **Test coverage**: 33 tests passing
- **Import time**: No significant change (~0.5s)

### Production Benchmarks
- **Trend collection**: ~30-60s (depends on sources)
- **Analysis**: ~10-20s (LLM-dependent)
- **Generation**: ~20-40s per batch
- **Storage**: ~5-10s (Notion/Sheets)
- **Total cycle**: ~2-5 minutes (typical)

---

## 🔄 Rollback Plan

If issues occur in production:

1. **Preserve data**:
   ```bash
   cp getdaytrends.db getdaytrends.db.backup
   ```

2. **Revert to previous version**:
   ```bash
   git log --oneline  # Find commit hash before refactoring
   git checkout <previous-commit-hash> getdaytrends/
   ```

3. **Restart service**:
   ```bash
   systemctl restart getdaytrends
   ```

---

## ✅ Deployment Validation Checklist

Before marking deployment complete:

- [x] Environment variables configured (`.env`)
- [x] Direct execution from any directory works
- [x] Import test passes
- [x] Unit tests pass (targeted validation suite)
- [x] Dry run completes successfully
- [x] Logs show no fatal runtime errors
- [x] First production run completes
- [x] Data saved to storage (Notion/Content Hub/DB)
- [ ] Alerts working (if enabled)

Validated on this machine with:
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\getdaytrends\validate_local_deployment.ps1 -Country korea -Limit 1`

Known non-blocking warnings:
- Instructor may log a `mistralai` import fallback warning during structured extraction.
- Low-confidence or low-diversity trends may still log QA warnings without failing the run.

---

## 📞 Support

**Issues**: See [getdaytrends/REFACTORING.md](REFACTORING.md) for details
**Documentation**: [CLAUDE.md](../CLAUDE.md) - Architecture section
**Tests**: Run `pytest getdaytrends/tests/ -v`

---

**Status**: ✅ Ready for Production (Validated 2026-03-23)
