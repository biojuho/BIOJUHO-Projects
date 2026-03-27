# notebooklm-automation

Unified NotebookLM automation package — content pipeline, extractors, alerts, and publishers.

## Quick Start

```bash
# Install (core)
pip install -e .

# Install with extractors
pip install -e ".[extraction,ocr,slides]"

# Run the API server
notebooklm-api              # → http://localhost:8788
```

## Content Pipeline

Google Drive → 텍스트 추출 → AI 아티클 → Notion 자동 발행

```bash
# PDF → Notion  
curl -X POST http://localhost:8788/pipeline/drive-to-notion \
  -H "Content-Type: application/json" \
  -d '{"file_url": "https://drive.google.com/...", "file_type": "pdf", "project": "MyProject"}'

# 실행 이력 조회
curl http://localhost:8788/pipeline/runs

# 일별 통계
curl http://localhost:8788/pipeline/stats
```

## Architecture

```
notebooklm_automation/
├── api.py              — FastAPI 서버 (pipeline + dashboard + auth)
├── bridge.py           — NotebookLM 코어 (노트북, 콘텐츠 팩토리, 리서치)
├── health.py           — 인증 모니터링, 자동 갱신
├── config.py           — 환경변수 설정
├── alerts.py           — Slack/Discord/Email 다채널 알림
├── execution_log.py    — SQLite 실행 로그 + 일별 통계
├── extractors/
│   ├── pdf_extractor.py    — PyMuPDF + pdfplumber
│   ├── ocr_extractor.py    — Google Vision + Tesseract
│   └── slides_extractor.py — Slides API + python-pptx
├── templates/
│   ├── __init__.py     — 프로젝트별 YAML 프롬프트 매니저
│   └── _default.yaml   — 기본 톤/스타일/구조
├── publishers/
│   ├── notion.py       — 7속성 스키마 + Markdown→블록 + 첨부
│   └── twitter.py      — X API v2 자동 발행
└── adapters/
    ├── dailynews.py    — DailyNews 리서치 어댑터
    └── desci.py        — DeSci 논문 분석 어댑터
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/pipeline/drive-to-notion` | 통합 파이프라인 (추출→생성→발행) |
| `GET` | `/pipeline/runs` | 실행 이력 |
| `GET` | `/pipeline/stats` | 일별 통계 |
| `GET` | `/health` | 서비스 상태 |
| `POST` | `/content-factory` | 인포그래픽 + 보고서 + 트윗 |
| `POST` | `/publish-notion` | Notion 수동 발행 |
| `POST` | `/auth/refresh` | 인증 갱신 |

## Configuration

`.env` 파일 또는 환경변수 (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `NOTEBOOKLM_API_PORT` | 8788 | 서버 포트 |
| `NOTION_API_KEY` | — | Notion Integration Token |
| `NOTION_DATABASE_ID` | — | 대상 Notion DB ID |
| `SLACK_WEBHOOK_URL` | — | Slack 알림 Webhook |
| `GDRIVE_NOTEBOOKLM_FOLDER_ID` | — | Drive 감시 폴더 |

## n8n Workflow

`n8n_workflows/notebooklm_content_pipeline.json`을 n8n Cloud에 임포트:
- **Google Drive Trigger** — 새 파일 감지 시 자동 실행
- **Schedule Trigger** — 매일 오전 9시 KST
- **Webhook Trigger** — 수동 실행

## Testing

```bash
pytest tests/unit/ -v          # 38 unit tests
python tests/test_notion_direct.py  # E2E Notion 테스트
```
