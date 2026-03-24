# Docker Desktop WSL Service Fix Guide

**Issue**: Docker Desktop fails to start with `Wsl/0x80070422` error
**Root Cause**: WslService is disabled in Windows
**Date**: 2026-03-24

---

## Error Symptoms

```
running wslexec: The service cannot be started, either because it is disabled
or because it has no enabled devices associated with it.
오류 코드: Wsl/0x80070422
```

**Service Status**:
```powershell
Name                Status StartType
----                ------ ---------
com.docker.service Stopped    Manual
vmcompute          Stopped    Manual
WslService         Stopped  Disabled  # ⚠️ Problem
```

---

## Solution: Enable WSL Service

### Option 1: PowerShell (Recommended) ✅

**Step 1**: Open PowerShell as Administrator
- Press `Win + X`
- Click "Windows PowerShell (Admin)" or "Terminal (Admin)"

**Step 2**: Run these commands:
```powershell
# Enable WSL Service
Set-Service -Name WslService -StartupType Manual

# Start required services
Start-Service WslService
Start-Service vmcompute
Start-Service com.docker.service

# Verify services are running
Get-Service -Name 'com.docker.service','WslService','vmcompute' | Select-Object Name,Status,StartType
```

**Expected Output**:
```
Name                Status  StartType
----                ------  ---------
com.docker.service Running    Manual
vmcompute          Running    Manual
WslService         Running    Manual
```

**Step 3**: Verify Docker is working
```powershell
docker version
```

### Option 2: Services GUI 🖱️

1. Press `Win + R`, type `services.msc`, click OK
2. Find **"Windows Subsystem for Linux"** (WslService)
3. Right-click → **Properties**
4. Change **Startup type** to **Manual**
5. Click **Start** button
6. Click **Apply** → **OK**
7. Repeat for **"Hyper-V Host Compute Service"** (vmcompute)
8. Repeat for **"Docker Desktop Service"** (com.docker.service)

### Option 3: Command Prompt (Admin)

```cmd
sc config WslService start= demand
net start WslService
net start vmcompute
net start com.docker.service
```

---

## Alternative: Use SQLite Instead of PostgreSQL

If Docker cannot be fixed immediately, AgriGuard can use SQLite:

```bash
# In AgriGuard/backend/.env
DATABASE_URL=sqlite:///./agriguard.db

# SQLite is the default - just don't set POSTGRES_* env vars
```

**Note**: Week 1 migration work already supports dual-database mode.

---

## Post-Fix: Resume AgriGuard Week 2

Once Docker is running:

```powershell
# Navigate to project root
cd "d:\AI 프로젝트"

# Run Week 2 validation script
powershell -NoProfile -ExecutionPolicy Bypass -File AgriGuard/validate_postgres_week2.ps1
```

---

## Verification Checklist

- [ ] WslService is **Running** (not Stopped)
- [ ] WslService startup type is **Manual** (not Disabled)
- [ ] vmcompute is **Running**
- [ ] com.docker.service is **Running**
- [ ] `docker version` shows **both Client and Server** versions
- [ ] Docker Desktop GUI shows "Engine running"

---

## Troubleshooting

### WSL still won't start after enabling

**Check Windows Features**:
```powershell
# Check if WSL is enabled
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux

# Enable if needed (requires reboot)
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart
```

### Docker Desktop starts but containers fail

**Reset Docker to factory defaults**:
- Docker Desktop → Settings → Troubleshoot → Reset to factory defaults

### Virtual Machine Platform missing

```powershell
# Enable Virtual Machine Platform (required for WSL 2)
Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart

# Reboot required after this
```

---

## Related Documentation

- [POSTGRESQL_MIGRATION_PLAN.md](POSTGRESQL_MIGRATION_PLAN.md)
- [AgriGuard/validate_postgres_week2.ps1](../AgriGuard/validate_postgres_week2.ps1)
- [Microsoft WSL Documentation](https://learn.microsoft.com/en-us/windows/wsl/)

---

**Status**: ⚠️ Blocking AgriGuard PostgreSQL Week 2
**Priority**: P2
**Requires**: Administrator privileges on Windows

🤖 Generated with [Claude Code](https://claude.com/claude-code)
