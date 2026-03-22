# DailyNews Insight Generator - Scheduling Setup Guide

## Overview

This guide covers setting up automated twice-daily insight generation using Windows Task Scheduler.

## Schedule

| Window | Time (KST) | Script | Categories |
|--------|------------|--------|------------|
| **Morning** | 7:00 AM | `run_morning_insights.bat` | Tech, Economy_KR, AI_Deep |
| **Evening** | 6:00 PM | `run_evening_insights.bat` | Tech, Economy_KR, AI_Deep |

## Prerequisites

- [x] Windows 10/11 with Task Scheduler
- [x] DailyNews project installed at `d:\AI 프로젝트\DailyNews`
- [x] Python virtual environment activated (`venv\Scripts\activate.bat`)
- [x] All dependencies installed (`pip install -r requirements.txt`)
- [x] `.env` configured with API keys (GEMINI_API_KEY, NOTION_API_KEY, etc.)

## Quick Setup (Recommended)

### Option 1: PowerShell Auto-Setup (One Command)

```powershell
# Run PowerShell as Administrator
cd "d:\AI 프로젝트"
PowerShell -ExecutionPolicy Bypass -File scripts\setup_scheduled_tasks.ps1
```

**What it does:**
- ✅ Creates 2 scheduled tasks (Morning + Evening)
- ✅ Configures triggers (7 AM, 6 PM daily)
- ✅ Sets execution parameters (battery, network, timeout)
- ✅ Verifies registration

**Expected output:**
```
========================================
DailyNews Insight Generator - Scheduler Setup
========================================
✓ Found morning script: d:\AI 프로젝트\scripts\run_morning_insights.bat
✓ Found evening script: d:\AI 프로젝트\scripts\run_evening_insights.bat

Creating morning task (7:00 AM)...
✓ Morning task created: DailyNews_Morning_Insights

Creating evening task (6:00 PM)...
✓ Evening task created: DailyNews_Evening_Insights

========================================
Setup Complete!
========================================
```

---

## Manual Setup (Alternative)

### Step 1: Open Task Scheduler

```cmd
taskschd.msc
```

### Step 2: Create Morning Task

1. **Action** → **Create Basic Task**
2. **Name**: `DailyNews_Morning_Insights`
3. **Description**: `DailyNews 오전 인사이트 자동 생성 (7:00 AM)`
4. **Trigger**: Daily at 7:00 AM
5. **Action**: Start a program
   - **Program/script**: `cmd.exe`
   - **Arguments**: `/c "d:\AI 프로젝트\scripts\run_morning_insights.bat"`
   - **Start in**: `d:\AI 프로젝트\DailyNews`
6. **Finish** → Open Properties
7. **Settings Tab**:
   - ✅ Allow task to be run on demand
   - ✅ Run task as soon as possible after a scheduled start is missed
   - ✅ If the task fails, restart every: 10 minutes (Attempt to restart up to 3 times)
   - ✅ Stop the task if it runs longer than: 2 hours
8. **Conditions Tab**:
   - ✅ Start only if the following network connection is available: Any connection
   - ❌ Start the task only if the computer is on AC power (uncheck for laptops)

### Step 3: Create Evening Task

Repeat Step 2 with:
- **Name**: `DailyNews_Evening_Insights`
- **Description**: `DailyNews 오후 인사이트 자동 생성 (6:00 PM)`
- **Trigger**: Daily at 6:00 PM
- **Arguments**: `/c "d:\AI 프로젝트\scripts\run_evening_insights.bat"`

---

## Verification

### 1. Check Task Scheduler

```cmd
taskschd.msc
```

Look for:
- `DailyNews_Morning_Insights` - Status: Ready, Next Run Time: [Tomorrow 7:00 AM]
- `DailyNews_Evening_Insights` - Status: Ready, Next Run Time: [Today/Tomorrow 6:00 PM]

### 2. Manual Test Run

**Option A: Via Task Scheduler GUI**
1. Right-click task → **Run**
2. Watch **Status** column change to "Running" → "Ready"
3. Check **Last Run Result**: `0x0` (success) or error code

**Option B: Via Command Line**
```cmd
schtasks /run /tn "DailyNews_Morning_Insights"
```

