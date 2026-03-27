@echo off
REM ===================================================
REM  fix_schedulers.bat — 관리자 권한으로 실행 필수
REM  GetDayTrends + CostDashboard 스케줄러 재활성화
REM ===================================================

echo [1/4] GetDayTrends 태스크 활성화...
schtasks /Change /TN "\GetDayTrends" /ENABLE
if %ERRORLEVEL%==0 (echo   → 성공) else (echo   → 실패 [%ERRORLEVEL%])

echo [2/4] CostDashboard 태스크 활성화...
schtasks /Change /TN "\CostDashboard" /ENABLE
if %ERRORLEVEL%==0 (echo   → 성공) else (echo   → 실패 [%ERRORLEVEL%])

echo [3/4] CostDashboard 배터리 제한 해제...
REM schtasks /Change 로는 배터리 설정 변경 불가 → XML 수정 필요
REM 대신 PowerShell로 직접 수정
powershell -Command "$t = Get-ScheduledTask -TaskName 'CostDashboard' -ErrorAction SilentlyContinue; if ($t) { $t.Settings.DisallowStartIfOnBatteries = $false; $t.Settings.StopIfGoingOnBatteries = $false; Set-ScheduledTask -InputObject $t; Write-Host '  → 성공' } else { Write-Host '  → 태스크 없음' }"

echo [4/4] GetDayTrends_AutoStart 점검...
schtasks /Query /TN "\GetDayTrends_AutoStart" /FO CSV /NH 2>nul
if %ERRORLEVEL%==0 (
    schtasks /Change /TN "\GetDayTrends_AutoStart" /ENABLE 2>nul
    echo   → 확인 완료
) else (
    echo   → 태스크 미존재 (정상: 옵션)
)

echo.
echo ===================================================
echo  완료! 아래 상태를 확인하세요:
echo ===================================================
schtasks /Query /TN "\GetDayTrends" /FO CSV /NH
schtasks /Query /TN "\CostDashboard" /FO CSV /NH
echo.
pause
