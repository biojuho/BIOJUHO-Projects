@echo off
chcp 65001 >nul
echo ===== 프로젝트 자동 백업 =====
echo 현재 시간: %date% %time%

cd /d "D:\AI 프로젝트"

echo [1/4] Git 상태 확인...
git status

echo [2/4] 변경 파일 스테이징...
git add .

echo [3/4] 커밋 생성...
for /f "tokens=1-3 delims=/" %%a in ("%date%") do set today=%%c-%%a-%%b
git commit -m "Daily backup %today%"

echo [4/4] GitHub에 푸시...
git push origin main

echo ===== 백업 완료! =====
pause
