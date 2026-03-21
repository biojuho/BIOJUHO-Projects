@echo off
:: GetDayTrends 스케줄러 재등록 스크립트
:: 관리자 권한으로 실행 필요: 우클릭 → "관리자 권한으로 실행"

echo ===== GetDayTrends 스케줄러 재등록 =====
echo.

:: 1. 기존 작업 삭제
echo [1/3] 기존 작업 삭제 중...
schtasks /delete /tn "GetDayTrends" /f 2>nul
echo.

:: 2. 3시간 간격 재등록
echo [2/3] 3시간 간격 작업 생성 중...
schtasks /create ^
  /tn "GetDayTrends" ^
  /tr "d:\AI 프로젝트\getdaytrends\run_getdaytrends.bat" ^
  /sc HOURLY ^
  /mo 3 ^
  /st 09:00 ^
  /rl HIGHEST ^
  /f

if %errorlevel% neq 0 (
    echo [오류] 작업 생성 실패! 관리자 권한으로 실행하세요.
    pause
    exit /b 1
)
echo.

:: 3. 배터리 패치 (배터리 모드에서도 실행)
echo [3/3] 배터리 패치 적용 중...
powershell -Command "$xml = [xml](schtasks /query /tn 'GetDayTrends' /xml ONE); if ($xml) { $ns = @{t='http://schemas.microsoft.com/windows/2004/02/mit/task'}; $settings = $xml.SelectSingleNode('//t:Settings', [System.Xml.XmlNamespaceManager]::new($xml.NameTable)); $ns2 = [System.Xml.XmlNamespaceManager]::new($xml.NameTable); $ns2.AddNamespace('t','http://schemas.microsoft.com/windows/2004/02/mit/task'); $disallow = $xml.SelectSingleNode('//t:DisallowStartIfOnBatteries', $ns2); if ($disallow) {$disallow.InnerText='false'}; $stop = $xml.SelectSingleNode('//t:StopIfGoingOnBatteries', $ns2); if ($stop) {$stop.InnerText='false'}; $tmpFile = [System.IO.Path]::GetTempFileName(); $xml.Save($tmpFile); schtasks /create /tn 'GetDayTrends' /xml $tmpFile /f; Remove-Item $tmpFile }"
echo.

:: 확인
echo ===== 등록 확인 =====
schtasks /query /tn "GetDayTrends" /v /fo LIST | findstr /i "작업 이름 다음 실행 시간 반복"
echo.
echo 완료! 3시간 간격 + 배터리 패치 적용됨.
pause
