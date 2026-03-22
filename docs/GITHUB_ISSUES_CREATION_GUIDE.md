# GitHub Issues 생성 가이드

**날짜**: 2026-03-22
**상태**: Ready to execute
**총 Issues**: 13개 (Critical 2개, High 3개, Medium 4개, Documentation 2개, Monitoring 1개, 완료 1개)

---

## ⚠️ 사전 준비

### 1. GitHub CLI 로그인

```bash
# GitHub CLI 로그인
gh auth login

# 로그인 과정:
# 1. GitHub.com 선택
# 2. HTTPS 선택
# 3. "Login with a web browser" 선택
# 4. One-time code 복사
# 5. 브라우저에서 코드 입력 및 인증
```

### 2. 로그인 확인

```bash
gh auth status

# 예상 출력:
# ✓ Logged in to github.com as biojuho
```

---

## 📋 Issue 생성 명령어

### Critical Issues (2개 남음, 1개 완료)

#### ✅ Issue #1: GitHub 보안 기능 활성화 (5-10분)
```bash
gh issue create \
  --title "Enable GitHub Security Features" \
  --label "security,critical,devops" \
  --body-file ".github/ISSUE_TEMPLATES/01-github-security-features.md"
```

#### ✅ Issue #2: Gemini 2.0 Flash 제거 (1-2시간)
```bash
gh issue create \
  --title "Remove Deprecated Gemini 2.0 Flash Model" \
  --label "technical-debt,critical,backend" \
  --body-file ".github/ISSUE_TEMPLATES/02-remove-gemini-2-0-flash.md"
```

#### ✅ ~~Issue #3: Gitleaks Pre-commit Hook~~ **[완료]**
```bash
# 이미 완료됨 (2026-03-22)
# - .pre-commit-config.yaml 생성 완료
# - docs/PRE_COMMIT_SETUP.md 가이드 작성 완료
# - CLAUDE.md 업데이트 완료
```

---

### High Priority Issues (3개)

#### Issue #4: PostgreSQL 마이그레이션 (3-5일)
```bash
gh issue create \
  --title "Migrate AgriGuard Database to PostgreSQL" \
  --label "database,high,backend" \
  --body-file ".github/ISSUE_TEMPLATES/04-migrate-postgresql.md"
```

#### Issue #5: 런타임 버전 통일 (2-3일)
```bash
gh issue create \
  --title "Standardize Runtime Versions Across Projects" \
  --label "infrastructure,high,devops" \
  --body-file ".github/ISSUE_TEMPLATES/05-standardize-runtime-versions.md"
```

#### Issue #6: Batch API 구현 (5-7일)
```bash
gh issue create \
  --title "Implement LLM Batch API for Cost Optimization" \
  --label "backend,high,optimization" \
  --body-file ".github/ISSUE_TEMPLATES/06-implement-batch-api.md"
```

---

### Medium Priority Issues (4개)

#### Issue #7: CI/CD 파이프라인 (3-5일)
```bash
gh issue create \
  --title "Implement CI/CD Pipeline with GitHub Actions" \
  --label "devops,medium,infrastructure" \
  --body-file ".github/ISSUE_TEMPLATES/07-cicd-pipeline.md"
```

#### Issue #8: pytest 커버리지 (2-3일)
```bash
gh issue create \
  --title "Improve pytest Coverage to 50%+" \
  --label "testing,medium,backend" \
  --body-file ".github/ISSUE_TEMPLATES/08-pytest-coverage.md"
```

#### Issue #9: Qdrant POC (5-7일)
```bash
gh issue create \
  --title "Evaluate Qdrant as ChromaDB Alternative" \
  --label "research,medium,backend" \
  --body-file ".github/ISSUE_TEMPLATES/09-qdrant-poc.md"
```

#### Issue #10: Docker Compose 통합 (3-4일)
```bash
gh issue create \
  --title "Docker Compose Full Integration + Docs" \
  --label "devops,medium,documentation" \
  --body-file ".github/ISSUE_TEMPLATES/10-docker-compose-setup.md"
```

---

### Documentation Issues (2개)

#### Issue #11: CLAUDE.md 업데이트 (1-2시간)
```bash
gh issue create \
  --title "Update CLAUDE.md with Latest Architecture" \
  --label "documentation" \
  --body-file ".github/ISSUE_TEMPLATES/11-update-claude-md.md"
```

#### Issue #12: 팀 온보딩 가이드 (2-3일)
```bash
gh issue create \
  --title "Create Team Onboarding Guide" \
  --label "documentation" \
  --body-file ".github/ISSUE_TEMPLATES/12-team-onboarding-guide.md"
```

---

### Monitoring Issues (1개)

#### Issue #13: Sentry 에러 트래킹 (2-3일)
```bash
gh issue create \
  --title "Implement Sentry Error Tracking" \
  --label "monitoring,medium,backend" \
  --body-file ".github/ISSUE_TEMPLATES/13-sentry-error-tracking.md"
```

---

## 🚀 일괄 생성 스크립트

모든 Issues를 한 번에 생성하려면 다음 스크립트를 실행하세요:

