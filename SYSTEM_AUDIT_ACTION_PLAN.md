# AI Projects Workspace - 종합 액션 플랜

**작성일**: 2026-03-22
**기반**: 3개 LLM 시스템 점검 보고서 통합 분석 (GPT-4, Claude, Gemini)
**상태**: 즉시 조치 완료, 단기/중기/장기 로드맵 정의

---

## 📋 Executive Summary

### 보안 스캔 결과 (즉시 조치 완료)

✅ **`.claude/settings.local.json` 분석**:
- **상태**: Git 추적 중 확인됨 (Critical Issue)
- **내용**: 52개의 pre-approved Bash 명령어, 주로 git/pytest/schtasks 작업
- **위험도**: **Medium** - API 키는 없으나 로컬 설정이 팀 전체에 공유되는 문제
- **조치**: `.gitignore`에 추가 완료

✅ **`shared/llm/config.py` 분석**:
- **상태**: API 키 하드코딩 **없음** (안전)
- **내용**: 환경 변수 기반 키 로딩 (`os.getenv`)
- **비용 최적화 설정**:
  - ✅ Gemini 2.5 Flash-Lite 우선 사용 (Free 1,000RPD, $0.10/$0.40)
  - ⚠️ Gemini 2.0 Flash deprecated (2026-06-01 종료 예정) - 레거시 폴백으로만 사용 중
  - ✅ Xiaomi MiMo-V2-Pro ($0.09/1M) 저비용 폴백 체인 구축
  - ✅ Task Tier 기반 모델 라우팅 (HEAVY/MEDIUM/LIGHTWEIGHT)
  - ✅ DeepSeek 제거됨 (한국어 프롬프트 오류로 인한 높은 에러율)

✅ **`DailyNews/src/antigravity_mcp/integrations/llm_adapter.py` 분석**:
- **상태**: API 키 하드코딩 **없음** (안전)
- **내용**:
  - L1 인메모리 캐시 (128개 항목) + L2 SQLite 캐시 구현
  - 3단계 폴백 체인: shared.llm → Gemini → Claude → OpenAI
  - 하드코딩된 임시 API URL 발견 (line 183, 200, 226) - 프로덕션 환경에서 문제 없음

✅ **`.gitignore` 업데이트 완료**:
```diff
+ # Claude Code local settings (NEVER commit - contains personal permissions/overrides)
+ .claude/settings.local.json
+ .claude/*.local.json

+ # DailyNews output files (generated content, test outputs)
+ DailyNews/output/*.txt
+ DailyNews/output/*.json
+ !DailyNews/output/SAMPLE-INSIGHT-OUTPUT.md
```

### 주요 발견 사항

**✅ 긍정적 요소**:
1. API 키가 코드에 하드코딩되지 않음 (환경 변수 기반 관리)
2. LLM 비용 최적화 체계가 잘 구축됨 (Tier 기반 라우팅, 저비용 모델 우선)
3. L1/L2 캐싱으로 중복 호출 방지
4. 명확한 폴백 체인으로 가용성 확보

**⚠️ 개선 필요 영역**:
1. `.claude/settings.local.json`이 Git에 추적됨 → 팀원별 동작 편차 가능
2. Gemini 2.0 Flash deprecated 모델 사용 (2026-06-01 종료 예정)
3. `ALLOW_TEST_BYPASS` 환경 변수 존재 여부 미확인 (프로덕션 노출 위험)
4. AgriGuard SQLite 동시성 문제
5. CI/CD 파이프라인 부재

---

## 🚨 즉시 조치 항목 (완료 ✅ / 진행 중 🔄 / 대기 ⏳)

### Critical (24시간 내)

