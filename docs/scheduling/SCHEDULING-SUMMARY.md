# DailyNews Insight Generator - Scheduling Summary

## Quick Reference

| Aspect | Details |
|--------|---------|
| **Schedule** | 2x daily (7 AM, 6 PM KST) |
| **Method** | Windows Task Scheduler |
| **Setup Script** | `scripts\setup_scheduled_tasks.ps1` |
| **Test Script** | `scripts\test_insight_generation.bat` |
| **Logs** | `DailyNews\logs\insights\*.log` |
| **Output** | Notion database (manual X publishing) |

---

## Files Created

### Scripts (4 files)
1. **`scripts/run_morning_insights.bat`** - 7 AM execution script
2. **`scripts/run_evening_insights.bat`** - 6 PM execution script
3. **`scripts/setup_scheduled_tasks.ps1`** - PowerShell auto-setup
4. **`scripts/test_insight_generation.bat`** - Manual testing

### Documentation (3 files)
1. **`docs/scheduling/SETUP-GUIDE.md`** - Comprehensive setup instructions
2. **`docs/scheduling/MONITORING-GUIDE.md`** - First-run monitoring checklist
3. **`docs/scheduling/SCHEDULING-SUMMARY.md`** - This file (quick reference)

---

## One-Time Setup (5 minutes)

```powershell
# 1. Open PowerShell as Administrator
# 2. Run setup script
cd "d:\AI 프로젝트"
PowerShell -ExecutionPolicy Bypass -File scripts\setup_scheduled_tasks.ps1

# 3. Verify in Task Scheduler
taskschd.msc
```

**Expected result:**
- ✅ 2 scheduled tasks created
- ✅ Morning task: runs daily at 7:00 AM
- ✅ Evening task: runs daily at 6:00 PM

---

## Daily Workflow

### Automated (No Action Required)
1. **7:00 AM** - Task Scheduler runs morning window insight generation
2. **6:00 PM** - Task Scheduler runs evening window insight generation

### Manual (Your Action)
1. **Check Notion** (after 7:30 AM / 6:30 PM)
   - Open DailyNews database
   - Review newly created insight pages
2. **Publish to X** (when ready)
   - Copy X long-form post from Notion page
   - Paste into X (Premium Plus required)
   - Add images/hashtags if desired
   - Publish manually

**Why manual publishing?**
Per user request: "X API 자동 발행 은 X 정책에 위배 우려로 진행안해" (X API auto-posting excluded due to policy concerns)

---

## Monitoring

### Health Check (Weekly)

```cmd
REM 1. Check scheduled tasks are running
schtasks /query /tn "DailyNews_Morning_Insights" | findstr "Status Ready"
schtasks /query /tn "DailyNews_Evening_Insights" | findstr "Status Ready"

REM 2. Check recent logs for errors
cd "d:\AI 프로젝트\DailyNews\logs\insights"
findstr /s "ERROR" *.log

REM 3. Check Notion has recent pages (manual)
```

**Expected:**
- Both tasks show "Status: Ready"
- No ERROR lines in logs
- Notion has 2 new pages per day (14 per week)

### Log Rotation
- Automatic: Old logs deleted after 30 days (handled by batch scripts)
- Manual: `del /q "d:\AI 프로젝트\DailyNews\logs\insights\*.log"` (if needed)

---

## Troubleshooting Quick Reference

| Symptom | Quick Fix |
|---------|-----------|
| Task never runs | Check Task Scheduler → Task → Properties → Triggers |
| Task runs but fails | Check `logs\insights\[latest].log` for ERROR messages |
| No Notion pages | Verify NOTION_API_KEY in `.env` |
| Validation always fails | Review quality scores in log, adjust thresholds if needed |
| Computer was off during scheduled time | Task will run at next boot (if "Run as soon as possible..." enabled) |

**Full troubleshooting:** See [SETUP-GUIDE.md](./SETUP-GUIDE.md#troubleshooting)

---

## Customization

### Change Schedule
Edit triggers in Task Scheduler:
- Right-click task → Properties → Triggers → Edit → Change time

### Add/Remove Categories
Edit `scripts/run_morning_insights.bat` and `scripts/run_evening_insights.bat`:
```batch
REM Change this line:
--categories Tech,Economy_KR,AI_Deep

REM To (example):
--categories Tech,Economy_KR,AI_Deep,Crypto,DeSci
```

### Adjust Max Items
```batch
REM Change this line:
--max-items 10

REM To (example):
--max-items 20
```

---

## Uninstall

```cmd
REM Remove scheduled tasks
schtasks /delete /tn "DailyNews_Morning_Insights" /f
schtasks /delete /tn "DailyNews_Evening_Insights" /f

REM (Optional) Remove scripts
del "d:\AI 프로젝트\scripts\run_morning_insights.bat"
del "d:\AI 프로젝트\scripts\run_evening_insights.bat"
del "d:\AI 프로젝트\scripts\setup_scheduled_tasks.ps1"
```

---

## Next Steps

After successful setup:
1. ✅ Wait for first automatic run (7 AM or 6 PM)
2. ✅ Follow [MONITORING-GUIDE.md](./MONITORING-GUIDE.md) to verify
3. ✅ Establish daily routine: Check Notion → Review → Publish to X
4. ✅ Track engagement on X to refine insight quality

---

**Questions?** See [SETUP-GUIDE.md](./SETUP-GUIDE.md) for comprehensive documentation.
