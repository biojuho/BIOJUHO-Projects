# DailyNews 자동 스케줄링 설정 가이드

**버전**: v1.0
**작성일**: 2026-03-21
**대상**: Windows Task Scheduler

---

## 📋 개요

DailyNews 인사이트 생성을 **하루 2회 자동 실행**하도록 Windows Task Scheduler를 설정합니다.

### 실행 스케줄

| 시간 | Window | 수집 기간 | 스크립트 |
|------|--------|----------|---------|
| **오전 7시** | `morning` | 전날 18:00 ~ 당일 07:00 | `run_morning_insights.bat` |
| **오후 6시** | `evening` | 당일 07:00 ~ 18:00 | `run_evening_insights.bat` |

---

## 🚀 빠른 설정 (자동)

### 1단계: PowerShell 관리자 권한으로 실행

```powershell
# Windows 키 + X → "Windows PowerShell(관리자)" 선택
```

### 2단계: 스크립트 실행

```powershell
cd "d:\AI 프로젝트\DailyNews\scripts"
.\setup_scheduled_tasks.ps1
```

### 3단계: 확인

스크립트가 자동으로:
- ✅ 기존 작업 제거 (있는 경우)
- ✅ `DailyNews_Morning_Insights` 작업 생성 (매일 7:00 AM)
- ✅ `DailyNews_Evening_Insights` 작업 생성 (매일 6:00 PM)

출력 예시:
```
=========================================
DailyNews Task Scheduler Setup
=========================================

✅ Script files found
   Morning: d:\AI 프로젝트\DailyNews\scripts\run_morning_insights.bat
   Evening: d:\AI 프로젝트\DailyNews\scripts\run_evening_insights.bat

✅ Existing tasks removed
✅ Morning task created successfully
   Task Name: DailyNews_Morning_Insights
   Schedule: Daily at 7:00 AM

✅ Evening task created successfully
   Task Name: DailyNews_Evening_Insights
   Schedule: Daily at 6:00 PM

=========================================
✅ Setup Complete!
=========================================
```

---

## 🔍 검증

### 1. Task Scheduler 열기

```powershell
# PowerShell에서
Start-Process taskschd.msc

# 또는 Win + R → "taskschd.msc" 입력
```

### 2. 작업 확인

**Task Scheduler Library** → 다음 2개 작업이 보여야 함:

| 이름 | 트리거 | 상태 | 다음 실행 시간 |
|------|--------|------|--------------|
| DailyNews_Morning_Insights | 매일 오전 7:00 | 준비 | (다음 오전 7시) |
| DailyNews_Evening_Insights | 매일 오후 6:00 | 준비 | (다음 오후 6시) |

### 3. 수동 테스트 실행

**방법 1: Task Scheduler에서**
1. 작업 우클릭 → "실행"
2. 로그 확인: `d:\AI 프로젝트\DailyNews\logs\insights\`

**방법 2: 테스트 스크립트 사용**
```cmd
cd "d:\AI 프로젝트\DailyNews\scripts"
test_insight_generation.bat morning
```

---

## 📂 파일 구조

```
DailyNews/scripts/
├── run_morning_insights.bat       # 오전 7시 실행 스크립트
├── run_evening_insights.bat       # 오후 6시 실행 스크립트
├── setup_scheduled_tasks.ps1      # 자동 설정 스크립트
└── test_insight_generation.bat    # 테스트용 스크립트

