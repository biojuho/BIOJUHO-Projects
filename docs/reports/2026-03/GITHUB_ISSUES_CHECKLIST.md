# GitHub Issues Checklist - System Audit Follow-up

**Generated**: 2026-03-22
**Source**: [SYSTEM_AUDIT_ACTION_PLAN.md](SYSTEM_AUDIT_ACTION_PLAN.md)

이 체크리스트는 시스템 감사 결과를 바탕으로 생성된 GitHub Issues 템플릿입니다.

---

## 🚨 Critical Priority (이번 주 완료 필수)

### Issue #1: Enable GitHub Security Features
**Labels**: `security`, `critical`, `devops`
**Assignee**: DevOps Lead

**Description**:
GitHub의 기본 보안 기능을 활성화하여 시크릿 노출 및 의존성 취약점을 자동 감지합니다.

**Tasks**:
- [ ] GitHub Secret Scanning 활성화
- [ ] Push Protection 활성화 (시크릿 푸시 차단)
- [ ] Dependabot alerts 활성화
- [ ] Dependabot security updates 활성화
- [ ] Dependency Review 활성화 (PR 체크)
- [ ] CodeQL 정적 분석 설정 (Python, JavaScript, TypeScript)

**Acceptance Criteria**:
- Secret scanning이 활성화되어 기존 히스토리 스캔 완료
- 새로운 시크릿 푸시 시 자동 차단 확인
- Dependabot이 주간 업데이트 PR 생성 확인
- CodeQL이 PR마다 실행되어 결과 리포트 확인

