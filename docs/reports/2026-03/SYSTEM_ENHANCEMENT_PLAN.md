# 시스템 고도화 계획안 (System Enhancement Plan)

**프로젝트**: AI 프로젝트 워크스페이스
**작성일**: 2026-03-25
**버전**: 1.0
**소유자**: Backend Team / DevOps Team
**상태**: 승인됨 (Approved)

---

## 목차

1. [개요](#개요)
2. [현황 분석](#현황-분석)
3. [Phase 1: 인프라 안정화](#phase-1-인프라-안정화)
4. [Phase 2: 코드 품질 향상](#phase-2-코드-품질-향상)
5. [Phase 3: 모니터링 & 옵저버빌리티](#phase-3-모니터링--옵저버빌리티)
6. [Phase 4: AI/LLM 최적화](#phase-4-aillm-최적화)
7. [Phase 5: 보안 & 컴플라이언스](#phase-5-보안--컴플라이언스)
8. [Phase 6: 문서화 & 지식 관리](#phase-6-문서화--지식-관리)
9. [Phase 7: 배포 & 운영](#phase-7-배포--운영)
10. [성공 지표 (KPI)](#성공-지표-kpi)
11. [타임라인 & 리소스](#타임라인--리소스)
12. [리스크 관리](#리스크-관리)

---

## 개요

### 배경

현재 AI 프로젝트 워크스페이스는 7개의 주요 프로젝트(DeSci Platform, AgriGuard, GetDayTrends, DailyNews, 4개 MCP 서버)를 포함한 멀티 프로젝트 모노레포로 운영되고 있습니다. 각 프로젝트가 성공적으로 개발되었으나, 다음 단계로 도약하기 위해서는 체계적인 시스템 고도화가 필요합니다.

### 목표

1. **안정성 향상**: 프로덕션 환경에서 99.9% uptime 달성
2. **개발 생산성 증대**: CI/CD 파이프라인 최적화로 배포 주기 단축
3. **운영 비용 절감**: LLM 비용 최적화 및 인프라 효율화
4. **코드 품질 강화**: 테스트 커버리지 70% 이상 달성
5. **보안 강화**: 자동화된 보안 스캔 및 취약점 관리
6. **지식 체계화**: 완전한 문서화 및 온보딩 프로세스 구축

### 범위

- **포함**: 모든 서브 프로젝트, 공유 라이브러리 (`shared/`), 스크립트 (`scripts/`), CI/CD, 문서
- **제외**: 비즈니스 로직 변경, 새로운 기능 추가 (별도 로드맵 관리)

---

## 현황 분석

### 프로젝트 현황 (2026-03-25 기준)

| 프로젝트 | 상태 | 주요 이슈 | 우선순위 |
|---------|------|----------|---------|
| **desci-platform** | Production | React 19 + Vite 7 안정화 완료 | Medium |
| **AgriGuard** | Migration | PostgreSQL QC 4/5 (sensor_readings drift) | **High** |
| **GetDayTrends** | Refactored | 435 tests passed, modular architecture | Low |
| **DailyNews** | Production | Twice-daily automation running | Low |
| **MCP Servers** | Stable | 7개 도구, FastMCP 기반 | Medium |
| **Content Intelligence** | New | v2.0 완료 (31 tests passed) | Low |

### 기술 스택

**Backend:**
- Python 3.13 (standard), 3.14 (canary)
- FastAPI, SQLAlchemy, Pydantic
- PostgreSQL 16 (AgriGuard), SQLite (others)

**Frontend:**
- React 19, Vite 7, Tailwind CSS 4
- Node.js 22.12+

**Blockchain:**
- Hardhat, Solidity 0.8.20
- OpenZeppelin v5

**AI/LLM:**
- Gemini 2.5 Flash-Lite (primary)
- OpenAI GPT-4o, Claude 3.5 Sonnet (heavy tasks)
- ChromaDB (vector store)

**DevOps:**
- Docker, Docker Compose
- GitHub Actions (CI/CD)
- Pre-commit hooks (Gitleaks, Ruff)

### 현재 메트릭스

| 메트릭 | 현재 값 | 목표 |
|--------|---------|------|
| **테스트 커버리지** | 미측정 (일부 프로젝트만) | 70%+ |
| **CI/CD 성공률** | ~85% | 95%+ |
| **배포 주기** | 수동 (주 1-2회) | 자동화 (일 1회) |
| **평균 복구 시간 (MTTR)** | ~2시간 | 30분 |
| **LLM 비용/요청** | ~$0.03 | $0.02 |
| **문서 최신성** | 70% | 95%+ |
| **보안 스캔 통과율** | 100% (Gitleaks) | 100% (SAST+DAST) |

### 강점

- **모듈화된 아키텍처**: GetDayTrends 리팩토링 완료 (1,435줄 → 358줄)
- **자동화 인프라**: Pre-commit hooks, 워크스페이스 smoke tests
- **공유 라이브러리**: `shared/llm`, `shared/embeddings`, `shared/db`
- **문서화**: ADR, Runbook, Postmortem 템플릿 존재

### 약점

- **기술 부채**: 53개 파일에 TODO/FIXME (145개 에러 핸들링 검토 필요)
- **테스트 격차**: 커버리지 미측정, E2E 테스트 부족
- **모니터링 부재**: 수동 헬스체크, 실시간 알림 미구축
- **시크릿 관리**: .env 파일 평문 보관 (Vault 미도입)
- **배포 프로세스**: 수동 배포, 롤백 스크립트 미완성

---

## Phase 1: 인프라 안정화

**기간**: 1-2주
**우선순위**: **High**

### 1.1 AgriGuard PostgreSQL 마이그레이션 완료

**현재 상태:**
- QC 결과: 4/5 (sensor_readings drift 허용 범위 초과)
- PostgreSQL: 14,102 rows
- SQLite (archived): 14,696 rows
- SQLite (current): 14,782 rows

**작업 계획:**

1. **Drift 원인 분석**
   - 라이브 센서 데이터 유입 경로 추적
   - `AgriGuard/backend/main.py` API 엔드포인트 검토
   - 백그라운드 작업 (cron, scheduler) 확인

2. **데이터 Sync 전략**
   - Option A: PostgreSQL 실시간 동기화 (권장)
   - Option B: SQLite → PostgreSQL 재마이그레이션 (--truncate)
   - Option C: 라이브 데이터 허용 (tolerance 상향)

3. **QC 재실행 및 문서화**
   ```powershell
   $env:DATABASE_URL = "postgresql://agriguard:agriguard_secret@localhost:5432/agriguard"
   python AgriGuard/backend/scripts/qc_postgres_migration.py
   ```

4. **SQLite 아카이브**
   - QC 5/5 통과 후 `agriguard.db` → `agriguard.db.final_archive`
   - `.gitignore` 업데이트

**산출물:**
- `POSTGRES_MIGRATION_COMPLETE.md` (최종 리포트)
- `AgriGuard/backend/scripts/sync_sensor_data.py` (선택)

**성공 기준:**
- QC 5/5 통과
- 프로덕션 PostgreSQL 안정 운영 7일

---

### 1.2 Docker Compose 통합 개발 환경 강화

**현황:**
- `docker-compose.yml`, `docker-compose.dev.yml` 존재
- 일부 서비스만 정의됨

**작업 계획:**

1. **전체 서비스 통합**
   ```yaml
   # docker-compose.dev.yml 확장
   services:
     desci-biolinker:
       build: ./desci-platform/biolinker
       ports: ["8000:8000"]
       depends_on: [chroma, postgres]

     desci-frontend:
       build: ./desci-platform/frontend
       ports: ["5173:5173"]

     agriguard-backend:
       build: ./AgriGuard/backend
       ports: ["8002:8002"]
       depends_on: [agriguard-postgres]

     agriguard-postgres:
       image: postgres:16-alpine
       environment:
         POSTGRES_DB: agriguard
         POSTGRES_USER: agriguard
         POSTGRES_PASSWORD: ${AGRIGUARD_DB_PASSWORD}
       volumes: [agriguard-data:/var/lib/postgresql/data]
       healthcheck:
         test: ["CMD", "pg_isready", "-U", "agriguard"]

     chroma:
       image: chromadb/chroma:latest
       ports: ["8001:8000"]

     # GetDayTrends, DailyNews (선택적)

   volumes:
     agriguard-data:
   ```

2. **Health Check 강화**
   - 모든 서비스에 healthcheck 추가
   - Dependency 순서 명확화 (depends_on + condition: service_healthy)

3. **원클릭 스크립트**
   ```powershell
   # scripts/setup_dev_environment.ps1
   docker compose -f docker-compose.dev.yml up -d
   docker compose ps
   # 자동 seed data 실행
   ```

**산출물:**
- `docker-compose.dev.yml` (확장)
- `DOCKER_SETUP_GUIDE.md` (업데이트)
- `scripts/setup_dev_environment.ps1`

**성공 기준:**
- `docker compose up` 한 번에 전체 환경 구성
- 신규 팀원 30분 내 환경 구축 가능

---

### 1.3 CI/CD 파이프라인 최적화

**현황:**
- `security-quality-gate.yml` 존재
- 프로젝트별 개별 CI 워크플로우
- 성공률 ~85%

**작업 계획:**

1. **워크플로우 통합**
   ```yaml
   # .github/workflows/enhanced-ci.yml
   name: Enhanced CI/CD
   on: [push, pull_request]
   jobs:
     security:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - name: Gitleaks
           uses: gitleaks/gitleaks-action@v2
         - name: Bandit
           run: pip install bandit && bandit -r . -f json -o bandit-report.json

     test-python:
       needs: security
       strategy:
         matrix:
           project: [desci-platform/biolinker, AgriGuard/backend, getdaytrends, DailyNews]
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with: {python-version: '3.13'}
         - run: pip install -r ${{ matrix.project }}/requirements.txt
         - run: pytest ${{ matrix.project }}/tests --cov --cov-report=xml
         - uses: codecov/codecov-action@v4

     test-frontend:
       needs: security
       strategy:
         matrix:
           project: [desci-platform/frontend]
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-node@v4
           with: {node-version: '22'}
         - run: npm ci --prefix ${{ matrix.project }}
         - run: npm run test --prefix ${{ matrix.project }}
         - run: npm run lint --prefix ${{ matrix.project }}
         - run: npm run build:lts --prefix ${{ matrix.project }}

     quality-gate:
       needs: [test-python, test-frontend]
       runs-on: ubuntu-latest
       steps:
         - name: Check coverage threshold
           run: |
             if [ $(cat coverage.xml | grep line-rate | cut -d'"' -f2 | awk '{print $1*100}') -lt 70 ]; then
               echo "Coverage below 70%"
               exit 1
             fi
   ```

2. **병렬 실행 최적화**
   - Matrix strategy 활용
   - 캐싱 강화 (pip, npm, docker layer)

3. **PR 품질 게이트 강화**
   - Coverage threshold: 60% → 70%
   - Lint 실패 시 PR 차단
   - Required status checks 설정

**산출물:**
- `.github/workflows/enhanced-ci.yml`
- `docs/adr/0004-ci-cd-optimization.md`

**성공 기준:**
- CI 성공률 95% 이상
- 빌드 시간 15분 이내 (현재 ~25분)

---

## Phase 2: 코드 품질 향상

**기간**: 2-3주
**우선순위**: **High**

### 2.1 기술 부채 해소

**현황:**
- 53개 파일에 TODO/FIXME/HACK/XXX 존재
- 145개 에러 핸들링 코드 검토 필요

**작업 계획:**

1. **기술 부채 인벤토리 작성**
   ```bash
   # 자동 수집 스크립트
   python scripts/generate_tech_debt_inventory.py --output docs/TECH_DEBT_INVENTORY.md
   ```

2. **우선순위 분류**
   - P0: 보안/버그 (즉시 수정)
   - P1: 성능/안정성 (2주 내)
   - P2: 리팩토링 (1개월 내)
   - P3: 문서화 (백로그)

3. **GitHub Issues 자동 생성**
   ```python
   # scripts/create_tech_debt_issues.py
   # TODO 주석 → GitHub Issue 자동 생성 (label: tech-debt)
   ```

4. **주간 부채 상환 할당**
   - 매주 금요일 2시간 "Tech Debt Friday"
   - 월 10개 이상 해소 목표

**산출물:**
- `docs/TECH_DEBT_INVENTORY.md` (자동 생성)
- `docs/TECH_DEBT_RESOLUTION_REPORT.md` (월간 리포트)
- GitHub Issues with label `tech-debt`

**성공 기준:**
- TODO/FIXME 50% 감소 (53 → 26개)
- P0 항목 100% 해소

---

### 2.2 테스트 커버리지 확대

**목표 커버리지:**
- desci-platform/biolinker: 70%
- AgriGuard/backend: 65%
- GetDayTrends: 80% (리팩토링 완료)
- DailyNews: 60%

**작업 계획:**

1. **커버리지 측정 인프라**
   ```yaml
   # pytest.ini (각 프로젝트)
   [pytest]
   addopts = --cov=. --cov-report=html --cov-report=term --cov-fail-under=70
   ```

2. **미커버 영역 우선 순위화**
   ```bash
   pytest --cov --cov-report=html
   # htmlcov/index.html 에서 빨간색 영역 확인
   ```

3. **테스트 유형별 확대**
   - Unit tests: 비즈니스 로직
   - Integration tests: API 엔드포인트
   - E2E tests: 사용자 시나리오 (Playwright)

4. **E2E 테스트 시나리오 예시**
   ```typescript
   // desci-platform/frontend/e2e/upload-paper.spec.ts
   test('researcher can upload paper and get matched RFPs', async ({ page }) => {
     await page.goto('http://localhost:5173/my-lab');
     await page.click('button:has-text("Upload Paper")');
     await page.setInputFiles('input[type="file"]', 'fixtures/sample-paper.pdf');
     await page.fill('input[name="title"]', 'Novel AI Algorithm');
     await page.click('button:has-text("Submit")');
     await expect(page.locator('.matching-rfps')).toBeVisible();
     await expect(page.locator('.rfp-card')).toHaveCount(3);
   });
   ```

**산출물:**
- `tests/` 디렉토리 확장 (각 프로젝트)
- Coverage HTML 리포트 (CI artifact)
- `docs/TESTING_GUIDE.md`

**성공 기준:**
- 전 프로젝트 평균 커버리지 70% 달성
- E2E 테스트 10개 이상

---

### 2.3 타입 안전성 강화

**작업 계획:**

1. **Python: mypy strict mode**
   ```ini
   # mypy.ini (workspace root)
   [mypy]
   python_version = 3.13
   strict = True
   warn_return_any = True
   warn_unused_configs = True
   disallow_untyped_defs = True

   [mypy-third_party.*]
   ignore_missing_imports = True
   ```

2. **TypeScript: strict mode**
   ```json
   // tsconfig.json (desci-platform/frontend)
   {
     "compilerOptions": {
       "strict": true,
       "noImplicitAny": true,
       "strictNullChecks": true,
       "strictFunctionTypes": true
     }
   }
   ```

3. **Pydantic 모델 확장**
   - GetDayTrends 패턴을 다른 프로젝트에 전파
   - API request/response 모델 완전 타입 정의

**성공 기준:**
- mypy strict mode 통과
- TypeScript 컴파일 에러 0개

---

## Phase 3: 모니터링 & 옵저버빌리티

**기간**: 2주
**우선순위**: Medium

### 3.1 통합 모니터링 대시보드

**작업 계획:**

1. **Prometheus + Grafana 로컬 스택**
   ```yaml
   # docker-compose.monitoring.yml
   services:
     prometheus:
       image: prom/prometheus
       ports: ["9090:9090"]
       volumes:
         - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

     grafana:
       image: grafana/grafana
       ports: ["3000:3000"]
       environment:
         GF_SECURITY_ADMIN_PASSWORD: admin
       volumes:
         - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards

     node-exporter:
       image: prom/node-exporter
       ports: ["9100:9100"]
   ```

2. **Healthcheck Web UI**
   ```python
   # scripts/healthcheck_server.py
   from fastapi import FastAPI
   from scripts.healthcheck import check_all_projects

   app = FastAPI()

   @app.get("/health")
   async def health():
       return await check_all_projects()

   @app.get("/metrics")
   async def metrics():
       # Prometheus format
       pass
   ```

3. **알림 통합**
   - Prometheus Alertmanager 설정
   - Telegram, Discord, Email 라우팅

**산출물:**
- `monitoring/` 디렉토리 (Prometheus, Grafana 설정)
- `scripts/healthcheck_server.py`
- Grafana 대시보드 JSON

**성공 기준:**
- 모든 서비스 메트릭 실시간 조회 가능
- 알림 1분 내 전달

---

### 3.2 성능 추적 시스템

**작업 계획:**

1. **DORA Metrics 자동화**
   ```bash
   # Cron: 매주 월요일 9시
   python scripts/dora_metrics.py --output reports/dora-$(date +%Y%m%d).md
   ```

2. **LLM 비용 대시보드 확장**
   - 실시간 비용 추적 (Grafana 통합)
   - 프로젝트별, 모델별 비용 분석

3. **API 레이턴시 모니터링**
   ```python
   # FastAPI middleware
   from prometheus_client import Histogram

   request_duration = Histogram('http_request_duration_seconds', 'HTTP request latency')

   @app.middleware("http")
   async def track_latency(request, call_next):
       with request_duration.time():
           response = await call_next(request)
       return response
   ```

**성공 기준:**
- DORA Metrics 자동 생성 (주간)
- API p95 레이턴시 < 500ms

---

### 3.3 로깅 표준화

**작업 계획:**

1. **구조화된 로깅**
   ```python
   # shared/logging_config.py
   import structlog

   structlog.configure(
       processors=[
           structlog.processors.add_log_level,
           structlog.processors.TimeStamper(fmt="iso"),
           structlog.processors.JSONRenderer()
       ]
   )

   logger = structlog.get_logger()
   logger.info("user_login", user_id=123, ip="192.168.1.1")
   # Output: {"event": "user_login", "user_id": 123, "ip": "192.168.1.1", "timestamp": "2026-03-25T10:00:00Z", "level": "info"}
   ```

2. **중앙 로그 수집**
   - Loki + Promtail (경량) 또는 ELK Stack
   - 모든 컨테이너 로그 → Loki

3. **로그 레벨 정책**
   - DEBUG: 개발 환경만
   - INFO: 일반 이벤트
   - WARNING: 복구 가능 오류
   - ERROR: 즉시 대응 필요
   - CRITICAL: 시스템 다운

**산출물:**
- `shared/logging_config.py`
- `docker-compose.logging.yml` (Loki stack)
- `docs/LOGGING_POLICY.md`

---

## Phase 4: AI/LLM 최적화

**기간**: 2-3주
**우선순위**: **High** (비용 절감)

### 4.1 프롬프트 엔지니어링 중앙화

**작업 계획:**

1. **프롬프트 라이브러리 구축**
   ```
   shared/prompts/
     ├── templates/
     │   ├── content_generation.yaml
     │   ├── data_analysis.yaml
     │   └── code_review.yaml
     ├── few_shot_examples/
     │   ├── trend_analysis.json
     │   └── rfp_matching.json
     └── prompt_manager.py
   ```

2. **Few-shot 예시 DB**
   ```python
   # shared/prompts/prompt_manager.py
   class PromptManager:
       def __init__(self):
           self.templates = self.load_templates()
           self.examples = self.load_examples()

       def get_prompt(self, template_name: str, context: dict) -> str:
           template = self.templates[template_name]
           examples = self.examples.get(template_name, [])
           return template.format(examples=examples, **context)
   ```

3. **A/B 테스트 프레임워크**
   - 프롬프트 버전 관리
   - 성능 메트릭 추적 (품질 점수, 토큰 사용량)

**산출물:**
- `shared/prompts/` 라이브러리
- 프롬프트 버전 관리 시스템
- A/B 테스트 결과 리포트

**성공 기준:**
- 모든 LLM 호출이 중앙 라이브러리 사용
- 프롬프트 품질 점수 10% 향상

---

### 4.2 LLM 라우팅 고도화

**작업 계획:**

1. **카테고리별 모델 라우팅 확대**
   ```python
   # shared/llm/router.py
   class LLMRouter:
       ROUTING_RULES = {
           # Heavy tasks (Sonnet)
           "정치": "claude-3.5-sonnet",
           "경제": "claude-3.5-sonnet",
           "테크": "claude-3.5-sonnet",
           # Light tasks (Flash)
           "엔터테인먼트": "gemini-2.5-flash",
           "스포츠": "gemini-2.5-flash",
           # Default
           "default": "gemini-2.5-flash-lite"
       }

       def route(self, category: str, task_complexity: str) -> str:
           if task_complexity == "heavy":
               return self.ROUTING_RULES.get(category, "claude-3.5-sonnet")
           return self.ROUTING_RULES.get(category, "gemini-2.5-flash-lite")
   ```

2. **비용 최적화 알고리즘**
   - 예산 초과 시 자동 다운그레이드 (Sonnet → Flash)
   - 시간대별 예산 할당 (피크/비피크)

3. **Fallback 체인 강화**
   ```python
   FALLBACK_CHAIN = [
       "gemini-2.5-flash",      # Primary
       "gpt-4o-mini",           # Fallback 1
       "claude-3-haiku",        # Fallback 2
       "local-ollama-llama3"    # Fallback 3 (offline)
   ]
   ```

**성공 기준:**
- LLM 비용 30% 절감 ($0.03 → $0.02/request)
- Fallback 성공률 99%

---

### 4.3 RAG 시스템 개선

**작업 계획:**

1. **ChromaDB → Qdrant 마이그레이션 검토**
   - 성능 벤치마크 (검색 속도, 정확도)
   - Qdrant 장점: 필터링, 하이브리드 검색, 스케일링

2. **Hybrid Search (Keyword + Semantic)**
   ```python
   # services/hybrid_search.py
   def hybrid_search(query: str, collection: str):
       # 1. Semantic search (embeddings)
       semantic_results = vector_store.search(query, top_k=20)

       # 2. Keyword search (BM25)
       keyword_results = bm25_index.search(query, top_k=20)

       # 3. Re-rank (reciprocal rank fusion)
       return rerank(semantic_results, keyword_results)
   ```

3. **Re-ranking 파이프라인**
   - Cohere Rerank API 또는 오픈소스 모델 (BGE-reranker)

**산출물:**
- Qdrant 마이그레이션 스크립트 (선택)
- Hybrid search 구현
- Re-ranking 벤치마크 리포트

**성공 기준:**
- 검색 정확도 15% 향상 (Recall@10)

---

## Phase 5: 보안 & 컴플라이언스

**기간**: 1-2주
**우선순위**: **High**

### 5.1 시크릿 관리 고도화

**현황:**
- 17개 .env.example 파일 존재
- 시크릿 평문 보관 (.env)

**작업 계획:**

1. **Vault 또는 SOPS 도입**
   ```bash
   # Option 1: HashiCorp Vault
   docker run -d -p 8200:8200 vault server -dev

   # Option 2: Mozilla SOPS (경량)
   sops --encrypt .env > .env.enc
   sops --decrypt .env.enc > .env
   ```

2. **.env 파일 암호화**
   ```bash
   # 각 프로젝트
   cd desci-platform/biolinker
   sops --encrypt .env --output .env.enc
   echo ".env" >> .gitignore
   git add .env.enc
   ```

3. **Pre-commit hook 강화**
   ```yaml
   # .pre-commit-config.yaml
   - repo: https://github.com/Yelp/detect-secrets
     rev: v1.4.0
     hooks:
       - id: detect-secrets
         args: ['--baseline', '.secrets.baseline']
   ```

**산출물:**
- 암호화된 .env 파일 (각 프로젝트)
- `docs/SECRET_MANAGEMENT_GUIDE.md`
- Pre-commit hook 업데이트

**성공 기준:**
- 모든 시크릿 암호화 저장
- 평문 .env 파일 Git에서 완전 제거

---

### 5.2 보안 스캔 자동화

**작업 계획:**

1. **Dependabot 활성화**
   ```yaml
   # .github/dependabot.yml
   version: 2
   updates:
     - package-ecosystem: "pip"
       directory: "/"
       schedule: {interval: "weekly"}
     - package-ecosystem: "npm"
       directory: "/desci-platform/frontend"
       schedule: {interval: "weekly"}
   ```

2. **SAST/DAST 파이프라인**
   ```yaml
   # .github/workflows/security-scan.yml
   jobs:
     sast:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - name: Semgrep SAST
           uses: returntocorp/semgrep-action@v1
         - name: Trivy container scan
           run: trivy image my-app:latest

     dast:
       runs-on: ubuntu-latest
       steps:
         - name: OWASP ZAP
           uses: zaproxy/action-baseline@v0.7.0
           with:
             target: 'http://localhost:8000'
   ```

3. **취약점 패치 정책**
   - Critical: 24시간 내 패치
   - High: 7일 내 패치
   - Medium: 30일 내 패치

**산출물:**
- Dependabot 설정
- SAST/DAST 워크플로우
- `docs/SECURITY_POLICY.md`

**성공 기준:**
- 취약점 0개 (Critical/High)
- 자동 패치 적용률 80%

---

### 5.3 감사 로그

**작업 계획:**

1. **API 호출 감사 로그**
   ```python
   # FastAPI middleware
   @app.middleware("http")
   async def audit_log(request, call_next):
       user_id = request.headers.get("X-User-ID")
       logger.info("api_call",
                   user_id=user_id,
                   method=request.method,
                   path=request.url.path,
                   ip=request.client.host)
       response = await call_next(request)
       logger.info("api_response", status=response.status_code)
       return response
   ```

2. **데이터 변경 추적**
   ```python
   # SQLAlchemy event listener
   from sqlalchemy import event

   @event.listens_for(Product, 'before_update')
   def audit_product_update(mapper, connection, target):
       audit_log.record_change(
           table='products',
           id=target.id,
           user_id=current_user_id(),
           changes=get_changes(target)
       )
   ```

3. **규정 준수 리포트**
   - 월간 감사 로그 리포트 자동 생성
   - 비정상 접근 패턴 탐지

**산출물:**
- Audit log middleware
- 감사 로그 DB 스키마
- 월간 리포트 생성 스크립트

---

## Phase 6: 문서화 & 지식 관리

**기간**: 진행 중 (Continuous)
**우선순위**: Medium

### 6.1 API 문서 자동화

**작업 계획:**

1. **FastAPI OpenAPI 문서 확장**
   ```python
   # main.py
   from fastapi import FastAPI
   from fastapi.openapi.utils import get_openapi

   app = FastAPI(
       title="DeSci BioLinker API",
       description="AI-powered research proposal matching platform",
       version="2.0.0",
       openapi_tags=[
           {"name": "papers", "description": "Research paper operations"},
           {"name": "rfps", "description": "RFP management"},
           {"name": "matching", "description": "AI matching engine"}
       ]
   )

   # 자동 생성: http://localhost:8000/docs
   ```

2. **Postman Collection 생성**
   ```bash
   # OpenAPI → Postman
   npx openapi-to-postmanv2 -s http://localhost:8000/openapi.json -o biolinker.postman.json
   ```

3. **GraphQL Schema 문서화** (선택)

**산출물:**
- FastAPI Swagger UI (자동)
- Postman Collection
- ReDoc 문서

---

### 6.2 아키텍처 다이어그램

**작업 계획:**

1. **C4 Model 다이어그램**
   ```mermaid
   # docs/architecture/context.mmd
   graph TB
       User[Researcher] --> DeSci[DeSci Platform]
       DeSci --> BioLinker[BioLinker API]
       BioLinker --> ChromaDB[Vector Store]
       BioLinker --> Blockchain[Ethereum Sepolia]
   ```

2. **Sequence Diagram 예시**
   ```mermaid
   sequenceDiagram
       User->>+Frontend: Upload Paper
       Frontend->>+BioLinker: POST /papers
       BioLinker->>+VectorStore: Store Embedding
       BioLinker->>+Matcher: Find Similar RFPs
       Matcher-->>-BioLinker: Top 5 RFPs
       BioLinker-->>-Frontend: Matching Results
       Frontend-->>-User: Display RFPs
   ```

**산출물:**
- `docs/architecture/` (C4 diagrams)
- Mermaid 플로우차트 (각 프로젝트)

---

### 6.3 온보딩 가이드

**작업 계획:**

1. **ONBOARDING.md 작성**
   ```markdown
   # 신규 팀원 온보딩 가이드

   ## Day 1: 환경 설정
   - [ ] Git clone 및 pre-commit hooks 설치
   - [ ] Docker Desktop 설치
   - [ ] Python 3.13, Node.js 22 설치
   - [ ] `.env` 파일 설정 (팀 리더에게 요청)
   - [ ] `docker compose up` 실행

   ## Week 1: 프로젝트 이해
   - [ ] CLAUDE.md 읽기
   - [ ] 각 프로젝트 README 읽기
   - [ ] 간단한 버그 픽스 (good-first-issue)

   ## Week 2-4: 본격 개발
   - [ ] 첫 Feature 개발
   ```

2. **CONTRIBUTING.md 작성**
   ```markdown
   # 기여 가이드

   ## 브랜치 전략
   - `main`: Production
   - `develop`: Development
   - `feature/*`: 새 기능
   - `fix/*`: 버그 수정

   ## Commit Convention
   - feat: 새 기능
   - fix: 버그 수정
   - docs: 문서 변경
   - refactor: 리팩토링
   - test: 테스트 추가
   ```

**산출물:**
- `ONBOARDING.md`
- `CONTRIBUTING.md`
- 온보딩 체크리스트

---

## Phase 7: 배포 & 운영

**기간**: 2-3주
**우선순위**: Medium

### 7.1 배포 자동화

**작업 계획:**

1. **Blue-Green 배포 스크립트**
   ```bash
   # scripts/deploy_blue_green.sh
   # 1. Deploy to Green (standby)
   docker compose -f docker-compose.green.yml up -d

   # 2. Health check
   curl http://green.example.com/health

   # 3. Switch traffic (Nginx)
   cp nginx.conf.green /etc/nginx/sites-enabled/default
   nginx -s reload

   # 4. Shutdown Blue (old)
   docker compose -f docker-compose.blue.yml down
   ```

2. **Canary 릴리스 전략**
   - 10% 트래픽 → Canary
   - 메트릭 모니터링 (에러율, 레이턴시)
   - 문제 없으면 100% 전환

3. **롤백 자동화**
   ```bash
   # scripts/rollback.sh
   git revert HEAD
   docker compose pull
   docker compose up -d
   ```

**산출물:**
- Blue-Green 배포 스크립트
- Canary 릴리스 설정
- 롤백 런북

---

### 7.2 스케일링 준비

**작업 계획:**

1. **Kubernetes Manifest 작성** (선택)
   ```yaml
   # k8s/biolinker-deployment.yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: biolinker
   spec:
     replicas: 3
     selector:
       matchLabels:
         app: biolinker
     template:
       spec:
         containers:
         - name: biolinker
           image: biolinker:latest
           ports:
           - containerPort: 8000
   ```

2. **수평 확장 테스트**
   - Load testing (Locust, k6)
   - Auto-scaling 트리거 설정

3. **캐싱 전략 (Redis)**
   ```python
   import redis
   r = redis.Redis(host='localhost', port=6379)

   @cache(ttl=3600)
   def get_rfp_matches(paper_id: str):
       # Expensive computation
       pass
   ```

**산출물:**
- K8s manifest (선택)
- Load testing 리포트
- Redis 캐싱 구현

---

### 7.3 재해 복구 계획

**작업 계획:**

1. **DR 계획 문서**
   ```markdown
   # DR_PLAN.md

   ## RTO (Recovery Time Objective): 4시간
   ## RPO (Recovery Point Objective): 1시간

   ## 복구 시나리오
   1. 데이터베이스 장애
      - 복구 시간: 30분
      - 절차: PostgreSQL WAL replay

   2. 전체 시스템 다운
      - 복구 시간: 2시간
      - 절차: 백업에서 복원 + DNS 전환
   ```

2. **백업 자동화**
   ```bash
   # Cron: 매일 2 AM
   0 2 * * * pg_dump agriguard > backups/agriguard-$(date +\%Y\%m\%d).sql
   0 2 * * * aws s3 sync backups/ s3://my-backups/
   ```

3. **복구 시나리오 테스트**
   - 분기별 DR 테스트 (실제 복구 수행)

**산출물:**
- `docs/DR_PLAN.md`
- 백업 자동화 스크립트
- DR 테스트 리포트

---

## 성공 지표 (KPI)

### 인프라 & 안정성

| 지표 | 현재 | 목표 | 측정 방법 |
|------|------|------|----------|
| Uptime | ~95% | 99.9% | Prometheus Uptime |
| 평균 복구 시간 (MTTR) | 2시간 | 30분 | Incident log |
| 배포 성공률 | 85% | 95% | GitHub Actions |

### 코드 품질

| 지표 | 현재 | 목표 | 측정 방법 |
|------|------|------|----------|
| 테스트 커버리지 | 미측정 | 70%+ | pytest --cov |
| 기술 부채 (TODO) | 53 files | 26 files | grep -r "TODO" |
| 보안 취약점 (High+) | 0 | 0 | Trivy, Bandit |

### 성능

| 지표 | 현재 | 목표 | 측정 방법 |
|------|------|------|----------|
| API p95 레이턴시 | ~800ms | <500ms | Prometheus |
| LLM 비용/요청 | $0.03 | $0.02 | Cost tracker |
| 빌드 시간 | 25분 | 15분 | GitHub Actions |

### 개발 생산성

| 지표 | 현재 | 목표 | 측정 방법 |
|------|------|------|----------|
| 배포 주기 | 주 1-2회 | 일 1회 | DORA Metrics |
| PR 리드 타임 | 3일 | 1일 | GitHub API |
| 온보딩 시간 | ~2일 | 4시간 | 체크리스트 |

---

## 타임라인 & 리소스

### 전체 타임라인

```mermaid
gantt
    title System Enhancement Roadmap
    dateFormat  YYYY-MM-DD

    section Phase 1: 인프라
    AgriGuard PostgreSQL      :2026-03-25, 7d
    Docker Compose 강화       :2026-03-27, 5d
    CI/CD 최적화             :2026-04-01, 10d

    section Phase 2: 코드 품질
    기술 부채 해소            :2026-03-26, 14d
    테스트 커버리지          :2026-04-03, 14d
    타입 안전성              :2026-04-10, 7d

    section Phase 3: 모니터링
    통합 대시보드            :2026-04-08, 7d
    성능 추적               :2026-04-15, 7d

    section Phase 4: AI/LLM
    프롬프트 중앙화          :2026-04-15, 10d
    LLM 라우팅              :2026-04-20, 7d
    RAG 개선                :2026-04-27, 7d

    section Phase 5: 보안
    시크릿 관리              :2026-03-28, 7d
    보안 스캔               :2026-04-05, 7d

    section Phase 6: 문서화
    API 문서                :2026-04-10, 5d
    아키텍처 다이어그램      :2026-04-15, 5d

    section Phase 7: 배포
    배포 자동화              :2026-05-01, 10d
    재해 복구 계획           :2026-05-10, 7d
```

### Quick Wins (2주 내 완료)

1. **Phase 1.1**: AgriGuard PostgreSQL 완료
2. **Phase 2.1**: 기술 부채 인벤토리 작성
3. **Phase 5.1**: .env 암호화

### High Impact (성능/비용 최적화)

1. **Phase 3**: 모니터링 대시보드
2. **Phase 4**: LLM 비용 최적화

### 리소스 계획

**개발 시간:**
- Backend Engineer: 120시간
- Frontend Engineer: 40시간
- DevOps Engineer: 80시간
- **Total**: ~240시간 (1.5 FTE x 6주)

**인프라 비용:**
- PostgreSQL (Managed): $20/월
- Monitoring Stack (Grafana Cloud): $50/월
- S3 Backup Storage: $10/월
- **Total**: ~$80-100/월

**도구 라이선스:**
- 오픈소스 우선 전략 → $0

---

## 리스크 관리

### 리스크 목록

| 리스크 | 확률 | 영향도 | 완화 전략 |
|--------|------|--------|----------|
| AgriGuard 마이그레이션 데이터 손실 | Low | Critical | QC 스크립트, 백업 강제 |
| CI/CD 파이프라인 장애 | Medium | High | 롤백 자동화, 알림 설정 |
| LLM 비용 초과 | Medium | Medium | 일일 예산 상한, 자동 다운그레이드 |
| 보안 취약점 발견 | Medium | High | 자동 스캔, 패치 정책 |
| 팀원 온보딩 지연 | Low | Low | 온보딩 가이드 사전 준비 |

### 의존성 관리

**외부 의존성:**
- GitHub Actions (CI/CD)
- LLM API (Gemini, OpenAI, Claude)
- Docker Hub (이미지)

**내부 의존성:**
- Phase 1 완료 전 Phase 7 시작 불가
- Phase 2 완료 전 커버리지 게이트 활성화 불가

---

## 다음 단계 (Next Steps)

### 즉시 착수 (이번 주)

1. ✅ 시스템 고도화 계획안 승인 받기 (완료)
2. [ ] Phase 1.1: AgriGuard sensor_readings drift 원인 분석
3. [ ] Phase 2.1: 기술 부채 인벤토리 생성 (`docs/TECH_DEBT_INVENTORY.md`)
4. [ ] Phase 5.1: .env 암호화 PoC (1개 프로젝트 시범)

### 2주 후

1. [ ] Phase 1.2: Docker Compose 통합 환경 구축
2. [ ] Phase 1.3: CI/CD 파이프라인 최적화 착수
3. [ ] Phase 2.2: 테스트 커버리지 측정 시작

### 1개월 후

1. [ ] Phase 3.1: 모니터링 대시보드 가동
2. [ ] Phase 4.1: 프롬프트 라이브러리 구축
3. [ ] 중간 리뷰 (KPI 점검)

---

## 승인 및 변경 이력

**승인자:**
- Backend Team Lead: [서명 대기]
- DevOps Team Lead: [서명 대기]
- Product Owner: [서명 대기]

**변경 이력:**
- 2026-03-25 v1.0: 초안 작성

---

**문서 소유자**: Backend Team
**다음 리뷰**: 2026-04-15 (Phase 1-2 완료 후)
**연락처**: [팀 채널]
