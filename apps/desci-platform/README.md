# DSCI-DecentBio

DSCI-DecentBio는 연구자와 투자자/펀더를 연결하는 DeSci 제품입니다. 연구자는 논문과 기술 자산을 등록하고, 플랫폼은 공고 수집, 벡터 매칭, AI 제안서 초안, 투자자 적합도, 리뷰/보상 흐름을 한 화면에서 운영합니다.

## 제품 흐름

- Research Submission: PDF 논문과 초록을 등록하고 IPFS/벡터 인덱싱 흐름을 시작합니다.
- Funding Radar: KDDF/NTIS 등 연구지원 공고를 수집하고 검색합니다.
- Match Studio: 논문과 공고를 매칭하고 AI 제안서 초안을 생성합니다.
- Investor View: VC 관점에서 연구 자산과 투자 적합도를 확인합니다.
- Research Vault: 제출한 논문과 IP-NFT 민팅 상태를 관리합니다.
- Governance Hub: 제안, 투표, 실행 상태를 추적합니다.
- Product Readiness: `/ready` API와 대시보드 패널로 출시 준비도를 점검합니다.

## 기술 스택

- Frontend: React, Vite, TypeScript baseline, TanStack Query, Fetch API
- Backend: FastAPI, async job runner, RabbitMQ worker option
- Data: PostgreSQL/Supabase migration, Redis usage/job state fallback
- Search: local vector store or Qdrant-compatible boundary
- Storage/Web3: IPFS/Pinata, Web3 mock or contract integration
- Mobile direction: Flutter/native 클라이언트가 REST/SSE API를 재사용할 수 있는 구조

상세 스택 정렬 기록은 [STACK_ALIGNMENT.md](./STACK_ALIGNMENT.md)를 확인하세요.

## 빠른 실행

### 인프라 포함 실행

```bash
cd apps/desci-platform
docker compose --profile infra up postgres redis rabbitmq biolinker-worker
```

### 백엔드

```bash
cd apps/desci-platform/biolinker
uv sync --extra dev
uv run uvicorn main:app --reload
```

### 프론트엔드

```bash
cd apps/desci-platform/frontend
npm install
npm run dev
```

## 주요 API

- `GET /health`: 하위 시스템 헬스 체크
- `GET /ready`: 제품 출시 준비도 체크
- `GET /jobs/{job_id}`: 장기 작업 상태 조회
- `GET /jobs/{job_id}/events`: 장기 작업 SSE 진행률 스트림
- `POST /jobs/notices/collect`: 공고 수집 작업 생성
- `POST /jobs/papers/index`: 논문 재인덱싱 작업 생성
- `POST /jobs/match/paper`: 논문-공고 매칭 작업 생성
- `POST /jobs/proposal/generate`: 제안서 생성 작업 생성

## 환경 변수

시작점은 `.env.example`과 `biolinker/.env.example`입니다. 제품형 실행에는 최소 하나의 LLM 키와 인증 설정이 필요합니다.

- `GOOGLE_API_KEY` 또는 `GEMINI_API_KEY` 또는 `OPENAI_API_KEY`
- `GOOGLE_APPLICATION_CREDENTIALS` 또는 Firebase 서비스 계정 설정
- `DATABASE_URL` 또는 Supabase 관련 키
- `REDIS_URL`
- `RABBITMQ_URL`
- `PINATA_JWT` 또는 Pinata API 키

개발 환경에서는 일부 서비스가 fallback으로 동작하지만, 대시보드의 Product Readiness 패널에서 출시 차단 항목을 확인할 수 있습니다.

## 품질 게이트

### 백엔드

```bash
cd apps/desci-platform/biolinker
uv run pytest tests/test_api_endpoints.py tests/test_jobs.py -q
```

### 프론트엔드

```bash
cd apps/desci-platform/frontend
npm run lint
npm run typecheck
npm run test
npm run build:lts
npm run check:bundle
```

### Compose 검증

```bash
cd apps/desci-platform
docker compose config --quiet
```

### 제품 스모크 체크

프론트엔드와 백엔드가 떠 있는 상태에서 실제 URL 기준으로 API, `/health`, `/ready`, 프론트 첫 화면을 확인합니다.

```bash
cd apps/desci-platform
python scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173
```

운영 배포 직전에는 readiness가 `blocked`이면 실패하도록 더 엄격하게 실행합니다.

```bash
python scripts/product_smoke.py --strict-ready
```

브라우저에서 실제 JS 라우팅과 콘솔 오류까지 확인하려면 프론트엔드가 실행 중인 상태에서 다음을 실행합니다.

```bash
python scripts/browser_smoke.py --frontend http://127.0.0.1:5173
```

## 운영 메모

- 프론트엔드는 장기 작업에 대해 EventSource 기반 SSE를 우선 사용하고, 미지원 환경에서는 폴링으로 fallback합니다.
- Redis/RabbitMQ/PostgreSQL/Supabase는 제품형 운영에서 권장됩니다.
- `/ready`의 `status`가 `blocked`이면 공개 데모 또는 운영 배포 전에 필수 항목을 먼저 해결해야 합니다.
- 모든 API 응답에는 `X-Request-ID`가 포함됩니다. 고객 문의나 장애 분석 시 이 값을 로그 추적 키로 사용하세요.