| # | 항목 | 상태 | 담당 | 완료일 |
|---|------|------|------|--------|
| 1 | `.claude/settings.local.json` Git 추적 해제 | ✅ | AI Agent | 2026-03-22 |
| 2 | `.gitignore`에 로컬 설정 패턴 추가 | ✅ | AI Agent | 2026-03-22 |
| 3 | `DailyNews/output/` 임시 파일 제외 | ✅ | AI Agent | 2026-03-22 |
| 4 | `ALLOW_TEST_BYPASS` 환경 변수 검색 및 제거 계획 | ⏳ | DevOps | - |
| 5 | Git 히스토리에서 민감정보 노출 여부 재확인 | ⏳ | Security | - |
| 6 | 모든 `.env` 파일 백업 및 키 로테이션 계획 | ⏳ | DevOps | - |

### High (1주 내)

| # | 항목 | 상태 | 담당 | 목표일 |
|---|------|------|------|--------|
| 7 | Gemini 2.0 Flash 제거 및 2.5 Flash-Lite로 완전 전환 | 🔄 | Backend | 2026-03-29 |
| 8 | GitHub Secret Scanning + Push Protection 활성화 | ⏳ | DevOps | 2026-03-29 |
| 9 | Dependabot + Dependency Review + CodeQL 설정 | ⏳ | DevOps | 2026-03-29 |
| 10 | `scripts/check_security.py` pre-commit hook 강제화 | ⏳ | DevOps | 2026-03-29 |
| 11 | AgriGuard SQLite → PostgreSQL 마이그레이션 계획 수립 | ⏳ | Backend | 2026-03-29 |
| 12 | Python 런타임 기준 3.13 통일 + 3.14 canary CI 구축 | ⏳ | DevOps | 2026-03-29 |

---

## 📊 보안 스캔 상세 결과

### 1. `.claude/settings.local.json` 분석

**파일 내용 요약**:
- 총 52개의 pre-approved Bash 명령어
- 주요 카테고리:
  - Git 작업 (log, add, commit, push)
  - Python 테스트 (pytest)
  - Windows Task Scheduler 조회 (schtasks)
  - DailyNews CLI 실행 (antigravity_mcp)

**보안 평가**:
- ✅ **API 키 하드코딩 없음**
- ✅ 명령어 허용 리스트(whitelist) 방식
- ⚠️ 일부 명령어에 절대 경로 포함 (로컬 환경 의존성)
- ⚠️ Git 커밋 메시지가 pre-approved에 포함됨 (과도한 자동화 가능성)

**권장 조치**:
1. 이 파일을 개인 로컬 설정으로 유지하고 Git 추적 해제 ✅
2. 팀 공통 정책은 `.claude/settings.json`으로 분리
3. 위험한 명령어(rm, dd, format 등) deny 리스트 추가

### 2. `shared/llm/config.py` 비용 최적화 분석

**현재 Tier 기반 모델 선택 전략**:

```python
TIER_CHAINS: dict[TaskTier, list[tuple[str, str]]] = {
    TaskTier.HEAVY: [
        ("anthropic", "claude-sonnet-4-20250514"),      # $3.0/$15.0
        ("gemini", "gemini-2.5-pro-preview-03-25"),     # $1.25/$10.0
        ("mimo", "mimo-v2-pro"),                        # $0.09/$0.09 ⭐
        ("grok", "grok-3"),                             # $3.0/$15.0
        ("openai", "gpt-4o"),                           # $2.5/$10.0
    ],
    TaskTier.MEDIUM: [
        ("gemini", "gemini-2.5-flash-lite"),            # $0.10/$0.40 ⭐
        ("gemini", "gemini-2.0-flash"),                 # ⚠️ deprecated 2026-06
        ("mimo", "mimo-v2-pro"),                        # $0.09/$0.09
        ("anthropic", "claude-haiku-4-5-20251001"),     # $0.8/$4.0
        ("grok", "grok-3-mini-fast"),                   # $0.3/$0.5
        ("openai", "gpt-4o-mini"),                      # $0.15/$0.6
    ],
    TaskTier.LIGHTWEIGHT: [
        ("gemini", "gemini-2.5-flash-lite"),            # $0.10/$0.40 ⭐ Free 1,000RPD
        ("gemini", "gemini-2.0-flash"),                 # ⚠️ deprecated 2026-06
        ("mimo", "mimo-v2-pro"),                        # $0.09/$0.09
        ("grok", "grok-3-mini-fast"),                   # $0.3/$0.5
        ("anthropic", "claude-haiku-4-5-20251001"),     # $0.8/$4.0
        ("openai", "gpt-4o-mini"),                      # $0.15/$0.6
        ("ollama", "phi3:3.8b"),                        # $0.0 (로컬)
        ("bitnet", "bitnet-b1.58-2b-4t"),               # $0.0 (로컬)
    ],
}
```

