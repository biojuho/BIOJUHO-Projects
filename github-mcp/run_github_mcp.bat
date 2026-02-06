@echo off
chcp 65001 >nul
echo [INFO] GitHub MCP 서버 실행 중...
set /p GITHUB_TOKEN=<.env
for /f "tokens=2 delims==" %%a in ('type .env ^| findstr GITHUB_PERSONAL_ACCESS_TOKEN') do set GITHUB_PERSONAL_ACCESS_TOKEN=%%a
npx -y @modelcontextprotocol/server-github
