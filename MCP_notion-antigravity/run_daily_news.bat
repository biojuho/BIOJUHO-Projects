@echo off
REM Antigravity Daily News Runner
REM 매일 오전 7시 Windows Task Scheduler로 실행

cd /d "D:\AI 프로젝트\MCP_notion-antigravity"
call venv\Scripts\activate.bat
REM 1. Notion News Archive 수집
python scripts\collect_news.py

REM 2. 데이터 시각화 생성
python scripts\visualization.py

REM 3. GitHub에 이미지 업로드 (자동 커밋/푸시)
git add output\*.png
git commit -m "Auto-update visualization charts [%date% %time%]"
git push origin main


REM 4. 노션 데일리 뉴스 요약 리포트 (시각화 포함)
python scripts\news_bot.py

REM 5. NotebookLM용 마크다운 아카이브 생성
python scripts\export_to_notebooklm.py

REM 6. Notion 뉴스룸 대시보드 업데이트
python scripts\update_dashboard.py

REM 로그 저장
echo [%date% %time%] Daily news completed >> logs\scheduler.log