**Option C: Via Test Script**
```cmd
cd "d:\AI 프로젝트"
scripts\test_insight_generation.bat
```

### 3. Check Logs

```cmd
dir "d:\AI 프로젝트\DailyNews\logs\insights\*.log"
```

**Expected log structure:**
```
DailyNews\logs\insights\
├── morning_20260321_070001.log
├── morning_20260322_070002.log
├── evening_20260321_180003.log
└── evening_20260322_180001.log
```

**Sample log content:**
```
==========================================
DailyNews Morning Insights
Started: 2026-03-21 07:00:01
==========================================
Running morning window insight generation...
[Insight generation output...]
SUCCESS: Morning insights generated
==========================================
Finished: 2026-03-21 07:04:23
==========================================
```

### 4. Check Notion Dashboard

Navigate to your Notion workspace and verify:
- New page created in DailyNews database
- **Category**: Tech / Economy_KR / AI_Deep
- **Window**: Morning / Evening
- **Status**: Draft (awaiting manual review)
- **Generated At**: [timestamp]
- **Validation Passed**: ✅
- **Quality Scores**: P1, P2, P3 (all ≥ 0.6)

---

## Troubleshooting

### Issue 1: Task Not Running

**Symptoms:**
- Task shows "Ready" but never runs
- Last Run Time is blank

**Solutions:**
1. Check trigger settings: Task Scheduler → Task → Triggers → Edit
2. Verify task is enabled: Right-click task → Enable
3. Check event logs: Event Viewer → Windows Logs → Application (Source: Task Scheduler)

### Issue 2: Task Fails with Exit Code

**Common exit codes:**
| Code | Meaning | Solution |
|------|---------|----------|
| `0x1` | General error | Check log file for Python errors |
| `0x2` | File not found | Verify script paths in task action |
| `0xC000013A` | Process terminated | Increase timeout (Settings tab) |

**Debugging steps:**
1. Open log file: `d:\AI 프로젝트\DailyNews\logs\insights\[latest].log`
2. Look for error messages after "ERROR:"
3. Common issues:
   - Virtual environment activation failed → Check `venv\Scripts\activate.bat` exists
   - Import errors → Reinstall dependencies: `pip install -r requirements.txt`
   - API errors → Verify `.env` has valid API keys

