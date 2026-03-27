@echo off
echo [INFO] Antigravity NotebookLM MCP 설치를 시작합니다...
echo [STEP 1] 가상환경(venv) 생성 중...
python -m venv venv

echo [STEP 2] 필수 라이브러리 설치 중...
venv\Scripts\pip install -r requirements.txt

echo [SUCCESS] 설치가 완료되었습니다! 
echo [주의] credentials.json 파일을 폴더에 넣고 'authenticate_notebooklm.bat'로 인증해주세요.
pause
