# 🚀 온보딩 가이드 — AI Projects Workspace

새 팀원이 최대한 빠르게 프로젝트에 기여할 수 있도록 안내합니다.

---

## 1단계: 환경 설정 (30분)

### 필수 도구

| 도구 | 버전 | 설치 방법 |
|------|------|-----------|
| Python | 3.12~3.13 | python.org (3.14는 호환성 이슈) |
| Node.js | 22 LTS | nodejs.org |
| Git | 최신 | git-scm.com |
| Docker | 최신 | docker.com |
| gitleaks | 8.x | `winget install Gitleaks.Gitleaks` |

### 프로젝트 클론 & 환경변수

```bash
git clone <repo-url>
cd "AI 프로젝트"

# .env 파일 생성 (각 .env.example 참고)
copy .env.example .env
# 프로젝트별 .env도 설정
copy getdaytrends\.env.example getdaytrends\.env
copy desci-platform\frontend\.env.example desci-platform\frontend\.env
```

> ⚠️ `.env` 파일에 실제 API 키를 입력해야 합니다. 기존 팀원에게 공유받으세요.

### Pre-commit 훅 설치

```bash
pip install pre-commit
pre-commit install
```

---

## 2단계: 프로젝트 이해 (1시간)

### 읽어야 할 문서

1. **[CLAUDE.md](CLAUDE.md)** — 프로젝트 구조, 스택, 명령어 총정리
2. **[CONTRIBUTING.md](CONTRIBUTING.md)** — 기여 가이드
3. **[docs/adr/](docs/adr/)** — 기술 결정 기록 (왜 이렇게 했는지)
4. **[docs/runbook.md](docs/runbook.md)** — 운영 절차

### 프로젝트 맵

```
AI 프로젝트/
├── desci-platform/     # DeSci 플랫폼 (RFP 매칭 + NFT)
│   ├── biolinker/      #   → FastAPI 백엔드 (:8000)
│   ├── frontend/       #   → React 프론트엔드 (:5173)
│   └── contracts/      #   → Solidity 스마트 컨트랙트
├── AgriGuard/          # 농업 공급망 추적
│   ├── backend/        #   → FastAPI (:8002)
│   └── frontend/       #   → React (:5174)
├── getdaytrends/       # 트렌드 분석 → 자동 콘텐츠 생성
├── DailyNews/          # X Growth Engine → Notion 자동화
├── canva-mcp/          # Canva MCP 서버
├── github-mcp/         # GitHub MCP 서버
├── notebooklm-mcp/     # NotebookLM MCP 서버
└── shared/             # 공유 LLM/유틸리티 모듈
```

---

## 3단계: 실행 확인 (30분)

### 전체 헬스체크

```bash
python scripts/healthcheck.py
```

### 개별 프로젝트 실행

```bash
# DeSci Backend
cd desci-platform/biolinker
pip install -r requirements.txt
python -m uvicorn main:app --port 8000 --reload

# DeSci Frontend
cd desci-platform/frontend
npm install && npm run dev

# GetDayTrends (테스트 모드)
cd getdaytrends
python main.py --one-shot --dry-run --verbose
```

### 또는 Docker로 한 번에

```bash
docker compose -f docker-compose.dev.yml up
```

---

## 4단계: 기여 시작

### PR 프로세스

```
코드 작성 → git add → git commit → push dev → PR 생성
          ↓ (자동)        ↓ (자동)          ↓ (자동)
       pre-commit    gitleaks 스캔    CI 테스트 + QA 리뷰
```

1. `dev` 브랜치에서 작업 (main 직접 커밋 금지)
2. PR 생성 시 **체크리스트 자동 적용** (`.github/pull_request_template.md`)
3. CI 통과 + 코드 리뷰 승인 후 머지

### 커밋 메시지 규칙

```
[프로젝트명] 변경 내용 요약
```

예시: `[GetDayTrends] feat: 벨로시티 스코어링 추가`

---

## 도움이 필요할 때

- **기술 결정 근거**: `docs/adr/` 디렉터리 확인
- **장애 대응**: `docs/runbook.md` 참고
- **성과 지표**: `python scripts/dora_metrics.py --days 30`