DailyNews/logs/insights/
├── morning_2026-03-21_0700.log    # 오전 실행 로그
├── evening_2026-03-21_1800.log    # 오후 실행 로그
└── (30일 이상 된 로그는 자동 삭제)
```

---

## 🔧 수동 설정 (고급)

자동 스크립트 대신 수동으로 설정하려면:

### 1. Task Scheduler 열기
```
Win + R → taskschd.msc
```

### 2. 새 작업 만들기

#### 일반 탭
- **이름**: `DailyNews_Morning_Insights`
- **설명**: `DailyNews 오전 인사이트 생성 (7:00 AM)`
- **보안 옵션**: "사용자가 로그온할 때만 실행"
- ☑ 최고 수준의 권한으로 실행 (체크 안 함)

#### 트리거 탭
- **새로 만들기** 클릭
  - 작업 시작: "일정에 따라"
  - 설정: "매일"
  - 시작 시간: `07:00:00`
  - ☑ 사용

#### 동작 탭
- **새로 만들기** 클릭
  - 작업: "프로그램 시작"
  - 프로그램/스크립트: `cmd.exe`
  - 인수 추가: `/c "d:\AI 프로젝트\DailyNews\scripts\run_morning_insights.bat"`
  - 시작 위치: `d:\AI 프로젝트\DailyNews`

#### 조건 탭
- ☑ 컴퓨터의 전원이 AC 전원일 때만 작업 시작 (체크 해제)
- ☑ 네트워크 연결을 사용할 수 있는 경우에만 시작 (체크)

#### 설정 탭
- ☑ 요청 시 작업 실행 허용 (체크)
- ☑ 작업이 실패한 경우 다시 시작 간격: `1분`, 최대 `3번`
- 작업 중지: `2시간`

### 3. 저장 및 반복

오후 작업(`DailyNews_Evening_Insights`)도 동일하게 생성하되:
- 시작 시간: `18:00:00`
- 스크립트: `run_evening_insights.bat`

---

## 📊 로그 확인

### 로그 파일 형식

```
d:\AI 프로젝트\DailyNews\logs\insights\morning_2026-03-21_0700.log
```

### 로그 내용 예시

```
=========================================
Morning Insight Generation Started
Date: 2026-03-21
Time: 0700
=========================================
Current directory: d:\AI 프로젝트\DailyNews
Activating virtual environment...
Python version:
Python 3.14.0

=========================================
Running Morning Brief Generation...
=========================================
[INFO] Loading news sources from config/news_sources.json
[INFO] Collecting 10 items for categories: Tech, Economy_KR, AI_Deep
[INFO] Fetching Tech sources... (12 sources)
[INFO] Collected 10 articles from Tech
[INFO] Generating insights with DailyNews Insight Generator...
[INFO] Insight validation: 3/4 passed (75%)
[SUCCESS] Morning insights generated successfully
=========================================

Updating Notion dashboard...
[SUCCESS] Dashboard updated
=========================================

Cleaning old logs (older than 30 days)...
Deleted 2 old log files

Script completed at 2026-03-21 0705
=========================================
```

---

## ❌ 문제 해결

### 문제 1: 작업이 실행되지 않음

**증상**: 예정 시간에 작업이 실행되지 않음

**확인 사항**:
1. Task Scheduler에서 작업 상태가 "준비" 또는 "실행 중"인지 확인
2. "기록" 탭에서 최근 실행 내역 확인
3. Windows Event Viewer 확인:
   ```
   eventvwr.msc → Windows 로그 → 응용 프로그램
   ```

**해결 방법**:
- 수동 실행 테스트: 작업 우클릭 → "실행"
- 트리거 재설정: 트리거 삭제 후 재생성

---

### 문제 2: 가상환경 활성화 실패

**증상**: 로그에 `Failed to activate virtual environment`

**확인**:
```cmd
cd "d:\AI 프로젝트\DailyNews"
dir venv\Scripts\activate.bat
```

**해결**:
```cmd
# 가상환경 재생성
cd "d:\AI 프로젝트\DailyNews"
python -m venv venv
venv\Scripts\activate
pip install -e .
```

---

### 문제 3: 로그 파일이 생성되지 않음

**증상**: `logs/insights/` 디렉토리가 비어있음

**확인**:
```cmd
dir "d:\AI 프로젝트\DailyNews\logs\insights"
```

**해결**:
```cmd
# 디렉토리 수동 생성
mkdir "d:\AI 프로젝트\DailyNews\logs\insights"
```

---

### 문제 4: 권한 오류

**증상**: `Access is denied` 오류

**해결**:
1. 스크립트 파일 권한 확인
2. Task Scheduler에서 "최고 수준의 권한으로 실행" 체크 (필요 시)
3. 또는 관리자 계정으로 작업 실행 설정

---

## 🔄 작업 수정/삭제

### 작업 수정

1. Task Scheduler 열기
2. 작업 우클릭 → "속성"
3. 설정 수정 후 "확인"

### 작업 삭제

**방법 1: Task Scheduler GUI**
1. 작업 우클릭 → "삭제"

**방법 2: PowerShell**
```powershell
# 관리자 권한 필요
Unregister-ScheduledTask -TaskName "DailyNews_Morning_Insights" -Confirm:$false
Unregister-ScheduledTask -TaskName "DailyNews_Evening_Insights" -Confirm:$false
```

**방법 3: 재설정 스크립트 재실행**
```powershell
cd "d:\AI 프로젝트\DailyNews\scripts"
.\setup_scheduled_tasks.ps1
# 기존 작업 자동 삭제 후 재생성
```

---

## ⚙️ 고급 설정

### 실행 시간 변경

```powershell
# 오전 작업을 8시로 변경
$task = Get-ScheduledTask -TaskName "DailyNews_Morning_Insights"
$task.Triggers[0].StartBoundary = (Get-Date "08:00").ToString("yyyy-MM-ddTHH:mm:ss")
Set-ScheduledTask -InputObject $task
```

### 카테고리 변경

스크립트 파일 편집:
```cmd
notepad "d:\AI 프로젝트\DailyNews\scripts\run_morning_insights.bat"