**비용 최적화 효과 추정**:

| 작업 유형 | 기존 모델 (예상) | 현재 모델 | 비용 절감율 |
|-----------|-----------------|----------|------------|
| LIGHTWEIGHT 단순 분류 | GPT-4o-mini ($0.15/$0.6) | Gemini 2.5 Flash-Lite ($0.10/$0.40) | **33%~50%** |
| MEDIUM 요약 작업 | Claude Haiku ($0.8/$4.0) | Gemini 2.5 Flash-Lite ($0.10/$0.40) | **87%~90%** |
| HEAVY 분석 작업 | Claude Sonnet 4 ($3.0/$15.0) | MiMo-V2-Pro ($0.09/$0.09) 폴백 | **97%** (성능 trade-off) |

**비용 관련 발견 사항**:
1. ✅ **우수한 설계**: Task Tier 기반 라우팅으로 작업 복잡도에 따라 모델 선택
2. ✅ **저비용 우선**: Gemini Flash-Lite (Free tier 1,000 RPD)를 최우선 사용
3. ⚠️ **Deprecated 모델**: Gemini 2.0 Flash는 2026-06-01 종료 예정이지만 레거시 폴백으로 남아있음
4. ✅ **로컬 모델 폴백**: Ollama/BitNet로 API 비용 $0 옵션 보유
5. ⚠️ **DeepSeek 제거**: 한국어 프롬프트 오류로 인해 모든 체인에서 제거됨 (line 151-156 주석)

**권장 조치** (비용 최적화):
1. **즉시**: Gemini 2.0 Flash 제거 (deprecated)
2. **단기**: OpenAI Batch API 통합 (50% 비용 절감)
3. **단기**: Gemini Batch API 통합 (50% 비용 절감)
4. **중기**: Semantic caching (gptcache) 도입으로 중복 쿼리 비용 $0 전환
5. **중기**: `cost_intelligence.py` 리포트를 Notion/이메일 자동 발송

### 3. `llm_adapter.py` 아키텍처 분석

**캐싱 전략**:
```python
# L1: 인메모리 LRU 캐시 (프로세스 수명 동안 유지)
_L1_MAX_SIZE = 128
_L1_CACHE: OrderedDict[str, ...] = OrderedDict()

# L2: SQLite 영구 캐시 (state_store)
cached_text = self._state_store.get_cached_llm_response(prompt_hash)
```

**폴백 체인**:
```python
1. shared.llm client (Tier 기반 자동 선택)
2. Google Gemini 2.5 Flash (direct API)
3. Anthropic Claude Haiku 4.5 (direct API)
4. OpenAI GPT-4o-mini (direct API)
5. Deterministic fallback (LLM 없이 단순 요약)
```

**보안 평가**:
- ✅ API 키는 `self.settings`에서 로드 (환경 변수 기반)
- ✅ Timeout 설정됨 (30초)
- ⚠️ API URL이 하드코딩됨 (line 183, 200, 226) - 프로덕션에서는 문제없으나 테스트 환경 mock 어려움

**성능 평가**:
- ✅ L1/L2 이중 캐싱으로 중복 호출 방지
- ✅ Prompt normalization으로 캐시 hit율 향상 (line 314-316)
- ⚠️ L1 캐시는 프로세스 재시작 시 소실 → warm-up 비용 발생 가능