### Issue 3: Python Import Errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'antigravity_mcp'
```

**Solution:**
```cmd
cd "d:\AI 프로젝트\DailyNews"
call venv\Scripts\activate.bat
pip install -e .
```

### Issue 4: Insight Validation Failures

**Symptoms:**
- Logs show "Validation FAILED"
- Notion page has ❌ in validation column

**Check:**
1. `d:\AI 프로젝트\DailyNews\logs\insights\[latest].log`
2. Look for validation scores:
   ```
   Principle 1 (점→선 연결): 0.45 / 0.60 FAIL
   Principle 2 (파급 효과): 0.80 / 0.60 PASS
   Principle 3 (실행 항목): 0.30 / 0.60 FAIL
   ```
3. If consistent failures, review `validator.py` thresholds or LLM prompts

### Issue 5: Network Connection Required

**Symptoms:**
- Task fails when on battery/disconnected

**Solution:**
Task Scheduler → Task Properties → Conditions tab:
- ✅ Start only if the following network connection is available: **Any connection**
- ❌ Uncheck "Start the task only if the computer is on AC power"

---

## Monitoring First Run

### Pre-Flight Checklist

Before the first scheduled run (tonight 6 PM or tomorrow 7 AM):

- [ ] Task Scheduler shows both tasks with Status: **Ready**
- [ ] Next Run Time is correct (7:00 AM / 6:00 PM)
- [ ] Manual test run succeeded (`scripts\test_insight_generation.bat`)
- [ ] Log directory exists: `d:\AI 프로젝트\DailyNews\logs\insights\`
- [ ] Notion API integration works (test with manual run)

### Watch for First Run

**30 minutes before scheduled time:**
1. Open Task Scheduler (`taskschd.msc`)
2. Select the task (morning or evening)
3. Watch **Status** column

**At scheduled time (within 1-2 minutes):**
- Status changes to **Running**
- Last Run Time updates to current time
- Log file appears in `logs\insights\`

**5 minutes after scheduled time:**
- Status returns to **Ready**
- Last Run Result: `0x0` (success)
- New Notion page created

**If task doesn't run:**
1. Check Event Viewer → Windows Logs → Application
2. Look for Task Scheduler events
3. Verify computer was on and connected to network

---

## Maintenance

### Log Rotation

Logs are automatically cleaned up after 30 days by the batch scripts:
```batch
forfiles /p "%LOG_DIR%" /s /m *.log /d -30 /c "cmd /c del @path"
```

**Manual cleanup:**
```cmd
cd "d:\AI 프로젝트\DailyNews\logs\insights"
del /q *.log
```

### Updating Scripts

After modifying `run_morning_insights.bat` or `run_evening_insights.bat`:
1. No need to re-register tasks (scripts are referenced by path)
2. Test manually: `scripts\test_insight_generation.bat`
3. Verify next scheduled run still works

### Disabling Scheduling Temporarily

**Pause for 1 day:**
```cmd
schtasks /change /tn "DailyNews_Morning_Insights" /disable
schtasks /change /tn "DailyNews_Evening_Insights" /disable
```

**Resume:**
```cmd
schtasks /change /tn "DailyNews_Morning_Insights" /enable
schtasks /change /tn "DailyNews_Evening_Insights" /enable
```

### Uninstalling

```cmd
schtasks /delete /tn "DailyNews_Morning_Insights" /f
schtasks /delete /tn "DailyNews_Evening_Insights" /f
```

---

## Advanced Configuration

### Changing Schedule

**Example: Run every 6 hours instead of twice daily:**
```powershell
$Trigger = New-ScheduledTaskTrigger -Once -At "00:00" -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration (New-TimeSpan -Days 9999)
Set-ScheduledTask -TaskName "DailyNews_Morning_Insights" -Trigger $Trigger
```

### Adding Categories

Edit `run_morning_insights.bat` / `run_evening_insights.bat`:
```batch
python -m antigravity_mcp jobs generate-brief ^
    --window morning ^
    --max-items 10 ^
    --categories Tech,Economy_KR,AI_Deep,Crypto,DeSci
```

### Email Notifications on Failure

Task Scheduler → Task Properties → Actions → New:
- **Action**: Send an e-mail (requires SMTP configuration)
- **Deprecated in Windows 10+** → Use PowerShell script with `Send-MailMessage` instead

**Alternative: Add to batch script:**
```batch
if %EXITCODE% neq 0 (
    powershell -Command "Send-MailMessage -To 'you@example.com' -From 'dailynews@example.com' -Subject 'DailyNews Insight Generation Failed' -Body 'Check logs at %LOGFILE%' -SmtpServer smtp.gmail.com"
)
```

---

## FAQ

**Q: Can I run both windows at the same time for testing?**
A: Yes, use `scripts\test_insight_generation.bat` which runs only morning window. For testing evening, modify the script or run manually:
```cmd
python -m antigravity_mcp jobs generate-brief --window evening --max-items 10
```

**Q: What happens if my computer is off at scheduled time?**
A: Task Scheduler will run the task as soon as the computer is turned on (if "Run task as soon as possible after a scheduled start is missed" is enabled).

**Q: Can I change the execution time after setup?**
A: Yes, Task Scheduler → Task → Properties → Triggers → Edit → Change time.

**Q: How do I test without waiting for scheduled time?**
A: Right-click task in Task Scheduler → **Run**, or use `scripts\test_insight_generation.bat`.

**Q: Where are insights published?**
A: Insights are saved to Notion. X (Twitter) posting is **manual** (not automated per user request).

---

## Next Steps

After successful setup:
1. ✅ Wait for first automatic run (7 AM or 6 PM)
2. ✅ Review logs: `d:\AI 프로젝트\DailyNews\logs\insights\`
3. ✅ Check Notion dashboard for new pages
4. ✅ Manually review and publish to X

See [MONITORING-GUIDE.md](./MONITORING-GUIDE.md) for detailed monitoring instructions.