# 이 줄을 찾아서 수정:
python -m antigravity_mcp jobs generate-brief ^
    --window morning ^
    --max-items 10 ^
    --categories Tech,Economy_KR,AI_Deep,Crypto  ← 여기에 Crypto 추가
```

### 알림 추가 (선택)

스크립트 끝에 추가:
```cmd
REM 성공 시 알림 (Windows 10/11)
if %EXITCODE% equ 0 (
    powershell -Command "& {Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Morning insights generated successfully!','DailyNews','OK','Information')}"
)
```

---

## 📈 모니터링

### 실행 내역 확인

**Task Scheduler에서**:
1. 작업 선택
2. "기록" 탭 클릭
3. 최근 실행 내역, 성공/실패 여부 확인

**로그 폴더에서**:
```cmd
cd "d:\AI 프로젝트\DailyNews\logs\insights"
dir /o-d
# 최근 로그 파일 순서로 표시

type morning_2026-03-21_0700.log
# 로그 내용 확인
```

### 성공률 추적

```powershell
# 최근 30일 성공률 계산
$logs = Get-ChildItem "d:\AI 프로젝트\DailyNews\logs\insights\*.log"
$total = $logs.Count
$success = ($logs | Select-String -Pattern "\[SUCCESS\]").Count
$rate = [math]::Round(($success / $total) * 100, 2)
Write-Host "Success Rate: $rate% ($success/$total)"
```

---

## 🔔 알림 설정 (Telegram/Email)

### Telegram 알림 (권장)

스크립트 끝에 추가:
```cmd
REM Telegram 알림
if %EXITCODE% equ 0 (
    python -m antigravity_mcp ops send-telegram --message "✅ Morning insights generated"
) else (
    python -m antigravity_mcp ops send-telegram --message "❌ Morning insights failed"
)
```

### Email 알림

Windows Task Scheduler 자체 기능 사용:
1. 작업 속성 → "동작" 탭
2. "전자 메일 보내기" 추가 (Windows Server만 지원)

---

## 📚 관련 문서

- [DailyNews Insight Generator 설정 가이드](../skills/daily-insight-generator-setup.md)
- [품질 체크리스트](../../prompts/insight_quality_check.md)
- [QC 보고서](../skills/QC-REPORT.md)

---

## 🆘 지원

문제가 계속 발생하면:
1. 로그 파일 확인: `d:\AI 프로젝트\DailyNews\logs\insights\`
2. Task Scheduler 이벤트 로그 확인: `eventvwr.msc`
3. 수동 테스트 실행: `test_insight_generation.bat morning`

---

**작성자**: Claude Code Agent
**버전**: 1.0
**최종 업데이트**: 2026-03-21