**References**:
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
- [Push Protection](https://docs.github.com/en/code-security/secret-scanning/push-protection-for-repositories-and-organizations)

---

### Issue #2: Remove Deprecated Gemini 2.0 Flash Model
**Labels**: `technical-debt`, `high-priority`, `backend`
**Assignee**: Backend Lead

**Description**:
Gemini 2.0 Flash 모델이 2026-06-01에 종료 예정입니다. 레거시 폴백 체인에서 제거 필요.

**Current Usage** (from cost report):
- 호출 횟수: 2,502회 (30일)
- 비용: $0.00 (Free tier)
- 위치:
  - `shared/llm/config.py` (line 50, 58)
  - `agents/trend_analyzer.py` (line 65)

**Tasks**:
- [ ] `shared/llm/config.py`에서 `gemini-2.0-flash` 제거
- [ ] `agents/trend_analyzer.py` 기본 모델을 `gemini-2.5-flash-lite`로 변경
- [ ] 테스트 파일 업데이트 (`tests/test_shared_llm.py`, `tests/test_llm_enhancements.py`)
- [ ] 변경 사항 테스트 (단위 테스트 + 통합 테스트)
- [ ] 문서 업데이트 (SYSTEM_AUDIT_ACTION_PLAN.md)

**Migration Path**:
```python
# Before
TIER_CHAINS = {
    TaskTier.MEDIUM: [
        ("gemini", "gemini-2.5-flash-lite"),
        ("gemini", "gemini-2.0-flash"),  # ❌ Remove
        ...
    ]
}

# After
TIER_CHAINS = {
    TaskTier.MEDIUM: [
        ("gemini", "gemini-2.5-flash-lite"),
        ("gemini", "gemini-2.5-flash"),  # ✅ Use 2.5 instead
        ...
    ]
}
```

**Acceptance Criteria**:
- `gemini-2.0-flash` 문자열이 코드베이스에서 테스트 파일 외에는 존재하지 않음
- 모든 테스트 통과
- 비용 리포트에서 2.0 Flash 호출이 0으로 확인됨

---

### Issue #3: Add Gitleaks Pre-commit Hook
**Labels**: `security`, `high-priority`, `devops`
**Assignee**: DevOps Lead

**Description**:
로컬 커밋 단계에서 시크릿 노출을 방지하기 위해 Gitleaks pre-commit hook을 추가합니다.

**Tasks**:
- [ ] `.pre-commit-config.yaml` 파일 생성
- [ ] Gitleaks hook 추가
- [ ] `scripts/check_security.py` hook 통합
- [ ] Python/JS 린터 hook 추가 (Ruff, ESLint)
- [ ] 팀원들에게 설치 가이드 공유
- [ ] CI에서도 동일 체크 실행 (우회 방지)

**Configuration**:
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks

  - repo: local
    hooks:
      - id: check-security
        name: Custom Security Scanner
        entry: python scripts/check_security.py
        language: system
        pass_filenames: false

      - id: ruff
        name: Ruff Linter
        entry: ruff check --fix
        language: system
        types: [python]

      - id: ruff-format
        name: Ruff Formatter
        entry: ruff format
        language: system
        types: [python]
```

**Acceptance Criteria**:
- 시크릿이 포함된 커밋 시도 시 pre-commit이 차단
- CI에서 동일 검사 실행 확인
- 팀원 3명 이상이 설치 및 테스트 완료

**References**:
- [Gitleaks](https://github.com/gitleaks/gitleaks)
- [pre-commit](https://pre-commit.com/)

---

## 🔥 High Priority (2주 내 완료)

### Issue #4: Migrate AgriGuard from SQLite to PostgreSQL
**Labels**: `enhancement`, `high-priority`, `backend`, `database`
**Assignee**: Backend Lead

**Description**:
AgriGuard의 SQLite는 동시성 문제로 프로덕션 환경에서 적합하지 않습니다. PostgreSQL로 마이그레이션합니다.

**Current State**:
- Database: SQLite (`agriguard.db`)
- ORM: SQLAlchemy
- Port: 8002

**Tasks**:
- [ ] PostgreSQL Docker Compose 설정 추가
- [ ] Alembic 마이그레이션 도구 설정
- [ ] 초기 스키마 마이그레이션 스크립트 작성
- [ ] SQLAlchemy connection string 환경 변수화
- [ ] 데이터 마이그레이션 스크립트 작성
- [ ] 로컬 테스트 (Docker Compose 환경)
- [ ] 성능 벤치마크 (SQLite vs PostgreSQL)
- [ ] 롤백 계획 수립
- [ ] 문서 업데이트 (CLAUDE.md)

**Environment Variables**:
```env
# Before
DATABASE_URL=sqlite:///./agriguard.db

# After
DATABASE_URL=postgresql://user:password@localhost:5432/agriguard
```

**Docker Compose**:
```yaml
services:
  agriguard-db:
    image: postgres:16
    environment:
      POSTGRES_USER: agriguard
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: agriguard
    ports:
      - "5432:5432"
    volumes:
      - agriguard-data:/var/lib/postgresql/data
```

**Acceptance Criteria**:
- PostgreSQL 환경에서 모든 API 테스트 통과
- 동시 쓰기 테스트 (10+ concurrent writes) 성공
- 데이터 마이그레이션 스크립트 실행 후 데이터 무결성 확인
- 롤백 가능 확인

**Estimated Effort**: 3-5 days

---

### Issue #5: Standardize Python/Node.js Runtime Versions
**Labels**: `devops`, `high-priority`, `infrastructure`
**Assignee**: DevOps Lead

**Description**:
현재 Python 3.14.2와 Node.js v24.13.0을 사용 중이나, CLAUDE.md는 Python 3.12/3.13을 명시합니다. 런타임 기준을 통일합니다.

**Current State**:
- **Python**: 3.14.2 (로컬), CLAUDE.md 권장: 3.12/3.13
- **Node.js**: v24.13.0 (Hardhat 2.x는 Node 18+ 요구)
- **Issue**: Vite 7 + Hardhat 3는 Node 22.12+ 필요 (현재 Hardhat 2.x 사용)

**Tasks**:
- [ ] Python 버전 결정:
  - Option A: 3.13 기준선 + 3.14 canary CI
  - Option B: 3.12 유지 (langchain 호환성 우선)
- [ ] Node.js 버전 결정:
  - Option A: Node 22.12+ (Vite 7/Hardhat 3 대비)
  - Option B: Node 18 LTS (현재 Hardhat 2.x 유지)
- [ ] `.python-version` 파일 추가 (pyenv 호환)
- [ ] `.nvmrc` 파일 추가 (nvm 호환)
- [ ] CI/CD에서 버전 강제 (GitHub Actions matrix)
- [ ] CLAUDE.md 업데이트
- [ ] 팀 공지 및 로컬 환경 마이그레이션 가이드

**Recommendation**:
- **Python**: 3.13 기준선 (langchain이 3.13 지원 확인됨)
- **Node.js**: 22.12+ (향후 Vite 7/Hardhat 3 업그레이드 대비)

**Files to Create**:
```
# .python-version
3.13.3

# .nvmrc
22.12.0
```

**GitHub Actions**:
```yaml
jobs:
  test-python:
    strategy:
      matrix:
        python-version: ['3.13', '3.14']  # 3.14 canary
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

  test-node:
    strategy:
      matrix:
        node-version: ['22.12']
    steps:
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
```

**Acceptance Criteria**:
- `.python-version`과 `.nvmrc` 파일이 커밋됨
- CI가 지정된 버전으로 실행됨
- CLAUDE.md가 업데이트됨
- 팀원 3명 이상이 로컬 환경 업데이트 완료

---

### Issue #6: Implement OpenAI/Gemini Batch API
**Labels**: `enhancement`, `cost-optimization`, `backend`
**Assignee**: Backend Lead

**Description**:
OpenAI와 Gemini Batch API를 통합하여 비동기 작업의 비용을 50% 절감합니다.

**Current Cost** (30일):
- Total: $4.06
- Claude Sonnet 4: $3.80 (94%)
- DeepSeek: $0.18 (4%)
- Others: $0.08 (2%)

**Potential Savings**:
- OpenAI Batch: 50% off (입력/출력 모두)
- Gemini Batch: 50% off (입력/출력 모두)
- **예상 절감**: $1.90~$2.00/월 (백그라운드 작업 50% 가정)

**Tasks**:
- [ ] OpenAI Batch API 클라이언트 구현
- [ ] Gemini Batch API 클라이언트 구현
- [ ] `shared/llm/` 모듈에 Batch 모드 추가
- [ ] 비동기 작업 식별 (DailyNews 콘텐츠 생성, 벡터 임베딩 등)
- [ ] Batch 작업 큐잉 로직 구현
- [ ] Batch 결과 폴링 및 재시도 로직
- [ ] 비용 추적 업데이트 (`cost_intelligence.py`)
- [ ] 통합 테스트
- [ ] 1주일 A/B 테스트 (Batch vs 실시간)

**API References**:
- [OpenAI Batch API](https://platform.openai.com/docs/guides/batch)
- [Gemini Batch API](https://ai.google.dev/gemini-api/docs/batch)

**Implementation Example**:
```python
# shared/llm/batch.py
class BatchClient:
    async def submit_batch(self, requests: list[dict]) -> str:
        """Submit batch job, returns batch_id"""
        pass

    async def check_batch(self, batch_id: str) -> dict:
        """Check batch status"""
        pass

    async def retrieve_batch(self, batch_id: str) -> list[dict]:
        """Retrieve completed batch results"""
        pass
```

**Acceptance Criteria**:
- Batch API 호출이 실시간 API보다 50% 저렴함을 확인
- 1주일 테스트 기간 동안 오류율 < 5%
- `cost_intelligence.py` 리포트에 Batch 비용 별도 표시
- 문서화 (API 사용법, 비용 비교)

**Estimated Effort**: 5-7 days

---

## 📊 Medium Priority (1개월 내)

### Issue #7: Set Up CI/CD Pipeline
**Labels**: `devops`, `infrastructure`, `ci-cd`
**Assignee**: DevOps Lead

**Description**:
GitHub Actions를 통한 기본 CI/CD 파이프라인을 구축합니다.

**Pipeline Stages**:
1. **Lint**: Ruff (Python), ESLint (JS/TS), Solidity linter
2. **Test**: pytest, Vitest, Hardhat test
3. **Security**: CodeQL, Dependency Review, Gitleaks
4. **Build**: Docker images
5. **Deploy**: (스테이징 환경 준비 후)

**Tasks**:
- [ ] `.github/workflows/ci.yml` 생성
- [ ] Python 프로젝트 CI (lint + test)
- [ ] Node.js 프로젝트 CI (lint + test + build)
- [ ] Solidity 프로젝트 CI (compile + test)
- [ ] Security 스캔 통합
- [ ] Docker 이미지 빌드 및 push (GHCR)
- [ ] Path-based filtering (변경된 프로젝트만 빌드)
- [ ] Matrix strategy (Python 3.13/3.14, Node 22)
- [ ] 캐싱 최적화 (pip, npm, Hardhat)

**Example Workflow**:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - uses: astral-sh/setup-uv@v5
      - run: uv pip install ruff
      - run: ruff check .
      - run: ruff format --check .

  test-python:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.13', '3.14']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements.txt
      - run: pytest --cov --cov-report=xml
      - uses: codecov/codecov-action@v4

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          languages: python, javascript
      - uses: github/codeql-action/analyze@v3
```

**Acceptance Criteria**:
- PR마다 자동으로 CI 실행
- 모든 스테이지 통과 시 merge 가능
- 실행 시간 < 10분 (캐싱 최적화 후)
- 팀원들이 CI 결과를 PR에서 확인 가능

**Estimated Effort**: 3-5 days

---

### Issue #8: Add pytest Coverage Reporting
**Labels**: `testing`, `quality`, `backend`
**Assignee**: Backend Lead

**Description**:
pytest 커버리지 측정 및 리포팅을 설정하여 테스트 품질을 모니터링합니다.

**Current State**:
- 테스트 커버리지: 미측정
- 일부 단위 테스트 존재 (`DailyNews/tests/unit/`)

**Target**:
- **1개월**: 50% 커버리지
- **3개월**: 70% 커버리지

**Tasks**:
- [ ] `pytest-cov` 의존성 추가
- [ ] `pytest.ini` 또는 `pyproject.toml`에 커버리지 설정
- [ ] CI에 커버리지 리포트 추가
- [ ] Codecov 또는 Coveralls 연동
- [ ] PR에 커버리지 변화 코멘트 자동 추가
- [ ] 프로젝트별 커버리지 목표 설정
- [ ] 미커버 코드 우선순위 분석

**Configuration**:
```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "--cov=shared",
    "--cov=DailyNews/src",
    "--cov=desci-platform/biolinker",
    "--cov=AgriGuard/backend",
    "--cov-report=term-missing",
    "--cov-report=xml",
    "--cov-fail-under=50",
]
```

**Acceptance Criteria**:
- CI에서 커버리지 리포트 생성 확인
- Codecov 대시보드에서 프로젝트별 커버리지 확인
- PR에 커버리지 변화 표시
- 커버리지 < 50% 시 CI 실패

---

### Issue #9: Migrate to Qdrant Vector Database (POC)
**Labels**: `research`, `performance`, `backend`
**Assignee**: Backend Lead

**Description**:
biolinker의 ChromaDB를 Qdrant로 마이그레이션하여 프로덕션 확장성을 확보합니다.

**Current State**:
- Vector DB: ChromaDB (PersistentClient, 로컬 모드)
- Use case: RFP 문서 벡터 검색

**Qdrant Advantages**:
- 클라우드 네이티브 (샤드 이동, 리샤딩)
- 멀티 테넌시 지원
- 고급 필터링 (metadata + 벡터 하이브리드)
- gRPC 지원 (낮은 지연시간)

**Tasks**:
- [ ] Qdrant Docker Compose 설정
- [ ] Qdrant Python 클라이언트 설치
- [ ] ChromaDB → Qdrant 마이그레이션 스크립트
- [ ] API 호환 레이어 구현 (`vector_store.py` 리팩토링)
- [ ] 성능 벤치마크 (검색 속도, 인덱싱 속도)
- [ ] 동시성 테스트 (100+ concurrent queries)
- [ ] 비용 분석 (Qdrant Cloud vs self-hosted)
- [ ] 롤백 계획

**Benchmark Metrics**:
- 검색 지연시간 (p50, p95, p99)
- 인덱싱 처리량 (docs/sec)
- 메모리 사용량
- 동시 쿼리 처리 능력

**Acceptance Criteria**:
- POC 환경에서 기존 기능 100% 동작
- 검색 지연시간 p95 < 200ms
- 벤치마크 리포트 작성
- Go/No-Go 결정 (마이그레이션 여부)

**Estimated Effort**: 5-7 days (POC)

---

### Issue #10: Docker Compose Multi-Service Setup
**Labels**: `devops`, `infrastructure`, `docker`
**Assignee**: DevOps Lead

**Description**:
전체 워크스페이스를 `docker compose up`으로 실행 가능하도록 통합 설정을 만듭니다.

**Services**:
- `biolinker` (FastAPI, port 8000)
- `agriguard-backend` (FastAPI, port 8002)
- `desci-frontend` (React + Vite, port 5173)
- `postgres` (AgriGuard DB, port 5432)
- `qdrant` (Vector DB, port 6333) - POC 후
- `redis` (캐싱, port 6379) - 향후

**Tasks**:
- [ ] 루트에 `docker-compose.yml` 생성
- [ ] 각 서비스별 `Dockerfile` 생성
- [ ] 환경 변수 통합 (`.env.docker`)
- [ ] 네트워크 설정 (서비스 간 통신)
- [ ] 볼륨 설정 (데이터 영속성)
- [ ] Health check 추가
- [ ] 로컬 테스트 (전체 스택 시작)
- [ ] README 업데이트 (Quick Start)

**Example `docker-compose.yml`**:
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: agriguard
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: agriguard
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "agriguard"]
      interval: 5s

  biolinker:
    build: ./desci-platform/biolinker
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: ${BIOLINKER_DB_URL}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy

  agriguard:
    build: ./AgriGuard/backend
    ports:
      - "8002:8002"
    environment:
      DATABASE_URL: postgresql://agriguard:${DB_PASSWORD}@postgres:5432/agriguard
    depends_on:
      postgres:
        condition: service_healthy

  frontend:
    build: ./desci-platform/frontend
    ports:
      - "5173:5173"
    environment:
      VITE_API_URL: http://localhost:8000

