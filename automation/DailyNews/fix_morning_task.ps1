# ============================================================
# DailyNews_Morning 태스크 스케줄러 설정 수정 스크립트
# 관리자 PowerShell에서 실행: .\fix_morning_task.ps1
# ============================================================
#Requires -RunAsAdministrator

$taskName = "DailyNews_Morning"

Write-Host "=== DailyNews_Morning 태스크 업데이트 ===" -ForegroundColor Cyan

# 1) 기존 태스크 삭제
Write-Host "[1/3] 기존 태스크 삭제..." -ForegroundColor Yellow
schtasks /delete /tn $taskName /f 2>$null

# 2) 새 태스크 생성 (비밀번호 미입력 = S4U 모드)
#    S4U: 비로그인 시에도 실행 가능 (네트워크 리소스 접근 불가하지만 로컬 작업은 OK)
Write-Host "[2/3] 새 태스크 생성 (S4U + WakeToRun + 배터리 모드 허용)..." -ForegroundColor Yellow

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>매일 오전 7시 데일리 뉴스 수집</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-03-06T07:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$env:USERNAME</UserId>
      <LogonType>S4U</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT72H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>D:\AI 프로젝트\DailyNews\run_daily_news.bat</Command>
      <WorkingDirectory>D:\AI 프로젝트\DailyNews</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

$xmlPath = "$env:TEMP\DailyNews_Morning.xml"
$xml | Out-File -Encoding unicode $xmlPath -Force
schtasks /create /tn $taskName /xml $xmlPath /f

# 3) 결과 확인
Write-Host "`n[3/3] 결과 확인:" -ForegroundColor Yellow
schtasks /query /tn $taskName /fo LIST /v | Select-String -Pattern "TaskName|Status|Next Run|Last Run|Last Result|Logon Mode|Power|Start Time"

Write-Host "`n✅ 완료!" -ForegroundColor Green
Write-Host "주요 변경사항:" -ForegroundColor Cyan
Write-Host "  - LogonType: Interactive → S4U (비로그인 시에도 실행)" -ForegroundColor White
Write-Host "  - DisallowStartIfOnBatteries: true → false (배터리 모드 허용)" -ForegroundColor White
Write-Host "  - StopIfGoingOnBatteries: true → false" -ForegroundColor White
Write-Host "  - StartWhenAvailable: false → true (미실행 시 자동 재시도)" -ForegroundColor White
Write-Host "  - WakeToRun: false → true (절전 모드에서 깨우기)" -ForegroundColor White