```bash
#!/bin/bash
# create_all_issues.sh

echo "Creating GitHub Issues..."

# Critical (2개, Issue #3은 완료)
gh issue create --title "Enable GitHub Security Features" \
  --label "security,critical,devops" \
  --body-file ".github/ISSUE_TEMPLATES/01-github-security-features.md"

gh issue create --title "Remove Deprecated Gemini 2.0 Flash Model" \
  --label "technical-debt,critical,backend" \
  --body-file ".github/ISSUE_TEMPLATES/02-remove-gemini-2-0-flash.md"

# High (3개)
gh issue create --title "Migrate AgriGuard Database to PostgreSQL" \
  --label "database,high,backend" \
  --body-file ".github/ISSUE_TEMPLATES/04-migrate-postgresql.md"

gh issue create --title "Standardize Runtime Versions Across Projects" \
  --label "infrastructure,high,devops" \
  --body-file ".github/ISSUE_TEMPLATES/05-standardize-runtime-versions.md"

gh issue create --title "Implement LLM Batch API for Cost Optimization" \
  --label "backend,high,optimization" \
  --body-file ".github/ISSUE_TEMPLATES/06-implement-batch-api.md"

# Medium (4개)
gh issue create --title "Implement CI/CD Pipeline with GitHub Actions" \
  --label "devops,medium,infrastructure" \
  --body-file ".github/ISSUE_TEMPLATES/07-cicd-pipeline.md"

gh issue create --title "Improve pytest Coverage to 50%+" \
  --label "testing,medium,backend" \
  --body-file ".github/ISSUE_TEMPLATES/08-pytest-coverage.md"

gh issue create --title "Evaluate Qdrant as ChromaDB Alternative" \
  --label "research,medium,backend" \
  --body-file ".github/ISSUE_TEMPLATES/09-qdrant-poc.md"

gh issue create --title "Docker Compose Full Integration + Docs" \
  --label "devops,medium,documentation" \
  --body-file ".github/ISSUE_TEMPLATES/10-docker-compose-setup.md"

# Documentation (2개)
gh issue create --title "Update CLAUDE.md with Latest Architecture" \
  --label "documentation" \
  --body-file ".github/ISSUE_TEMPLATES/11-update-claude-md.md"

gh issue create --title "Create Team Onboarding Guide" \
  --label "documentation" \
  --body-file ".github/ISSUE_TEMPLATES/12-team-onboarding-guide.md"

# Monitoring (1개)
gh issue create --title "Implement Sentry Error Tracking" \
  --label "monitoring,medium,backend" \
  --body-file ".github/ISSUE_TEMPLATES/13-sentry-error-tracking.md"

echo "✅ All issues created!"
```

---

## 📊 우선순위별 실행 순서

### 이번 주 (Critical)
1. **Issue #1**: GitHub 보안 기능 활성화 → **5-10분 소요**
2. **Issue #2**: Gemini 2.0 Flash 제거 → **1-2시간 소요**

### 2주 내 (High)
3. **Issue #4**: PostgreSQL 마이그레이션 → **3-5일 소요**
4. **Issue #5**: 런타임 버전 통일 → **2-3일 소요**
5. **Issue #6**: Batch API 구현 → **5-7일 소요**

### 1개월 내 (Medium)
6. **Issue #7**: CI/CD 파이프라인 → **3-5일 소요**
7. **Issue #8**: pytest 커버리지 → **2-3일 소요**
8. **Issue #9**: Qdrant POC → **5-7일 소요**
9. **Issue #10**: Docker Compose 통합 → **3-4일 소요**

### 진행 중 (Documentation)
10. **Issue #11**: CLAUDE.md 업데이트 → **1-2시간 소요**
11. **Issue #12**: 팀 온보딩 가이드 → **2-3일 소요**

### 1개월 내 (Monitoring)
12. **Issue #13**: Sentry 에러 트래킹 → **2-3일 소요**

---

## ✅ 완료 체크리스트

### GitHub CLI 설정
- [ ] `gh auth login` 완료
- [ ] `gh auth status` 확인

### Issues 생성
- [ ] Critical Issues 2개 생성 (Issue #1, #2)
- [ ] High Issues 3개 생성 (Issue #4, #5, #6)
- [ ] Medium Issues 4개 생성 (Issue #7, #8, #9, #10)
- [ ] Documentation Issues 2개 생성 (Issue #11, #12)
- [ ] Monitoring Issue 1개 생성 (Issue #13)

### 검증
- [ ] GitHub 웹에서 Issues 확인
- [ ] 라벨이 올바르게 설정되었는지 확인
- [ ] Milestone 설정 (선택 사항)
- [ ] Assignees 설정 (선택 사항)

---

## 🔗 참고 링크

- **GitHub Issues**: https://github.com/biojuho/BIOJUHO-Projects/issues
- **GitHub Security**: https://github.com/biojuho/BIOJUHO-Projects/settings/security_analysis
- **GitHub Actions**: https://github.com/biojuho/BIOJUHO-Projects/actions
- **Issue Templates**: `.github/ISSUE_TEMPLATES/`

---

## 📝 다음 단계

Issues 생성 후:

1. **Critical Issues부터 작업 시작**
   - Issue #1: GitHub 보안 기능 활성화 (웹에서 수동 설정)
   - Issue #2: Gemini 2.0 Flash 제거 (코드 수정)

2. **Project Board 생성** (선택 사항)
   ```bash
   gh project create --title "System Audit Action Plan" --body "Q2 2026 Roadmap"
   ```

3. **Milestone 설정** (선택 사항)
   ```bash
   gh api repos/biojuho/BIOJUHO-Projects/milestones \
     -X POST \
     -f title='Q2 2026 - System Improvements' \
     -f due_on='2026-06-30T00:00:00Z'
   ```

---

**마지막 업데이트**: 2026-03-22
**작성자**: Claude Code
**관련 문서**:
- [GITHUB_ISSUES_CHECKLIST.md](../GITHUB_ISSUES_CHECKLIST.md)
- [SYSTEM_AUDIT_ACTION_PLAN.md](../SYSTEM_AUDIT_ACTION_PLAN.md)
- [.github/ISSUE_TEMPLATES/](../.github/ISSUE_TEMPLATES/)