volumes:
  postgres-data:
```

**Acceptance Criteria**:
- `docker compose up`으로 전체 스택 시작 가능
- 모든 서비스 health check 통과
- 로컬 개발 환경 < 5분 셋업
- 팀원 3명 이상이 테스트 완료

**Estimated Effort**: 3-4 days

---

## 📝 Documentation & Cleanup

### Issue #11: Update CLAUDE.md with Latest Changes
**Labels**: `documentation`
**Assignee**: Tech Lead

**Description**:
최근 변경 사항을 반영하여 CLAUDE.md를 업데이트합니다.

**Tasks**:
- [ ] Python 버전 요구사항 업데이트
- [ ] Node.js 버전 요구사항 업데이트
- [ ] Gemini 2.0 Flash 제거 반영
- [ ] PostgreSQL 마이그레이션 반영
- [ ] Docker Compose 가이드 추가
- [ ] 비용 최적화 전략 추가
- [ ] Gotchas 섹션 업데이트

---

### Issue #12: Create Team Onboarding Guide
**Labels**: `documentation`, `team`
**Assignee**: Tech Lead

**Description**:
새 팀원이 1시간 내에 로컬 개발 환경을 셋업할 수 있도록 가이드를 작성합니다.

**Content**:
- 필수 도구 설치 (Python, Node.js, Docker)
- 환경 변수 설정
- Docker Compose 실행
- 첫 PR 제출 가이드
- 트러블슈팅 FAQ

---

## 📊 Metrics & Monitoring

### Issue #13: Set Up Sentry Error Tracking
**Labels**: `monitoring`, `infrastructure`
**Assignee**: DevOps Lead

**Description**:
Sentry를 통해 프론트엔드/백엔드 에러를 중앙에서 추적합니다.

**Tasks**:
- [ ] Sentry 프로젝트 생성 (5개)
- [ ] Python SDK 통합 (FastAPI)
- [ ] JavaScript SDK 통합 (React)
- [ ] 환경별 분리 (dev/staging/prod)
- [ ] 성능 모니터링 활성화
- [ ] 알림 채널 설정 (Slack/Telegram)

---

## 🎯 Summary

**Total Issues**: 13
- **Critical**: 3 issues
- **High**: 6 issues
- **Medium**: 4 issues

**Estimated Timeline**:
- **Week 1**: Issues #1, #2, #3 (보안 + deprecated 모델 제거)
- **Week 2**: Issues #4, #5, #6 (DB 마이그레이션 + 런타임 통일 + Batch API)
- **Week 3-4**: Issues #7, #8, #9, #10 (CI/CD + 커버리지 + Qdrant POC + Docker)
- **Ongoing**: Issues #11, #12, #13 (문서화 + 모니터링)

**Key Success Metrics**:
- [ ] 보안 스캔 100% 활성화 (Secret Scanning, Dependabot, CodeQL)
- [ ] Deprecated 모델 0개
- [ ] SQLite 의존성 0개 (AgriGuard → PostgreSQL)
- [ ] 런타임 버전 통일 (Python 3.13, Node 22.12+)
- [ ] LLM 비용 30% 절감 (Batch API + 캐싱)
- [ ] CI/CD 파이프라인 가동
- [ ] 테스트 커버리지 50%+

---

**Next Steps**:
1. GitHub Issues 탭에서 이 체크리스트를 기반으로 이슈 생성
2. 각 이슈에 담당자 배정
3. 주간 스프린트 계획에 포함
4. 진행 상황을 [SYSTEM_AUDIT_ACTION_PLAN.md](SYSTEM_AUDIT_ACTION_PLAN.md)의 KPI에 반영