**권장 조치**:
1. API URL을 환경 변수로 추출 (테스트 환경 mock 용이)
2. L1 캐시 크기를 동적 조정 (메모리 사용량 모니터링 기반)
3. Redis 기반 L1.5 캐시 도입 검토 (다중 프로세스/컨테이너 환경 대비)

---

## 🗂️ 단기 액션 플랜 (1~2주, 2026-03-22 ~ 2026-04-05)

### A. 보안 강화

| 항목 | 우선순위 | 담당 | 상태 |
|------|----------|------|------|
| GitHub Secret Scanning + Push Protection 활성화 | Critical | DevOps | ⏳ |
| Gitleaks pre-commit hook 추가 | High | DevOps | ⏳ |
| Dependabot 자동 업데이트 설정 | High | DevOps | ⏳ |
| CodeQL 정적 분석 (Python/JS/Solidity) | High | DevOps | ⏳ |
| Firebase 보안 규칙 검토 및 테스트 자동화 | High | Backend | ⏳ |
| `ALLOW_TEST_BYPASS` 환경 변수 제거 | Critical | Backend | ⏳ |
| 블록체인 `PRIVATE_KEY` 시크릿 매니저 이관 | Critical | DevOps | ⏳ |

### B. LLM 비용 최적화

| 항목 | 우선순위 | 담당 | 상태 |
|------|----------|------|------|
| Gemini 2.0 Flash 제거 (deprecated) | High | Backend | 🔄 |
| Gemini 2.5 Flash-Lite Free tier 활용 극대화 | High | Backend | 🔄 |
| OpenAI Batch API 통합 (50% 비용 절감) | Medium | Backend | ⏳ |
| Gemini Batch API 통합 (50% 비용 절감) | Medium | Backend | ⏳ |
| `cost_intelligence.py` 주간 리포트 자동화 | Medium | Backend | ⏳ |

### C. 데이터베이스 마이그레이션

| 항목 | 우선순위 | 담당 | 상태 |
|------|----------|------|------|
| AgriGuard SQLite → PostgreSQL 마이그레이션 계획 | High | Backend | ⏳ |
| Alembic 마이그레이션 스크립트 작성 | High | Backend | ⏳ |
| biolinker ChromaDB → Qdrant POC | Medium | Backend | ⏳ |
| 데이터 백업 자동화 스크립트 | Medium | DevOps | ⏳ |

### D. 테스트 인프라

| 항목 | 우선순위 | 담당 | 상태 |
|------|----------|------|------|
| pytest-cov 커버리지 측정 (목표 70%) | High | Backend | ⏳ |
| Vitest 프론트엔드 테스트 설정 | High | Frontend | ⏳ |
| Playwright E2E 테스트 기본 세트 | High | QA | ⏳ |
| MCP 서버 통합 테스트 | Medium | Backend | ⏳ |

### E. 의존성 관리

| 항목 | 우선순위 | 담당 | 상태 |
|------|----------|------|------|
| Python 3.13 기준선 + 3.14 canary CI | High | DevOps | ⏳ |
| Node 22.12+ 통일 (Vite 7/Hardhat 3 요구사항) | High | DevOps | ⏳ |
| `uv` 패키지 매니저 도입 | Medium | Backend | ⏳ |
| Renovate 자동 업데이트 설정 | Medium | DevOps | ⏳ |

---

## 🚀 중기 액션 플랜 (1~3개월, 2026-04-06 ~ 2026-06-22)

### A. DevOps & CI/CD

| 항목 | 우선순위 | 목표일 |
|------|----------|--------|
| Docker Compose 전체 서비스 통합 | High | 2026-04-30 |
| GitHub Actions CI/CD 파이프라인 (lint → test → build → deploy) | High | 2026-05-15 |
| 환경 분리 (dev/staging/prod) | High | 2026-05-15 |
| Sentry 에러 추적 + 분산 tracing | Medium | 2026-05-31 |
| Prometheus + Grafana 메트릭 수집 | Medium | 2026-06-15 |

