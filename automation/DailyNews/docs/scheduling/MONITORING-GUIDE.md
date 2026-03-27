# DailyNews 자동 스케줄링 — 모니터링 가이드

**날짜**: 2026-03-21
**버전**: v1.0
**대상**: 운영 담당자

---

## 📊 첫 자동 실행 대기 중

설정이 완료되었습니다! 다음 실행까지 대기하는 동안 준비할 사항을 안내합니다.

### ⏰ 다음 실행 예정 시간

Task Scheduler에서 확인:
1. `taskschd.msc` 실행
2. `DailyNews_Morning_Insights` 또는 `DailyNews_Evening_Insights` 선택
3. **다음 실행 시간** 확인

**예시**:
- 현재 시간: 2026-03-21 오후 2시
- 다음 실행: **2026-03-21 오후 6시** (Evening)
- 그 다음: **2026-03-22 오전 7시** (Morning)

---

## 🔍 실시간 모니터링 방법

### 방법 1: Task Scheduler 실시간 확인

```
1. taskschd.msc 실행
2. DailyNews 작업 선택
3. "기록" 탭 클릭
4. 자동 새로고침: F5 키
```

**상태 표시**:
- **실행 중**: 작업이 현재 진행 중
- **완료됨 (0x0)**: 성공
- **완료됨 (0x1)**: 실패

### 방법 2: 로그 폴더 모니터링

```cmd
# 실시간 로그 폴더 감시
cd "d:\AI 프로젝트\DailyNews\logs\insights"
dir /o-d

# 30초마다 자동 새로고침
:loop
cls
dir /o-d
timeout /t 30
goto loop
```

### 방법 3: PowerShell 실시간 로그 모니터링

```powershell
# 최신 로그 파일 자동 추적
$logPath = "d:\AI 프로젝트\DailyNews\logs\insights"
Get-ChildItem $logPath -Filter *.log |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1 |
    Get-Content -Wait -Tail 50
```

---

## 📝 첫 실행 후 확인 체크리스트

### ✅ 1. 로그 파일 생성 확인

```cmd
cd "d:\AI 프로젝트\DailyNews\logs\insights"
dir /o-d
```

**예상 파일**:
- `morning_2026-03-22_0700.log` (오전 실행)
- `evening_2026-03-21_1800.log` (오후 실행)

### ✅ 2. 로그 내용 확인

```cmd
type evening_2026-03-21_1800.log
```

**확인할 내용**:

#### ✅ 정상 실행 표시
```
=========================================
Evening Insight Generation Started
Date: 2026-03-21
Time: 1800
=========================================
```

#### ✅ 가상환경 활성화
```
Activating virtual environment...
Python version:
Python 3.14.0
```

#### ✅ 인사이트 생성 성공
```
=========================================
Running Evening Brief Generation...
=========================================
[INFO] Loading news sources from config/news_sources.json
[INFO] Collecting 10 items for categories: Tech, Economy_KR, AI_Deep
[INFO] Collected 10 articles
[INFO] Generating insights with DailyNews Insight Generator...
[INFO] Insight validation: 3/4 passed (75%)
[SUCCESS] Evening insights generated successfully
=========================================
```

#### ✅ Notion 업데이트
```
Updating Notion dashboard...
[SUCCESS] Dashboard updated
```

#### ✅ 정상 종료
```
Script completed at 2026-03-21 1805
=========================================
```

### ✅ 3. Notion 대시보드 확인

1. Notion 열기
2. DailyNews 대시보드 페이지 이동
3. 새 리포트 확인:
   - 카테고리: Tech, Economy_KR, AI_Deep
   - 생성 시간: 18:00 ~ 18:05 사이
   - 인사이트 개수: 3~4개

### ✅ 4. Task Scheduler 기록 확인

```
1. taskschd.msc 실행
2. DailyNews_Evening_Insights 선택
3. "기록" 탭 → 최근 작업 확인
4. "마지막 실행 결과": 0x0 (성공)
```

---

## 🚨 에러 대응 가이드

### Case 1: 작업이 실행되지 않음

**증상**: 예정 시간이 지났지만 로그 파일이 생성되지 않음

**원인 진단**:
1. Task Scheduler에서 작업 상태 확인
2. "마지막 실행 결과" 확인
3. Windows Event Viewer 확인:
   ```
   eventvwr.msc → Windows 로그 → 응용 프로그램
   ```

**해결 방법**:

#### A. 트리거 시간 확인
```powershell
$task = Get-ScheduledTask -TaskName "DailyNews_Evening_Insights"
$task.Triggers[0].StartBoundary
# 출력: 2026-03-21T18:00:00 (확인)
```

#### B. 작업 수동 실행 테스트
```
Task Scheduler → 작업 우클릭 → "실행"
```

#### C. 시스템 시간 확인
```cmd
time
date
# 시스템 시간이 정확한지 확인
```

---

### Case 2: 가상환경 활성화 실패

**로그 에러**:
```
[ERROR] Failed to activate virtual environment
```

**해결 방법**:

