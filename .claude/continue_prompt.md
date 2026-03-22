# 다음 작업 계속 진행 프롬프트

다음 작업들을 계속 진행해주세요:

## 완료된 작업 (참고용)

✅ Gemini 2.0 Flash 제거 완료 (72/72 테스트 통과)
✅ Pre-commit hooks 설치 가이드 작성 완료
✅ GitHub 보안 설정 파일 생성 완료 (Dependabot, CodeQL, SECURITY.md)
✅ 모든 문서 커밋 및 푸시 완료 (커밋: 7590439)

## 남은 작업 목록

### 우선순위 1: GitHub 수동 설정 (5-10분)

1. **Secret Scanning + Push Protection 활성화**
   - 가이드: `docs/GITHUB_SECURITY_SETUP.md` 참고
   - URL: https://github.com/biojuho/BIOJUHO-Projects/settings/security_analysis
   - 작업:
     - [ ] Secret scanning → Enable
     - [ ] Push protection → Enable
     - [ ] 활성화 스크린샷으로 확인

2. **CodeQL 첫 실행 확인**
   - URL: https://github.com/biojuho/BIOJUHO-Projects/actions/workflows/codeql.yml
   - 작업:
     - [ ] "Run workflow" 버튼 클릭 (수동 트리거)
     - [ ] Python + JavaScript 분석 결과 대기
     - [ ] Security 탭에서 결과 확인

3. **Branch Protection Rules 설정**
   - URL: https://github.com/biojuho/BIOJUHO-Projects/settings/branches
   - 작업:
     - [ ] "Add branch protection rule" 클릭
     - [ ] Branch name pattern: `main`
     - [ ] 권장 설정 (docs/GITHUB_SECURITY_SETUP.md 섹션 참고):
       - Require pull request before merging (1 approval)
       - Require status checks (CodeQL, Pre-commit)
       - Require conversation resolution

### 우선순위 2: GitHub Issues 생성 (20-30분)

**참고 문서**: `GITHUB_ISSUES_CHECKLIST.md`

Critical Priority (3개):
- [ ] Issue #1: Enable GitHub Secret Scanning + Push Protection
- [ ] Issue #2: Remove Gemini 2.0 Flash (완료됨 - Close as completed)
- [ ] Issue #3: Add Gitleaks to Pre-commit Hooks

High Priority (3개):
- [ ] Issue #4: Migrate AgriGuard to PostgreSQL
- [ ] Issue #5: Standardize Python 3.13 + Node 22.12+
- [ ] Issue #6: Implement Batch API for Cost Optimization

Medium Priority (7개):
- [ ] Issue #7: Add CI/CD Pipeline (GitHub Actions)
- [ ] Issue #8: Increase Test Coverage to 80%+
- [ ] Issue #9: Qdrant POC for Biolinker
- [ ] Issue #10: Docker Compose Production Config
- [ ] Issue #11: LLM Cost Monitoring Dashboard
- [ ] Issue #12: Setup Sentry Error Tracking
- [ ] Issue #13: i18n Support (Korean/English)

**작업 방법**:
```bash
# GitHub CLI로 Issue 생성 예시:
gh issue create \
  --title "Enable GitHub Secret Scanning + Push Protection" \
  --body-file .github/ISSUE_TEMPLATES/secret-scanning.md \
  --label "security,critical" \
  --assignee biojuho
```

또는 웹에서 수동 생성:
- https://github.com/biojuho/BIOJUHO-Projects/issues/new

### 우선순위 3: PostgreSQL 마이그레이션 Week 1 (1-2시간)

**참고 문서**: `docs/POSTGRESQL_MIGRATION_PLAN.md`

**Week 1 작업** (AgriGuard SQLite → PostgreSQL):

1. **Alembic 설정**
   ```bash
   cd AgriGuard/backend
   pip install alembic psycopg2-binary
   alembic init alembic
   ```

2. **마이그레이션 스크립트 생성**
   ```bash
   # alembic/env.py 설정
   # models.py의 Base.metadata import

   alembic revision --autogenerate -m "initial migration from SQLite"
   ```

3. **PostgreSQL 데이터베이스 준비**
   ```bash
   # Docker Compose로 PostgreSQL 시작
   docker compose up -d postgres

   # 데이터베이스 초기화
   docker compose exec postgres psql -U postgres -f /scripts/init-databases.sql
   ```

4. **병렬 테스트 환경 구축**
   ```bash
   # .env.test 파일 생성
   DATABASE_URL=postgresql://postgres:password@localhost:5432/agriguard_test

   # 테스트 실행
   pytest AgriGuard/tests/ --database=postgresql
   ```