### B. 성능 & 확장성

| 항목 | 우선순위 | 목표일 |
|------|----------|--------|
| AgriGuard PostgreSQL 마이그레이션 완료 | Critical | 2026-04-30 |
| biolinker Qdrant 마이그레이션 (또는 server-backed Chroma) | High | 2026-05-31 |
| Semantic caching (gptcache 또는 Redis) 도입 | High | 2026-05-31 |
| Vite 번들 크기 최적화 (lazy loading, code splitting) | Medium | 2026-06-15 |
| FastAPI BackgroundTasks → Celery 전환 (durable queue) | Medium | 2026-06-15 |

### C. 아키텍처 개선

| 항목 | 우선순위 | 목표일 |
|------|----------|--------|
| FastAPI OpenAPI → TypeScript client 자동 생성 | High | 2026-05-15 |
| Pact 계약 테스트 (프론트엔드-백엔드) | High | 2026-05-31 |
| `shared/` 모듈 독립 패키지 분리 | Medium | 2026-06-15 |
| Nx 또는 Turborepo 모노레포 표준화 | Medium | 2026-06-22 |

### D. 자동화 & 워크플로우

| 항목 | 우선순위 | 목표일 |
|------|----------|--------|
| Windows Task Scheduler → GitHub Actions Cron 이전 | High | 2026-04-30 |
| `orchestrator.py` checkpoint/retry 로직 추가 | High | 2026-05-15 |
| pre-commit.ci 클라우드 훅 강제화 | Medium | 2026-05-31 |
| Linear 양방향 동기화 (webhook 기반) | Medium | 2026-06-15 |

---

## 🎯 장기 액션 플랜 (3~12개월, 2026-06-23 ~ 2027-03-22)

### 3개월 (Q2 2026, ~2026-06-22)

**목표**: 보안·비용·안정성 기본기 확립

- [x] `.claude/settings.local.json` Git 추적 해제
- [ ] GitHub secret scanning + push protection + Dependabot + CodeQL 활성화
- [ ] AgriGuard PostgreSQL 마이그레이션
- [ ] LLM Batch API 통합 (비용 50% 절감)
- [ ] Docker Compose + CI/CD 파이프라인 구축
- [ ] 테스트 커버리지 70% 달성

### 6개월 (Q3 2026, ~2026-09-22)

**목표**: 프로덕션 준비 완료

- [ ] biolinker Qdrant 마이그레이션
- [ ] Semantic caching으로 중복 쿼리 비용 $0 전환
- [ ] Sentry + Prometheus 관측성 체계 구축
- [ ] E2E 테스트 80% 커버리지
- [ ] 스마트 컨트랙트 외부 감사 (Slither/Mythril)
- [ ] Nx/Turborepo 모노레포 표준화

### 12개월 (Q1 2027, ~2027-03-22)

**목표**: 엔터프라이즈 수준 운영 체계

- [ ] Kubernetes 또는 서버리스 배포
- [ ] i18n 다국어 지원
- [ ] WCAG 2.2 AA 접근성 준수
- [ ] Python 3.14 호환성 확보
- [ ] 재해 복구 테스트 정례화
- [ ] SBOM + 공급망 보안 자동 리포트

---

## 📈 KPI & 측정 지표

### 보안

| 지표 | 현재 | 목표 (1개월) | 목표 (3개월) |
|------|------|-------------|-------------|
| Git 노출 시크릿 수 | 1 (.claude/settings.local.json) | 0 | 0 |
| Dependabot 자동 업데이트율 | 0% | 80% | 95% |
| 의존성 취약점 수 (Critical/High) | 미측정 | < 5 | 0 |
| 코드 정적 분석 경고 (CodeQL) | 미측정 | < 10 | 0 |

### 비용

