# GitHub Issues 생성 가이드

이 디렉토리에는 시스템 감사 결과를 바탕으로 생성된 13개의 GitHub Issue 템플릿이 있습니다.

---

## 📋 전체 Issues 목록

### 🚨 Critical Priority (3개)

| # | Issue | Labels | Time |
|---|-------|--------|------|
| 1 | [Enable GitHub Security Features](01-github-security-features.md) | `security`, `critical`, `devops` | 5-10분 |
| 2 | [Remove Deprecated Gemini 2.0 Flash](02-remove-gemini-2-0-flash.md) | `technical-debt`, `critical`, `backend` | 1-2시간 |
| 3 | [Add Gitleaks Pre-commit Hook](03-gitleaks-pre-commit.md) | `security`, `critical`, `devops` | 2-3시간 |

### 🔥 High Priority (3개)

| # | Issue | Labels | Time |
|---|-------|--------|------|
| 4 | [Migrate AgriGuard to PostgreSQL](04-migrate-postgresql.md) | `enhancement`, `high-priority`, `backend`, `database` | 3-5일 |
| 5 | [Standardize Runtime Versions](05-standardize-runtime-versions.md) | `devops`, `high-priority`, `infrastructure` | 2-3일 |
| 6 | [Implement Batch API](06-implement-batch-api.md) | `enhancement`, `cost-optimization`, `backend` | 5-7일 |

### 📊 Medium Priority (4개)

| # | Issue | Labels | Time |
|---|-------|--------|------|
| 7 | [Set Up CI/CD Pipeline](07-cicd-pipeline.md) | `devops`, `infrastructure`, `ci-cd` | 3-5일 |
| 8 | [Add pytest Coverage](08-pytest-coverage.md) | `testing`, `quality`, `backend` | 2-3일 |
| 9 | [Qdrant POC](09-qdrant-poc.md) | `research`, `performance`, `backend` | 5-7일 |
| 10 | [Docker Compose Setup](10-docker-compose-setup.md) | `devops`, `infrastructure`, `docker` | 3-4일 |

### 📝 Documentation (2개)

| # | Issue | Labels | Time |
|---|-------|--------|------|
| 11 | [Update CLAUDE.md](11-update-claude-md.md) | `documentation` | 1-2시간 |
| 12 | [Team Onboarding Guide](12-team-onboarding-guide.md) | `documentation`, `team` | 2-3일 |

### 🔍 Monitoring (1개)

| # | Issue | Labels | Time |
|---|-------|--------|------|
| 13 | [Sentry Error Tracking](13-sentry-error-tracking.md) | `monitoring`, `infrastructure` | 2-3일 |

---

## 🚀 Issues 생성 방법

### 방법 1: GitHub CLI (gh) - 자동화

**사전 요구사항**:
```bash
# gh CLI 인증
gh auth login
```

**전체 Issues 일괄 생성**:
```bash
cd ".github/ISSUE_TEMPLATES"

# Critical Issues (1-3)
gh issue create --title "Enable GitHub Security Features" \
  --body-file 01-github-security-features.md \
  --label "security,critical,devops"

gh issue create --title "Remove Deprecated Gemini 2.0 Flash Model" \
  --body-file 02-remove-gemini-2-0-flash.md \
  --label "technical-debt,critical,backend"

gh issue create --title "Add Gitleaks Pre-commit Hook" \
  --body-file 03-gitleaks-pre-commit.md \
  --label "security,critical,devops"

# High Priority Issues (4-6)
gh issue create --title "Migrate AgriGuard from SQLite to PostgreSQL" \
  --body-file 04-migrate-postgresql.md \
  --label "enhancement,high-priority,backend,database"

gh issue create --title "Standardize Python/Node.js Runtime Versions" \
  --body-file 05-standardize-runtime-versions.md \
  --label "devops,high-priority,infrastructure"

gh issue create --title "Implement OpenAI/Gemini Batch API for Cost Optimization" \
  --body-file 06-implement-batch-api.md \
  --label "enhancement,cost-optimization,backend"

# Medium Priority Issues (7-10)
gh issue create --title "Set Up CI/CD Pipeline" \
  --body-file 07-cicd-pipeline.md \
  --label "devops,infrastructure,ci-cd"

gh issue create --title "Add pytest Coverage Reporting" \
  --body-file 08-pytest-coverage.md \
  --label "testing,quality,backend"

gh issue create --title "Migrate to Qdrant Vector Database (POC)" \
  --body-file 09-qdrant-poc.md \
  --label "research,performance,backend"

gh issue create --title "Docker Compose Multi-Service Setup" \
  --body-file 10-docker-compose-setup.md \
  --label "devops,infrastructure,docker"

# Documentation Issues (11-12)
gh issue create --title "Update CLAUDE.md with Latest Changes" \
  --body-file 11-update-claude-md.md \
  --label "documentation"

gh issue create --title "Create Team Onboarding Guide" \
  --body-file 12-team-onboarding-guide.md \
  --label "documentation,team"

# Monitoring Issue (13)
gh issue create --title "Set Up Sentry Error Tracking" \
  --body-file 13-sentry-error-tracking.md \
  --label "monitoring,infrastructure"
```

