# DailyNews Insight Generator - First Run Monitoring Guide

## Purpose

This guide helps you monitor the first automatic execution of the DailyNews insight generator to ensure everything works correctly.

---

## Pre-Flight Checklist (Before First Run)

Run this checklist **before** the first scheduled execution:

### 1. Task Scheduler Status

```cmd
schtasks /query /tn "DailyNews_Morning_Insights" /fo list /v
schtasks /query /tn "DailyNews_Evening_Insights" /fo list /v
```

**Expected output:**
```
Task To Run: cmd.exe /c "d:\AI 프로젝트\scripts\run_morning_insights.bat"
Status: Ready
Next Run Time: [Tomorrow] 7:00:00 AM
```

- [ ] Status = **Ready** (not Disabled/Running)
- [ ] Next Run Time is correct
- [ ] Task To Run path is correct

### 2. Log Directory

```cmd
dir "d:\AI 프로젝트\DailyNews\logs\insights"
```

- [ ] Directory exists (created by batch script on first run, but verify permissions)

### 3. Manual Test

```cmd
cd "d:\AI 프로젝트"
scripts\test_insight_generation.bat
```

**Check:**
- [ ] Script completes without errors
- [ ] Log file created in `logs\insights\`
- [ ] Notion page created (check your Notion workspace)
- [ ] Validation passed (check log for "Validation PASSED" or Notion page for ✅)

### 4. API Keys

```cmd
cd "d:\AI 프로젝트\DailyNews"
call venv\Scripts\activate.bat
python -c "from antigravity_mcp.config import get_settings; s=get_settings(); print('✓ GEMINI_API_KEY:', 'OK' if s.gemini_api_key else 'MISSING'); print('✓ NOTION_API_KEY:', 'OK' if s.notion_api_key else 'MISSING')"
```

- [ ] GEMINI_API_KEY: OK
- [ ] NOTION_API_KEY: OK

---

## Timeline: First Scheduled Run

### T-30 minutes (Before Scheduled Time)

**What to do:**
1. Ensure computer is **on** and **connected to network**
2. Open Task Scheduler (`taskschd.msc`)
3. Navigate to task folder and select the upcoming task (morning or evening)
4. Keep Task Scheduler window open

**What to watch:**
- **Status** column shows "Ready"
- **Next Run Time** matches current date/time + buffer

### T-5 minutes

**What to do:**
1. Open File Explorer to `d:\AI 프로젝트\DailyNews\logs\insights\`
2. Sort by **Date Modified** (newest first)
3. Keep window visible to see new log file appear

**What to watch:**
- No new log files yet

### T=0 (Scheduled Time: 7:00 AM or 6:00 PM)

**What to expect:**

**Within 1 minute:**
- Task Scheduler **Status** changes from "Ready" → "**Running**"
- New log file appears in `logs\insights\`
  - Filename format: `morning_YYYYMMDD_HHMMSS.log` or `evening_YYYYMMDD_HHMMSS.log`

**If Status doesn't change:**
1. Check Event Viewer (see troubleshooting below)
2. Verify computer time is correct
3. Verify task is enabled (right-click → Enable)

### T+1 to T+5 minutes (During Execution)

**What to do:**
1. Open the new log file in Notepad
2. Refresh periodically (Ctrl+R or close/reopen)

**What to watch:**
```
==========================================
DailyNews Morning Insights
Started: 2026-03-21 07:00:01
==========================================
Running morning window insight generation...
[API calls to news sources...]
[LLM insight generation...]
[Validation checks...]
SUCCESS: Morning insights generated
==========================================
Finished: 2026-03-21 07:04:23
==========================================
```

**Red flags:**
- Lines starting with "ERROR:"
- Python tracebacks (lines starting with "Traceback (most recent call last):")
- Script stops before "Finished:" line

### T+5 to T+10 minutes (After Execution)

**What to do:**
1. Check Task Scheduler **Status** → Should return to "Ready"
2. Check **Last Run Time** → Should show current date/time
3. Check **Last Run Result**:
   - `0x0` = Success
   - `0x1` or other = Error (see troubleshooting)

**Verify outputs:**

**1. Log File**
```cmd
type "d:\AI 프로젝트\DailyNews\logs\insights\[latest log file].log"
```
- [ ] Contains "SUCCESS: Morning insights generated"
- [ ] No "ERROR:" lines

**2. Notion Dashboard**
- Open your Notion workspace
- Navigate to DailyNews database
- Sort by **Created** (newest first)
- [ ] New page exists with today's date
- [ ] **Category**: Tech / Economy_KR / AI_Deep (at least one)
- [ ] **Window**: Morning (or Evening)
- [ ] **Status**: Draft
- [ ] **Validation Passed**: ✅ (green checkmark)
- [ ] **Quality Scores** section shows P1, P2, P3 scores (all ≥ 0.6)

**3. X Long-Form Post (in Notion page)**
- Scroll to bottom of Notion page
- [ ] "X Long-Form Post" section exists
- [ ] Post is formatted with structure:
  ```
  🧵 [Hook]

  1️⃣ [Principle 1: Fact→Trend]

  2️⃣ [Principle 2: Ripple Effect]

  3️⃣ [Principle 3: Action Items]

  💬 [CTA / Question]
  ```
- [ ] Character count shown (should be ~800-1000 for long-form)

---

## Success Criteria

First run is **successful** if all of these are true:

- [x] Task Scheduler shows Last Run Result: `0x0`
- [x] Log file contains "SUCCESS: Morning insights generated"
- [x] At least 1 new Notion page created
- [x] Notion page has ✅ validation passed
- [x] Notion page contains X long-form post

---

## Troubleshooting

### Issue 1: Task Status Never Changes to "Running"

**Possible causes:**
1. Task is disabled
2. Computer time is incorrect
3. Task Scheduler service is stopped

**Steps to diagnose:**
```cmd
REM Check task is enabled
schtasks /query /tn "DailyNews_Morning_Insights" | findstr "Status"

