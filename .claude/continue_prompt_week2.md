# AI Projects Workspace - Week 2 작업 계속 진행 프롬프트

**날짜**: 2026-03-22
**현재 상태**: PostgreSQL 마이그레이션 Week 2 진행 중
**다음 작업**: Docker 준비 후 PostgreSQL 벤치마크 + 데이터 마이그레이션

---

## 📊 완료된 작업 (2026-03-22)

### ✅ PostgreSQL Week 2 - Part 1
1. **SQLite 벤치마크 실행 완료**
   - AgriGuard DB: 700 KB, 2,126 rows (5개 테이블)
   - 5가지 성능 테스트 완료
   - 결과: 동시 쓰기 불가능, Single INSERT 너무 느림 (105ms)
   - 문서: `docs/db_migration_benchmark_sqlite.md`

2. **GitHub Issues 생성 가이드 작성**
   - 13개 Issue 템플릿 → 12개 생성 필요 (Issue #3 이미 완료)
   - 일괄 생성 스크립트: `scripts/create_github_issues.sh`
   - 가이드: `docs/GITHUB_ISSUES_CREATION_GUIDE.md`

3. **Git 커밋 완료**
   - Commit: `65e56e3` - "feat: PostgreSQL Week 2 진행 - SQLite 벤치마크 + GitHub Issues 가이드"
   - 3개 파일 추가 (728 라인)

---

## 🚧 남은 작업 (우선순위별)

### 🔴 Critical - 이번 주 완료 필수

#### 1. GitHub 수동 설정 (5-10분)
```
현재 상태: 대기 중 (GitHub CLI 로그인 필요)

작업 순서:
1. gh auth login
   - GitHub.com 선택
   - HTTPS 선택
   - Login with web browser
   - One-time code 입력

2. GitHub Issues 생성 (12개)
   bash scripts/create_github_issues.sh
   또는 수동: gh issue create --body-file [템플릿].md

3. GitHub 웹 설정 (수동):
   a. Secret Scanning 활성화
      URL: https://github.com/biojuho/BIOJUHO-Projects/settings/security_analysis
      - "Secret scanning" Enable 클릭
      - "Push protection" Enable 클릭

   b. Branch Protection Rules
      URL: https://github.com/biojuho/BIOJUHO-Projects/settings/branches
      - Branch: main
      - ✅ Require pull request (1 approval)
      - ✅ Require status checks
      - ✅ Require conversation resolution

   c. CodeQL 첫 실행
      URL: https://github.com/biojuho/BIOJUHO-Projects/actions/workflows/codeql.yml
      - "Run workflow" 클릭

참고: docs/GITHUB_SECURITY_SETUP.md
```

#### 2. Gemini 2.0 Flash 제거 (1-2시간)
```
현재 상태: 대기 중

영향 범위:
- shared/llm/config.py (line 50, 58)
- agents/trend_analyzer.py (line 65)
- 테스트 파일 업데이트

마이그레이션:
- Before: ("gemini", "gemini-2.0-flash")
- After:  ("gemini", "gemini-2.5-flash")

검증:
rg "gemini-2\.0-flash" --type py --glob '!tests/'
pytest shared/tests/ DailyNews/tests/ -v
python scripts/cost_intelligence.py --days 7

Deadline: 2026-05-01 (EOL 1개월 전)
```

---

### 🟠 High Priority - 2주 내 완료

#### 3. PostgreSQL 마이그레이션 Week 2 (3-5일)
```
현재 상태: 50% 완료 (SQLite 벤치마크 완료, PostgreSQL 대기 중)

다음 단계:
1. Docker Desktop 시작
   - Docker Desktop 실행
   - docker ps 명령어로 확인

2. PostgreSQL 컨테이너 시작
   docker compose up -d postgres

3. PostgreSQL 연결 확인
   docker exec -it ai-postgres psql -U postgres -d agriguard
   \dt  # 테이블 목록 (비어있어야 함)
   \q

4. PostgreSQL 벤치마크 실행
   python scripts/benchmark_database.py \
     --sqlite AgriGuard/backend/agriguard.db \
     --postgres postgresql://postgres:postgres@localhost:5432/agriguard \
     --output docs/db_migration_benchmark_full.md

5. 결과 비교 분석
   - SQLite vs PostgreSQL 성능 비교
   - 동시 쓰기 테스트 (PostgreSQL만 가능)
   - 마이그레이션 권장사항 확정

6. 데이터 마이그레이션 실행
   python scripts/migrate_agriguard_db.py

7. 마이그레이션 검증
   - Row count 비교 (SQLite 2,126 vs PostgreSQL)
   - 데이터 무결성 확인
   - 외래키 제약 조건 확인

참고: docs/POSTGRESQL_MIGRATION_PLAN.md (Week 2-3)
```

#### 4. 런타임 버전 통일 (2-3일)
```
현재 상태: 대기 중

현재 문제:
- Python: 3.12 (langchain), 3.13 (표준), 3.14 (테스트)
- Node: 22.12.0+ (Vite 7 필요)

작업:
1. Python 3.13.3 표준화
   - .python-version 파일 생성
   - 모든 requirements.txt 업데이트
   - CI/CD에서 3.13 강제

2. Node 22.12.0+ 표준화
   - .nvmrc 파일 생성
   - package.json "engines" 필드 추가
   - CI/CD에서 Node 22 강제

3. Docker 이미지 업데이트
   - python:3.13-slim
   - node:22-alpine

참고: .github/ISSUE_TEMPLATES/05-standardize-runtime-versions.md
```

#### 5. Batch API 구현 (5-7일)
```
현재 상태: 대기 중

목표: LLM 비용 30% 절감

현재 비용 (30일):
- Gemini API: $12.34 (6,502 calls)
- OpenAI API: $8.76 (1,234 calls)
- Total: $21.10

구현 계획:
1. Gemini Batch API 통합
   - DailyNews 트렌드 분석 (비실시간)
   - Biolinker RFP 매칭 (백그라운드)

2. OpenAI Batch API 통합
   - 콘텐츠 생성 (24시간 지연 허용)

3. 우선순위 큐 설계
   - Realtime: 기존 API (사용자 대기)
   - Batch: 새 API (백그라운드)

4. 비용 모니터링
   - scripts/cost_intelligence.py 업데이트
   - 주간 리포트 자동 생성

참고: .github/ISSUE_TEMPLATES/06-implement-batch-api.md
```

---

### 🟡 Medium Priority - 1개월 내

#### 6. CI/CD 파이프라인 (3-5일)
```
.github/workflows/ci.yml 생성
- Python: pytest, ruff, mypy
- Node: npm test, ESLint
- Docker: build & push

참고: .github/ISSUE_TEMPLATES/07-cicd-pipeline.md
```

#### 7. pytest 커버리지 50%+ (2-3일)
```
현재 커버리지: 미측정

목표:
- DailyNews: 50%+
- Biolinker: 50%+
- AgriGuard: 50%+

참고: .github/ISSUE_TEMPLATES/08-pytest-coverage.md
```

#### 8. Qdrant POC (5-7일)
```
ChromaDB 대안 평가
- 성능 비교
- 비용 분석
- 마이그레이션 계획

참고: .github/ISSUE_TEMPLATES/09-qdrant-poc.md
```

#### 9. Docker Compose 통합 (3-4일)
```
모든 서비스를 docker-compose.yml로 통합
- biolinker, frontend, contracts
- AgriGuard backend
- PostgreSQL, Redis, Qdrant

참고: .github/ISSUE_TEMPLATES/10-docker-compose-setup.md
```

---

### 📝 Documentation - 진행 중

#### 10. CLAUDE.md 업데이트 (1-2시간)
```
최신 아키텍처 반영:
- PostgreSQL 마이그레이션 상태
- Gemini 2.5 Flash 모델
- Pre-commit hooks 필수 설정
- Docker Compose 통합

참고: .github/ISSUE_TEMPLATES/11-update-claude-md.md
```

#### 11. 팀 온보딩 가이드 (2-3일)
```
신규 팀원용 종합 가이드:
- 환경 설정 (Python, Node, Docker)
- Pre-commit hooks 설치
- 프로젝트 구조 설명
- 개발 워크플로우
- 문제 해결 가이드

참고: .github/ISSUE_TEMPLATES/12-team-onboarding-guide.md
```

---

### 📊 Monitoring - 1개월 내

#### 12. Sentry 에러 트래킹 (2-3일)
```
프로덕션 모니터링 설정:
- Sentry SDK 통합 (Python, React)
- 에러 알림 설정
- 성능 모니터링
- Release tracking

참고: .github/ISSUE_TEMPLATES/13-sentry-error-tracking.md
```

---

## 🎯 다음 세션에서 진행할 작업

### 옵션 1: PostgreSQL 마이그레이션 완료 (권장)
```
"PostgreSQL 마이그레이션 Week 2 계속 진행해주세요"

진행 내용:
1. Docker Desktop 시작 확인
2. PostgreSQL 컨테이너 시작
3. 벤치마크 실행 (SQLite vs PostgreSQL)
4. 데이터 마이그레이션
5. 검증 및 문서화
```

### 옵션 2: GitHub Issues 생성 먼저
```
"GitHub Issues 13개 생성해주세요"

진행 내용:
1. gh auth login 가이드
2. scripts/create_github_issues.sh 실행
3. 생성 결과 확인
4. Critical Issues 작업 시작 (#1, #2)
```

### 옵션 3: Gemini 2.0 Flash 제거 (빠른 승리)
```
"Gemini 2.0 Flash 모델 제거 작업 시작해주세요"

진행 내용:
1. shared/llm/config.py 수정
2. agents/trend_analyzer.py 수정
3. 테스트 파일 업데이트
4. pytest 실행 및 검증
5. 비용 리포트 생성
```

### 옵션 4: 모든 작업 통합
```
".claude/continue_prompt_week2.md 파일을 읽고 남은 작업을 우선순위대로 진행해주세요"

진행 내용:
- Critical → High → Medium 순서로 자동 진행
- 각 작업마다 완료 여부 확인
- 블로커 발생 시 사용자에게 알림
```

---

## 📁 주요 파일 위치

### 새로 생성된 문서
```
docs/
  ├── db_migration_benchmark_sqlite.md        # SQLite 벤치마크 결과
  ├── GITHUB_ISSUES_CREATION_GUIDE.md         # Issues 생성 가이드
  ├── POSTGRESQL_MIGRATION_PLAN.md            # 4주 마이그레이션 계획
  ├── GITHUB_SECURITY_SETUP.md                # GitHub 보안 설정 가이드
  └── PRE_COMMIT_SETUP.md                     # Pre-commit hooks 가이드

scripts/
  ├── benchmark_database.py                   # DB 벤치마크 스크립트
  ├── migrate_agriguard_db.py                 # 데이터 마이그레이션 스크립트
  └── create_github_issues.sh                 # Issues 일괄 생성 스크립트

.github/
  ├── ISSUE_TEMPLATES/                        # 13개 Issue 템플릿
  ├── dependabot.yml                          # 의존성 자동 업데이트
  └── workflows/
      └── codeql.yml                          # CodeQL 정적 분석
```

### 기존 중요 문서
```
CLAUDE.md                                     # 프로젝트 메인 가이드
SYSTEM_AUDIT_ACTION_PLAN.md                  # 종합 개선 로드맵
GITHUB_ISSUES_CHECKLIST.md                   # Issues 체크리스트
.pre-commit-config.yaml                       # Pre-commit hooks 설정
docker-compose.yml                            # Docker 서비스 정의
```

---

## 🔍 현재 시스템 상태

### Git
```bash
브랜치: main
커밋: 65e56e3 (origin/main보다 3 커밋 앞섬)
미푸시 커밋:
  - ad00543: PostgreSQL Week 1 (스크립트 + 인프라)
  - 8e7db46: GitHub Issues 템플릿 13개
  - 65e56e3: PostgreSQL Week 2 Part 1 (SQLite 벤치마크 + Issues 가이드)

다음 단계: git push origin main (선택 사항)
```

### 데이터베이스
```
SQLite (현재):
  - 파일: AgriGuard/backend/agriguard.db (700 KB)
  - Rows: 2,126 (5개 테이블)
  - 성능: 읽기 우수, 쓰기 느림, 동시 쓰기 불가

PostgreSQL (대기 중):
  - Docker 이미지: postgres:16-alpine
  - 포트: 5432
  - 상태: 컨테이너 미실행 (Docker Desktop 필요)
```

### 보안 설정
```
✅ 완료:
  - .pre-commit-config.yaml (Gitleaks, Ruff, Custom Security)
  - scripts/check_security.py (API 키 스캐너)
  - docs/PRE_COMMIT_SETUP.md (팀 가이드)
  - .github/workflows/codeql.yml (정적 분석)
  - .github/dependabot.yml (의존성 업데이트)
  - SECURITY.md (보안 정책)

⏳ 대기 중 (수동 설정):
  - GitHub Secret Scanning 활성화
  - Push Protection 활성화
  - Branch Protection Rules 설정
```

---

## 💡 사용 방법

### 간단하게 다음 작업 계속
```
"다음 작업 진행해주세요"
→ PostgreSQL 벤치마크부터 자동 재개
```

### 특정 작업 지정
```
"PostgreSQL 마이그레이션 완료해주세요"
"GitHub Issues 13개 생성해주세요"
"Gemini 2.0 Flash 제거 작업 시작해주세요"
```

### 상세 계획 기반 진행
```
".claude/continue_prompt_week2.md 파일을 읽고 남은 Critical 작업부터 진행해주세요"
```

### 특정 섹션만 진행
```
"이 파일의 'PostgreSQL 마이그레이션 Week 2' 섹션만 진행해주세요"
"이 파일의 'GitHub 수동 설정' 섹션을 먼저 완료해주세요"
```

---

**마지막 업데이트**: 2026-03-22 21:15 KST
**작성자**: Claude Code
**다음 우선순위**: PostgreSQL 벤치마크 + 데이터 마이그레이션 (Docker 준비 시)