---

### 방법 2: GitHub 웹 UI - 수동

1. **GitHub Issues 페이지로 이동**
   - URL: https://github.com/biojuho/BIOJUHO-Projects/issues

2. **New Issue 클릭**

3. **각 템플릿 파일 열기**
   - `.github/ISSUE_TEMPLATES/01-github-security-features.md` 파일 열기

4. **내용 복사 & 붙여넣기**
   - 템플릿 파일의 **Title** (첫 줄 `#` 제외)를 Issue Title에 입력
   - 템플릿 파일의 **본문 전체**를 Issue Description에 붙여넣기
   - **Labels**를 템플릿 파일 상단의 `**Labels**` 섹션에서 확인하여 추가

5. **Submit new issue**

6. **1번부터 13번까지 반복**

---

## 📊 예상 타임라인

### Week 1 (Critical)
- ✅ Issue #1: GitHub Security Features (5-10분)
- ✅ Issue #2: Remove Gemini 2.0 Flash (1-2시간)
- ✅ Issue #3: Gitleaks Pre-commit Hook (2-3시간)

### Week 2-3 (High Priority)
- 🔄 Issue #4: PostgreSQL Migration (3-5일)
- 🔄 Issue #5: Runtime Versions (2-3일)
- 🔄 Issue #6: Batch API (5-7일)

### Week 4-5 (Medium Priority)
- 🔄 Issue #7: CI/CD Pipeline (3-5일)
- 🔄 Issue #8: pytest Coverage (2-3일)
- 🔄 Issue #9: Qdrant POC (5-7일)
- 🔄 Issue #10: Docker Compose (3-4일)

### Ongoing (Documentation & Monitoring)
- 📝 Issue #11: CLAUDE.md Update (1-2시간)
- 📝 Issue #12: Onboarding Guide (2-3일)
- 🔍 Issue #13: Sentry Setup (2-3일)

---

## 🎯 성공 지표 (KPIs)

완료 시 다음 지표 달성:
- ✅ 보안 스캔 100% 활성화 (Secret Scanning, Dependabot, CodeQL)
- ✅ Deprecated 모델 0개
- ✅ SQLite 의존성 0개 (AgriGuard → PostgreSQL)
- ✅ 런타임 버전 통일 (Python 3.13.3, Node 22.12.0+)
- ✅ LLM 비용 30% 절감 (Batch API + 캐싱)
- ✅ CI/CD 파이프라인 가동
- ✅ 테스트 커버리지 50%+

---

## 📚 참고 문서

- [GITHUB_ISSUES_CHECKLIST.md](../../GITHUB_ISSUES_CHECKLIST.md) - 원본 체크리스트
- [SYSTEM_AUDIT_ACTION_PLAN.md](../../SYSTEM_AUDIT_ACTION_PLAN.md) - 3/6/12개월 로드맵
- [docs/POSTGRESQL_MIGRATION_PLAN.md](../../docs/POSTGRESQL_MIGRATION_PLAN.md) - DB 마이그레이션 계획
- [docs/PRE_COMMIT_SETUP.md](../../docs/PRE_COMMIT_SETUP.md) - Pre-commit hooks 가이드
- [docs/GITHUB_SECURITY_SETUP.md](../../docs/GITHUB_SECURITY_SETUP.md) - GitHub 보안 설정 가이드

---

## ❓ 문의

Issues 생성 중 문제가 발생하면:
1. GitHub CLI 인증 확인: `gh auth status`
2. 레이블이 없으면 수동으로 생성: Repository Settings → Labels
3. 기타 문의: Tech Lead에게 연락

---

**생성일**: 2026-03-22
**마지막 업데이트**: 2026-03-22
**Source**: System Audit Report