```cmd
# 1. 가상환경 경로 확인
cd "d:\AI 프로젝트\DailyNews"
dir venv\Scripts\activate.bat

# 2. 없으면 재생성
python -m venv venv
venv\Scripts\activate
pip install -e .
```

---

### Case 3: 인사이트 생성 실패

**로그 에러**:
```
[ERROR] Morning insight generation failed with exit code 1
```

**원인 가능성**:
1. ❌ 네트워크 연결 없음 (RSS 피드 수집 실패)
2. ❌ LLM API 키 만료
3. ❌ Notion API 오류
4. ❌ Python 패키지 누락

**진단 방법**:

```cmd
# 수동 테스트 실행
cd "d:\AI 프로젝트\DailyNews\scripts"
test_insight_generation.bat morning

# 상세 에러 메시지 확인
```

**해결 방법**:

#### A. 네트워크 확인
```cmd
ping google.com
```

#### B. API 키 확인
```cmd
cd "d:\AI 프로젝트\DailyNews"
type .env | findstr "API_KEY"
# GOOGLE_API_KEY=...
# NOTION_API_KEY=...
```

#### C. 패키지 재설치
```cmd
cd "d:\AI 프로젝트\DailyNews"
venv\Scripts\activate
pip install -e . --force-reinstall
```

---

### Case 4: Notion 업데이트 실패

**로그 경고**:
```
[WARNING] Dashboard update failed but insights were generated
```

**영향**: 인사이트는 생성되었으나 Notion에 저장 안 됨

**원인**:
1. Notion API 키 만료
2. Notion 데이터베이스 ID 변경
3. 네트워크 일시 오류

**해결 방법**:

```cmd
# 수동 대시보드 업데이트
cd "d:\AI 프로젝트\DailyNews"
venv\Scripts\activate
python -m antigravity_mcp ops refresh-dashboard
```

---

## 📈 성공률 모니터링

### 일일 성공률 확인

```powershell
# 오늘 실행된 작업의 성공률
$today = (Get-Date).ToString("yyyy-MM-dd")
$logs = Get-ChildItem "d:\AI 프로젝트\DailyNews\logs\insights\*$today*.log"

$total = $logs.Count
$success = ($logs | Select-String -Pattern "\[SUCCESS\]").Count

Write-Host "Today's Success Rate: $success / $total"
```

### 주간 성공률 확인

```powershell
# 최근 7일 성공률
$logs = Get-ChildItem "d:\AI 프로젝트\DailyNews\logs\insights\*.log" -Recurse |
    Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-7) }

$total = $logs.Count
$success = ($logs | Select-String -Pattern "\[SUCCESS\]").Count
$rate = [math]::Round(($success / $total) * 100, 2)

Write-Host "Weekly Success Rate: $rate% ($success/$total)"
```

### 월간 리포트

```powershell
# 월간 실행 통계
$month = (Get-Date).ToString("yyyy-MM")
$logs = Get-ChildItem "d:\AI 프로젝트\DailyNews\logs\insights\*$month*.log"

$morning = ($logs | Where-Object { $_.Name -like "morning*" }).Count
$evening = ($logs | Where-Object { $_.Name -like "evening*" }).Count
$success = ($logs | Select-String -Pattern "\[SUCCESS\]").Count
$failed = ($logs | Select-String -Pattern "\[ERROR\]").Count

Write-Host "========================================="
Write-Host "Monthly Report: $month"
Write-Host "========================================="
Write-Host "Total Runs: $($logs.Count)"
Write-Host "  - Morning: $morning"
Write-Host "  - Evening: $evening"
Write-Host "Success: $success"
Write-Host "Failed: $failed"
Write-Host "Success Rate: $([math]::Round(($success / $logs.Count) * 100, 2))%"
Write-Host "========================================="
```

---

## 🔔 알림 설정 (선택 사항)

### 방법 1: Windows 알림 (간단)

`run_morning_insights.bat` 끝에 추가:
```cmd
REM 성공 시 알림
if %EXITCODE% equ 0 (
    msg %username% "DailyNews Morning Insights: SUCCESS"
) else (
    msg %username% "DailyNews Morning Insights: FAILED - Check logs"
)
```

### 방법 2: Telegram 알림 (권장)

`.env`에 추가:
```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

스크립트에 추가:
```cmd
REM Telegram 알림
if %EXITCODE% equ 0 (
    python -m antigravity_mcp ops send-telegram --message "✅ Morning insights generated"
) else (
    python -m antigravity_mcp ops send-telegram --message "❌ Morning insights FAILED"
)
```

### 방법 3: Email 알림

PowerShell 스크립트 작성:
```powershell
# send-email-notification.ps1
param([string]$Subject, [string]$Body)

$From = "dailynews@example.com"
$To = "admin@example.com"
$SmtpServer = "smtp.gmail.com"
$SmtpPort = 587