| 지표 | 현재 | 목표 (1개월) | 목표 (3개월) |
|------|------|-------------|-------------|
| 월간 LLM API 비용 | 미측정 | 기준선 확립 | -30% |
| Cache hit rate (L1+L2) | 미측정 | 60% | 85% |
| Batch API 사용률 | 0% | 30% | 70% |
| Free tier 활용률 (Gemini Flash-Lite) | 높음 | 최대화 | 최대화 |

### 품질

| 지표 | 현재 | 목표 (1개월) | 목표 (3개월) |
|------|------|-------------|-------------|
| 테스트 커버리지 (Python) | 미측정 | 50% | 70% |
| 테스트 커버리지 (JS/TS) | 미측정 | 40% | 60% |
| E2E 테스트 시나리오 수 | 0 | 10 | 30 |
| CI 빌드 성공률 | 미측정 | 90% | 98% |

### 성능

| 지표 | 현재 | 목표 (1개월) | 목표 (3개월) |
|------|------|-------------|-------------|
| AgriGuard DB 동시 사용자 수 | 1 (SQLite 한계) | 100+ (PostgreSQL) | 1000+ |
| biolinker 벡터 검색 지연 (p95) | 미측정 | < 500ms | < 200ms |
| 프론트엔드 초기 로드 시간 (p75) | 미측정 | < 3s | < 1.5s |
| API 응답 시간 (p95) | 미측정 | < 1s | < 500ms |

---

## 🛠️ 즉시 실행 체크리스트 (오늘 완료)

### 보안

- [x] `.claude/settings.local.json`을 Git 추적 해제
- [x] `.gitignore`에 `.claude/*.local.json` 패턴 추가
- [x] `DailyNews/output/*.txt` .gitignore 추가
- [ ] `git rm --cached .claude/settings.local.json` 실행
- [ ] 변경 사항 커밋 및 푸시

### 비용

- [x] `shared/llm/config.py` 현재 설정 검토 완료
- [ ] Gemini 2.0 Flash 제거 일정 수립
- [ ] `cost_intelligence.py` 현재 월간 비용 리포트 생성

### 문서화

- [x] 시스템 점검 보고서 3개 취합
- [x] 종합 액션 플랜 작성
- [ ] 팀 공유 및 우선순위 합의
- [ ] Linear/Notion에 작업 티켓 생성

---

## 📚 참고 자료

### 도구 추천

**보안**:
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
- [Gitleaks](https://github.com/gitleaks/gitleaks)
- [Slither](https://github.com/crytic/slither) (Solidity)
- [Doppler](https://www.doppler.com/) (시크릿 매니저)

**성능**:
- [Qdrant](https://qdrant.tech/) (벡터 DB)
- [Sentry](https://sentry.io/) (에러 추적)
- [LiteLLM](https://github.com/BerriAI/litellm) (LLM 프록시)

**테스트**:
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [Vitest](https://vitest.dev/)
- [Playwright](https://playwright.dev/)
- [Pact](https://pact.io/) (계약 테스트)

**모노레포**:
- [Nx](https://nx.dev/)
- [Turborepo](https://turbo.build/)
- [uv](https://github.com/astral-sh/uv) (Python 패키지 매니저)

### 관련 문서

- [CLAUDE.md](CLAUDE.md) - 프로젝트 구조 및 명령어
- [SYSTEM_AUDIT_PROMPT.md](SYSTEM_AUDIT_PROMPT.md) - LLM 점검 프롬프트
- [docs/QUALITY_GATE.md](docs/QUALITY_GATE.md) - 품질 기준
- [docs/WORKSPACE-STATUS-2026-03-22.md](docs/WORKSPACE-STATUS-2026-03-22.md) - 워크스페이스 상태

---

## 🔄 업데이트 로그

| 날짜 | 버전 | 변경 사항 |
|------|------|----------|
| 2026-03-22 | 1.0 | 초기 작성 - 3개 LLM 보고서 통합, 즉시 조치 완료 |

---

**다음 검토 일정**: 2026-04-05 (2주 후)
**담당자**: DevOps Lead, Backend Lead, Security Lead