REM Check computer time
echo %date% %time%

REM Check Task Scheduler service
sc query Schedule
```

**Solutions:**
1. Enable task: Right-click task → **Enable**
2. Sync computer time: Settings → Time & Language → Sync now
3. Start service: `sc start Schedule`

### Issue 2: Task Runs But Fails (Last Run Result ≠ 0x0)

**Step 1: Check Event Viewer**
```cmd
eventvwr.msc
```
Navigate to: **Windows Logs** → **Application**
Filter by **Source**: **Task Scheduler**
Look for errors around scheduled time.

**Step 2: Check Log File**
```cmd
cd "d:\AI 프로젝트\DailyNews\logs\insights"
type [latest log file].log
```

**Common errors:**

**Error: "Failed to activate venv"**
- Cause: Virtual environment not found or corrupted
- Solution:
  ```cmd
  cd "d:\AI 프로젝트\DailyNews"
  python -m venv venv --clear
  call venv\Scripts\activate.bat
  pip install -r requirements.txt
  ```

**Error: "ModuleNotFoundError: No module named 'antigravity_mcp'"**
- Cause: Package not installed in venv
- Solution:
  ```cmd
  cd "d:\AI 프로젝트\DailyNews"
  call venv\Scripts\activate.bat
  pip install -e .
  ```

**Error: "GEMINI_API_KEY not found"**
- Cause: `.env` file missing or incomplete
- Solution: Copy `.env.example` to `.env` and fill in API keys

### Issue 3: Task Runs Successfully But No Notion Page

**Check 1: Notion API Token**
```cmd
cd "d:\AI 프로젝트\DailyNews"
call venv\Scripts\activate.bat
python -c "from antigravity_mcp.config import get_settings; print(get_settings().notion_api_key[:10])"
```
Should print first 10 characters (not empty).

**Check 2: Notion Database ID**
```cmd
python -c "from antigravity_mcp.config import get_settings; print(get_settings().notion_database_id)"
```
Should print a valid UUID.

**Check 3: Notion Integration Permissions**
- Open Notion workspace
- Go to Settings & Members → Connections
- Verify "DailyNews" integration has access to the database

### Issue 4: Validation Always Fails

**Check validation scores in log:**
```
Principle 1 (점→선 연결): 0.35 / 0.60 FAIL
Principle 2 (파급 효과): 0.45 / 0.60 FAIL
Principle 3 (실행 항목): 0.25 / 0.60 FAIL
```

**Possible causes:**
1. LLM not following prompt instructions (check `generator.py` prompts)
2. Validator thresholds too high (check `validator.py` THRESHOLDS)
3. News sources provide low-quality data

**Temporary workaround (testing only):**
Lower thresholds in `.agent/skills/daily-insight-generator/validator.py`:
```python
THRESHOLDS = {
    "principle_1": 0.4,  # Was 0.6
    "principle_2": 0.4,  # Was 0.6
    "principle_3": 0.4,  # Was 0.6
}
```

**Permanent fix:**
Review and improve prompts in `generator.py` to enforce quality principles more explicitly.

---

## Event Viewer Quick Reference

**To check Task Scheduler events:**
1. Open Event Viewer: `eventvwr.msc`
2. Navigate: **Windows Logs** → **Application**
3. Click **Filter Current Log** in right panel
4. **Event sources**: Select **Task Scheduler**
5. Click **OK**

**Important Event IDs:**
| Event ID | Level | Meaning |
|----------|-------|---------|
| 100 | Information | Task started |
| 102 | Information | Task completed successfully |
| 103 | Error | Task failed to start |
| 111 | Error | Task terminated (timeout or crash) |
| 201 | Error | Task action failed to execute |

---

## Next Steps After Successful First Run

1. ✅ **Review Notion page content**
   - Read generated insight
   - Verify 3 quality principles are met
   - Check actionable items make sense

2. ✅ **Test manual publishing to X**
   - Copy X long-form post from Notion
   - Paste into X (Premium Plus account required for long-form)
   - Add images if desired
   - Publish

3. ✅ **Monitor second run**
   - Wait for next scheduled time (morning or evening)
   - Verify consistency (should succeed again)

4. ✅ **Establish routine**
   - Check Notion dashboard daily (after 7:30 AM and 6:30 PM)
   - Review and publish insights to X
   - Track engagement (likes, retweets, replies)

5. ✅ **Tune categories (optional)**
   - If certain categories consistently produce low-quality insights, remove them
   - If interested in new topics, add categories to scripts

---

## Monitoring Checklist (Print This)

**First Run Checklist:**

```
Date: __________  Time: __________  Window: [ ] Morning [ ] Evening

Pre-Flight:
[ ] Task Scheduler status: Ready
[ ] Next Run Time correct
[ ] Manual test passed
[ ] API keys configured

T=0 (Scheduled Time):
[ ] Status changed to "Running"
[ ] Log file appeared

T+5 (After Execution):
[ ] Status returned to "Ready"
[ ] Last Run Result: 0x0
[ ] Log shows "SUCCESS"

Output Verification:
[ ] Notion page created
[ ] Validation passed (✅)
[ ] X long-form post exists
[ ] Quality scores ≥ 0.6

Post-Run:
[ ] Reviewed insight content
[ ] Published to X (manual)
[ ] Noted any issues: ___________________

Ready for production? [ ] Yes [ ] No (explain): ___________________
```

---

## Support

If first run fails after following this guide:
1. Save log file: `d:\AI 프로젝트\DailyNews\logs\insights\[failed run].log`
2. Export Event Viewer logs: Event Viewer → Windows Logs → Application → Save Filtered Log
3. Check GitHub issues: [project repo]/issues
4. Create new issue with logs attached

---

**Good luck with your first run!** 🚀