Send-MailMessage -From $From -To $To -Subject $Subject -Body $Body -SmtpServer $SmtpServer -Port $SmtpPort -UseSsl
```

---

## 📊 대시보드 모니터링

### Notion 대시보드 확인 사항

#### 1. 리포트 생성 빈도
- ✅ 매일 2개 리포트 생성 (오전, 오후)
- ✅ 카테고리별 분리

#### 2. 인사이트 품질
- ✅ 원칙 1 (점→선 연결) 충족
- ✅ 원칙 2 (파급 효과) 충족
- ✅ 원칙 3 (실행 항목) 충족
- ✅ 검증 통과율 60% 이상

#### 3. 데이터 신선도
- ✅ 최신 뉴스 포함 (수집 윈도우 내)
- ✅ 중복 기사 제거
- ✅ 다중 소스 통합

---

## 🛠️ 최적화 가이드

### 1. 실행 시간 조정

더 빠른 실행이 필요하면:

```powershell
# 카테고리 수 줄이기
# run_morning_insights.bat 수정:
--categories Tech  # Economy_KR, AI_Deep 제거

# 최대 아이템 수 줄이기
--max-items 5  # 10 → 5
```

### 2. 로그 보관 기간 조정

```cmd
REM run_morning_insights.bat에서
REM 30일 → 90일로 변경
forfiles /p "%LOG_DIR%" /s /m *.log /d -90 /c "cmd /c del @path"
```

### 3. 재시도 횟수 조정

Task Scheduler 설정:
```
작업 속성 → 설정 탭
→ 작업이 실패한 경우 다시 시작 간격: 1분
→ 다시 시작 횟수: 3회 → 5회로 변경
```

---

## 📅 정기 점검 스케줄

### 매일
- [ ] 로그 폴더에 새 파일 생성 확인
- [ ] Notion 대시보드에 새 리포트 확인

### 매주 (월요일)
- [ ] 주간 성공률 확인 (90% 이상 목표)
- [ ] 에러 로그 검토
- [ ] 디스크 공간 확인 (로그 폴더)

### 매월 (1일)
- [ ] 월간 리포트 생성
- [ ] 인사이트 품질 샘플링 검토
- [ ] API 사용량 확인 (Gemini, Notion)
- [ ] 로그 아카이빙 (필요 시)

---

## 🎯 성능 지표 (KPI)

### 목표 수치

| 지표 | 목표 | 현재 | 상태 |
|------|------|------|------|
| 실행 성공률 | ≥ 95% | 측정 대기 | ⏳ |
| 평균 실행 시간 | ≤ 5분 | 측정 대기 | ⏳ |
| 인사이트 품질 | ≥ 80% 검증 통과 | 측정 대기 | ⏳ |
| 로그 저장 공간 | ≤ 100MB/월 | 측정 대기 | ⏳ |

### 측정 방법

```powershell
# 평균 실행 시간 계산
$logs = Get-ChildItem "d:\AI 프로젝트\DailyNews\logs\insights\*.log"
$durations = @()

foreach ($log in $logs) {
    $content = Get-Content $log -Raw
    if ($content -match "Started.*(\d{4}).*completed.*(\d{4})") {
        $start = $matches[1]
        $end = $matches[2]
        $duration = [int]$end - [int]$start
        $durations += $duration
    }
}

$avgDuration = ($durations | Measure-Object -Average).Average
Write-Host "Average Execution Time: $avgDuration seconds"
```

---

## 📚 관련 명령어 참조

### Task Scheduler 관리

```powershell
# 모든 DailyNews 작업 조회
Get-ScheduledTask | Where-Object { $_.TaskName -like "DailyNews*" }

# 작업 비활성화 (일시 중지)
Disable-ScheduledTask -TaskName "DailyNews_Morning_Insights"

# 작업 활성화 (재개)
Enable-ScheduledTask -TaskName "DailyNews_Morning_Insights"

# 작업 삭제
Unregister-ScheduledTask -TaskName "DailyNews_Morning_Insights" -Confirm:$false

# 작업 수동 실행
Start-ScheduledTask -TaskName "DailyNews_Morning_Insights"
```

### 로그 관리

```cmd
REM 최신 로그 10개 보기
cd "d:\AI 프로젝트\DailyNews\logs\insights"
dir /o-d /b | more

REM 특정 날짜 로그 찾기
dir *2026-03-21*.log

REM 실패한 작업 찾기
findstr /s /i "ERROR" *.log

REM 성공한 작업 찾기
findstr /s /i "SUCCESS" *.log
```

---

## 🎉 모니터링 대시보드 (향후 계획)

### Phase 4 구현 예정

- [ ] **실시간 웹 대시보드**
  - Streamlit 기반
  - 실행 상태 실시간 표시
  - 성공률 차트
  - 최근 로그 스트리밍

- [ ] **자동 알림 시스템**
  - Telegram 통합
  - 실패 즉시 알림
  - 일일/주간 리포트 자동 발송

- [ ] **성능 분석**
  - 카테고리별 실행 시간
  - API 호출 비용 추적
  - 인사이트 품질 트렌드

---

**모니터링 가이드 작성 완료**
**날짜**: 2026-03-21
**버전**: v1.0

이제 첫 자동 실행을 기다리시면 됩니다! 📊✨
