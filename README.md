# BIOJUHO-Projects

DeSci(Decentralized Science) 및 AI 통합 도구 모노레포

## Projects

| # | Project | Description | Tech Stack |
|---|---------|-------------|------------|
| 1 | [desci-platform](#1-desci-platform) | 탈중앙화 과학 플랫폼 (BioLinker) | FastAPI, React, Solidity, Firebase |
| 2 | [MCP_notion-antigravity](#2-mcp_notion-antigravity) | Notion 연동 MCP 서버 | Python, Notion API, Gemini AI |
| 3 | [notebooklm-mcp](#3-notebooklm-mcp) | NotebookLM 연동 MCP 서버 | Python, Google Cloud |
| 4 | [github-mcp](#4-github-mcp) | GitHub 연동 MCP 서버 | Node.js, GitHub API |

---

### 1. desci-platform

탈중앙화 과학(DeSci) 플랫폼. 연구 과제 매칭(BioLinker), IPFS 기반 논문 저장, 블록체인 토큰 보상 시스템을 결합한 연구자용 서비스.

**구조:**
```
desci-platform/
├── backend/       # FastAPI + Firebase Auth
├── frontend/      # React (Vite) + Tailwind CSS
├── biolinker/     # AI 연구과제 매칭 엔진
│   └── services/  # 크롤러(KDDF, NTIS), 벡터검색, IPFS, Web3
└── contracts/     # DeSciToken (ERC20, Sepolia)
```

**주요 기능:** Google/Email 인증 | 논문 IPFS 업로드 | 토큰 보상 | AI 과제 매칭

**실행:**
```bash
# Backend
cd desci-platform/backend && pip install -r requirements.txt && uvicorn main:app --reload

# Frontend
cd desci-platform/frontend && npm install && npm run dev
```

---

### 2. MCP_notion-antigravity

AI 모델(Antigravity/Gemini)이 Notion 페이지를 검색하고 읽을 수 있도록 하는 MCP 서버. 뉴스 수집, 트렌드 분석, 시각화 등 자동화 스크립트 포함.

**구조:**
```
MCP_notion-antigravity/
├── server.py              # MCP 서버 (search_notion, read_page)
├── scripts/               # 자동화 스크립트 (15+)
│   ├── news_bot.py        # RSS 뉴스 수집 + AI 요약
│   ├── brain_module.py    # 다중 기사 인사이트 종합
│   ├── trend_analyzer.py  # 트렌드 분석
│   ├── visualization.py   # 차트 생성
│   └── ...
└── config/                # 뉴스 소스, 대시보드 설정
```

**주요 기능:** Notion 검색/읽기 | AI 뉴스 요약 | 시장 데이터 분석 | 자동 로깅

**실행:**
```bash
cd MCP_notion-antigravity
pip install -r requirements.txt
./run_server.sh
```

---

### 3. notebooklm-mcp

Google NotebookLM과 AI 어시스턴트를 연동하는 MCP 서버. 문서 분석 및 지식 종합 기능 제공.

**구조:**
```
notebooklm-mcp/
├── requirements.txt                # 의존성
├── scripts/list_notebooks.py       # 노트북 목록 조회
├── tests/                          # 성능 테스트
├── install.bat                     # 설치
├── authenticate_notebooklm.bat     # Google 인증
└── run_notebooklm.bat              # 서버 실행
```

**주요 기능:** NotebookLM 노트북 접근 | Google OAuth 인증 | 문서 분석

**실행:**
```bash
cd notebooklm-mcp
install.bat              # 설치
authenticate_notebooklm.bat  # 인증
run_notebooklm.bat           # 실행
```

---

### 4. github-mcp

GitHub과 AI 모델을 연동하는 MCP 서버. 리포지토리, 이슈, PR 등을 AI를 통해 관리.

**구조:**
```
github-mcp/
├── package.json          # @modelcontextprotocol/server-github
├── create_repo.json      # 리포 생성 템플릿
├── scripts/fetch_info.py # GitHub 정보 조회
├── run_github_mcp.bat    # 서버 실행
└── daily_backup.bat      # 일일 백업
```

**주요 기능:** 리포지토리 관리 | 이슈/PR 생성 | 파일 읽기/쓰기 | 브랜치 관리

**실행:**
```bash
cd github-mcp
npx -y @modelcontextprotocol/server-github
```

---

## Requirements

- Python 3.10+
- Node.js 18+
- 각 프로젝트별 `.env` 파일 설정 필요 (API 키, 인증 정보)

## Authors

Built by Raph & JuPark