5. **성능 비교 보고서**
   ```bash
   python scripts/benchmark_database.py \
     --sqlite agriguard.db \
     --postgres postgresql://localhost/agriguard \
     --output docs/db_migration_benchmark.md
   ```

### 우선순위 4: Dependabot PR 첫 검토 (대기 중)

Dependabot이 첫 PR을 생성하면 (월요일 예상):

1. **PR 확인**
   ```bash
   gh pr list --label dependencies
   ```

2. **변경사항 검토**
   - CHANGELOG 확인 (Breaking Changes 있는지)
   - 테스트 통과 여부 확인
   - 보안 취약점 수정인지 확인

3. **로컬 테스트**
   ```bash
   gh pr checkout <PR-number>
   pytest
   npm test
   ```

4. **머지 또는 코멘트**
   ```bash
   # 승인 후 머지
   gh pr review <PR-number> --approve
   gh pr merge <PR-number> --squash

   # 또는 코멘트
   gh pr comment <PR-number> --body "LGTM after CI passes"
   ```

## 작업 진행 방법

### 옵션 1: 수동 설정 먼저 (권장)

```
나에게 다음을 알려주세요:
1. GitHub Secret Scanning 활성화 완료
2. Push Protection 활성화 완료
3. Branch Protection Rules 설정 완료

그러면 GitHub Issues 13개를 자동으로 생성해드리겠습니다.
```

### 옵션 2: GitHub Issues 생성부터 시작

```
GITHUB_ISSUES_CHECKLIST.md를 기반으로 GitHub Issues 13개를 생성해주세요.
gh CLI를 사용하거나 수동으로 생성할 수 있습니다.
```

### 옵션 3: PostgreSQL 마이그레이션 시작

```
docs/POSTGRESQL_MIGRATION_PLAN.md의 Week 1 작업을 시작해주세요:
1. Alembic 설정
2. 마이그레이션 스크립트 생성
3. Docker Compose PostgreSQL 환경 구축
```

### 옵션 4: 모든 작업 자동 진행

```
다음 순서로 모든 작업을 진행해주세요:
1. 수동 설정 가이드 출력 (스크린샷 첨부 요청)
2. GitHub Issues 13개 생성 (gh CLI 사용)
3. PostgreSQL 마이그레이션 Week 1 시작
```

## 현재 상태 체크리스트

### 완료 (2026-03-22)
- [x] Gemini 2.0 Flash 제거
- [x] 테스트 72/72 통과
- [x] Pre-commit hooks 가이드 작성
- [x] Dependabot 설정 파일
- [x] CodeQL workflow 파일
- [x] SECURITY.md 작성
- [x] 보안 설정 가이드 작성

### 진행 중 (수동 작업 필요)
- [ ] Secret Scanning 활성화
- [ ] Push Protection 활성화
- [ ] Branch Protection Rules 설정
- [ ] CodeQL 첫 실행

### 대기 중
- [ ] GitHub Issues 13개 생성
- [ ] PostgreSQL 마이그레이션 Week 1
- [ ] Dependabot PR 첫 검토 (월요일)

## 참고 문서 목록

- `GITHUB_ISSUES_CHECKLIST.md` - 생성할 Issue 템플릿 13개
- `SYSTEM_AUDIT_ACTION_PLAN.md` - 3/6/12개월 로드맵
- `docs/POSTGRESQL_MIGRATION_PLAN.md` - 4주 마이그레이션 계획
- `docs/PRE_COMMIT_SETUP.md` - Pre-commit hooks 가이드
- `docs/GITHUB_SECURITY_SETUP.md` - GitHub 보안 설정 가이드
- `QUICK_START.md` - 30분 온보딩 가이드
- `SECURITY.md` - 보안 정책 및 인시던트 대응
- `.github/dependabot.yml` - Dependabot 설정
- `.github/workflows/codeql.yml` - CodeQL 워크플로우

## 프롬프트 사용법

새 대화 세션에서 다음 중 하나를 입력하세요:

**간단 버전**:
```
다음 작업 진행해주세요
```

**상세 버전**:
```
.claude/continue_prompt.md 파일을 읽고 남은 작업들을 순서대로 진행해주세요.
현재 완료된 작업은 참고만 하고, "남은 작업 목록" 섹션부터 시작하면 됩니다.
```

**특정 작업 지정**:
```
PostgreSQL 마이그레이션 Week 1 작업을 시작해주세요.
docs/POSTGRESQL_MIGRATION_PLAN.md를 참고하여 Alembic 설정부터 시작합니다.
```

---

**마지막 업데이트**: 2026-03-22 23:00 KST
**다음 체크포인트**: GitHub 수동 설정 완료 후
**예상 소요 시간**: 1-3시간 (작업 범위에 따라)
