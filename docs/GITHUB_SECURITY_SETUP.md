# GitHub 보안 기능 활성화 가이드

이 가이드는 BIOJUHO-Projects 저장소의 GitHub 보안 기능을 활성화하는 방법을 설명합니다.

## 목차

1. [Secret Scanning 활성화](#secret-scanning-활성화)
2. [Push Protection 활성화](#push-protection-활성화)
3. [Dependabot 활성화](#dependabot-활성화)
4. [CodeQL Analysis 활성화](#codeql-analysis-활성화)
5. [보안 정책 설정](#보안-정책-설정)

---

## Secret Scanning 활성화

Secret Scanning은 커밋된 API 키, 비밀번호 등을 자동으로 검사합니다.

### 1. GitHub 웹 인터페이스에서 활성화

#### 단계별 가이드:

1. **저장소 Settings 이동**
   - https://github.com/biojuho/BIOJUHO-Projects 접속
   - 상단 메뉴에서 **Settings** 클릭

2. **Security 섹션 찾기**
   - 왼쪽 사이드바에서 **Code security and analysis** 클릭

3. **Secret scanning 활성화**
   - "Secret scanning" 섹션 찾기
   - **Enable** 버튼 클릭

   ```
   ✅ Secret scanning
   Receive alerts on GitHub for detected secrets, keys, or other tokens.
   [Enabled]
   ```

4. **확인**
   - "Secret scanning enabled successfully" 메시지 확인

### 2. 검사되는 Secret 유형

GitHub는 다음 200+ 가지 Secret 유형을 자동으로 검사합니다:

#### API Keys
- AWS Access Key ID / Secret Access Key
- Google Cloud API Key
- Azure Storage Account Key
- OpenAI API Key
- Anthropic API Key
- GitHub Personal Access Token

#### Database Credentials
- PostgreSQL Connection String
- MySQL Password
- MongoDB Connection URI
- Redis Password

#### Encryption Keys
- RSA Private Key
- SSH Private Key
- PGP Private Key
- JWT Secret

#### OAuth & Authentication
- OAuth Client Secret
- Firebase Service Account
- Stripe API Key
- Twilio Auth Token

### 3. Secret 발견 시 조치

#### Alert 확인:
```bash
# GitHub CLI로 Secret Scanning Alerts 확인
gh secret scanning list

# 특정 Alert 상세 정보
gh secret scanning view <alert-number>
```

#### Alert 대응 절차:

1. **즉시 Secret 무효화**
   ```bash
   # 예: OpenAI API Key가 노출된 경우
   # 1. OpenAI Dashboard에서 해당 키 삭제
   # 2. 새 키 생성
   # 3. .env 파일 업데이트
   ```

2. **Git History에서 Secret 제거**
   ```bash
   # BFG Repo-Cleaner 사용 (권장)
   java -jar bfg.jar --replace-text passwords.txt .git
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive

   # 또는 git filter-branch (수동)
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch path/to/file" \
     --prune-empty --tag-name-filter cat -- --all
   ```

3. **Force Push (주의!)**
   ```bash
   # ⚠️ 팀에 미리 공지 필요
   git push origin --force --all
   git push origin --force --tags
   ```

4. **Alert 해결 표시**
   ```bash
   # GitHub 웹에서 "Close as revoked" 클릭
   # 또는 GitHub CLI 사용
   gh secret scanning close <alert-number> --reason revoked
   ```

---

## Push Protection 활성화

Push Protection은 Secret이 포함된 커밋을 푸시하는 것을 사전에 차단합니다.

### 1. 저장소 레벨에서 활성화

#### GitHub 웹 인터페이스:

1. **Settings > Code security and analysis** 이동

2. **Push protection 활성화**
   - "Push protection" 섹션 찾기
   - **Enable** 버튼 클릭

   ```
   ✅ Push protection
   Block commits that contain supported secrets.
   [Enabled]
   ```

3. **확인**
   - "Push protection enabled successfully" 메시지 확인

### 2. 조직 레벨에서 활성화 (관리자만 가능)

#### GitHub Organization Settings:

1. **Organization > Settings > Code security and analysis**

2. **Enable push protection for all repositories**
   - "Automatically enable for new repositories" 체크

### 3. Push Protection 동작 방식

#### Secret 검출 시:
```bash
$ git push origin main
remote: error: GH013: Repository rule violations found for refs/heads/main.
remote:
remote: - Secret scanning prevented the following secret(s) from being pushed:
remote:
remote:   On line 15:
remote:   OPENAI_API_KEY=sk-proj-abc123def456...
remote:
remote:   Possible types: OpenAI API Key
remote:
remote: Push protection can be bypassed by the following users:
remote:   - Organization owners
remote:   - Repository administrators
remote:
remote: Visit https://docs.github.com/code-security/secret-scanning/push-protection-for-repositories
remote: to learn more about push protection.
To https://github.com/biojuho/BIOJUHO-Projects.git
 ! [remote rejected] main -> main (push declined due to repository rule violations)
error: failed to push some refs to 'https://github.com/biojuho/BIOJUHO-Projects.git'
```

#### 대응 방법:

**Option 1: Secret 제거 (권장)**
```bash
# 1. 마지막 커밋 수정
git reset --soft HEAD~1

# 2. Secret을 .env로 이동
echo "OPENAI_API_KEY=sk-proj-abc..." >> .env

# 3. 코드에서 하드코딩 제거
# config.py:
# - api_key = "sk-proj-abc..."
# + api_key = os.getenv("OPENAI_API_KEY")

# 4. 다시 커밋
git add .
git commit -m "fix: move API key to environment variable"
git push origin main
```

**Option 2: False Positive인 경우 우회**
```bash
# ⚠️ 정말 False Positive인 경우에만 사용
# GitHub 웹에서 "Allow this secret" 클릭
# 또는 secret을 .gitignore에 추가
echo "path/to/fake-secret.txt" >> .gitignore
```

---

## Dependabot 활성화

Dependabot은 의존성 취약점을 자동으로 검사하고 PR을 생성합니다.

### 1. Dependabot Alerts 활성화

#### GitHub 웹 인터페이스:

1. **Settings > Code security and analysis** 이동

2. **Dependabot alerts 활성화**
   - "Dependabot alerts" 섹션
   - **Enable** 버튼 클릭

3. **Dependabot security updates 활성화**
   - "Dependabot security updates" 섹션
   - **Enable** 버튼 클릭 (자동 PR 생성)

### 2. Dependabot Version Updates 설정

#### `.github/dependabot.yml` 파일 생성:

```yaml
version: 2
updates:
  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    reviewers:
      - "biojuho"
    labels:
      - "dependencies"
      - "python"

  # Python dependencies (DailyNews)
  - package-ecosystem: "pip"
    directory: "/DailyNews"
    schedule:
      interval: "weekly"

  # Python dependencies (AgriGuard)
  - package-ecosystem: "pip"
    directory: "/AgriGuard/backend"
    schedule:
      interval: "weekly"

  # Python dependencies (desci-platform)
  - package-ecosystem: "pip"
    directory: "/desci-platform/biolinker"
    schedule:
      interval: "weekly"

  # npm dependencies (Frontend)
  - package-ecosystem: "npm"
    directory: "/desci-platform/frontend"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    reviewers:
      - "biojuho"
    labels:
      - "dependencies"
      - "javascript"

  # npm dependencies (Contracts)
  - package-ecosystem: "npm"
    directory: "/desci-platform/contracts"
    schedule:
      interval: "weekly"

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "monthly"
    labels:
      - "dependencies"
      - "github-actions"
```

#### 커밋 및 푸시:
```bash
mkdir -p .github
# 위 내용을 .github/dependabot.yml에 복사

git add .github/dependabot.yml
git commit -m "ci: add Dependabot config for automated dependency updates"
git push origin main
```

### 3. Dependabot PR 검토

#### PR 자동 생성 예시:
```
title: Bump anthropic from 1.0.0 to 1.1.0
labels: dependencies, python

Updates anthropic from 1.0.0 to 1.1.0

Release notes:
- Added support for new model
- Fixed token counting bug

Changelog:
https://github.com/anthropics/anthropic-sdk-python/releases/tag/v1.1.0
```

#### PR 머지 전 체크리스트:
- [ ] CI 테스트 통과 확인
- [ ] CHANGELOG 확인 (Breaking Changes 없는지)
- [ ] 로컬에서 테스트 (`git pull && pytest`)
- [ ] 머지 후 production 배포 모니터링

---

## CodeQL Analysis 활성화

CodeQL은 코드 취약점을 정적 분석으로 검사합니다.

### 1. CodeQL Workflow 생성

#### `.github/workflows/codeql.yml` 파일:

```yaml
name: "CodeQL Security Scan"

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]
  schedule:
    - cron: '0 6 * * 1'  # 매주 월요일 오전 6시 (UTC)

jobs:
  analyze:
    name: Analyze
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      security-events: write

    strategy:
      fail-fast: false
      matrix:
        language: [ 'python', 'javascript' ]

    steps:
    - name: Checkout repository
      uses: actions/checkout@v4

    - name: Initialize CodeQL
      uses: github/codeql-action/init@v3
      with:
        languages: ${{ matrix.language }}
        queries: security-extended

    - name: Autobuild
      uses: github/codeql-action/autobuild@v3

    - name: Perform CodeQL Analysis
      uses: github/codeql-action/analyze@v3
      with:
        category: "/language:${{matrix.language}}"
```

#### 커밋 및 푸시:
```bash
mkdir -p .github/workflows
# 위 내용을 .github/workflows/codeql.yml에 복사

git add .github/workflows/codeql.yml
git commit -m "ci: add CodeQL security analysis workflow"
git push origin main
```

### 2. CodeQL 결과 확인

#### GitHub 웹에서:
1. **Security > Code scanning alerts** 이동
2. 발견된 취약점 확인
3. 각 Alert 클릭 → 상세 설명 + 수정 제안 확인

#### GitHub CLI:
```bash
# CodeQL 결과 조회
gh api /repos/biojuho/BIOJUHO-Projects/code-scanning/alerts

# 특정 Alert 상세 정보
gh api /repos/biojuho/BIOJUHO-Projects/code-scanning/alerts/<alert-number>
```

---

## 보안 정책 설정

### 1. SECURITY.md 파일 생성

#### `SECURITY.md`:

```markdown
# Security Policy

## Supported Versions

Currently supported versions for security updates:

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them to:
- **Email**: security@biojuho.com
- **GitHub Security Advisory**: https://github.com/biojuho/BIOJUHO-Projects/security/advisories/new

You should receive a response within 48 hours.

### What to include:
- Type of issue (e.g. SQL injection, XSS, etc.)
- Full paths of source file(s) related to the issue
- Step-by-step instructions to reproduce
- Proof-of-concept or exploit code (if possible)
- Impact of the issue

## Security Features

- **Secret Scanning**: Automated detection of leaked credentials
- **Push Protection**: Prevents pushing secrets to GitHub
- **Dependabot**: Automated dependency vulnerability scanning
- **CodeQL**: Static code analysis for security issues
- **Pre-commit Hooks**: Local security checks before commit

## Security Best Practices

1. **Never commit sensitive data**
   - Use `.env` files for secrets (excluded via `.gitignore`)
   - Use environment variables in production

2. **Keep dependencies updated**
   - Review Dependabot PRs weekly
   - Run `pip list --outdated` monthly

3. **Follow secure coding guidelines**
   - Input validation for all user inputs
   - Parameterized queries for database access
   - HTTPS for all external API calls

4. **Code review process**
   - All PRs must be reviewed by at least one other developer
   - Security-sensitive changes require additional review

## Incident Response

If a security incident is discovered:

1. **Immediate**: Notify security@biojuho.com
2. **1 hour**: Security team investigates
3. **4 hours**: Initial assessment and containment
4. **24 hours**: Root cause analysis
5. **48 hours**: Patch development and testing
6. **72 hours**: Patch deployment and public disclosure
```

#### 커밋:
```bash
# 위 내용을 SECURITY.md에 복사
git add SECURITY.md
git commit -m "docs: add security policy and reporting guidelines"
git push origin main
```

### 2. Branch Protection Rules 설정

#### GitHub 웹에서:

1. **Settings > Branches** 이동

2. **Add branch protection rule** 클릭

3. **main 브랜치 보호 규칙 설정**:
   ```
   Branch name pattern: main

   ✅ Require a pull request before merging
      ✅ Require approvals: 1
      ✅ Dismiss stale pull request approvals when new commits are pushed

   ✅ Require status checks to pass before merging
      ✅ Require branches to be up to date before merging
      Status checks:
        - CodeQL / Analyze (python)
        - CodeQL / Analyze (javascript)
        - Pre-commit Checks

   ✅ Require conversation resolution before merging

   ✅ Do not allow bypassing the above settings
   ```

4. **Create** 버튼 클릭

---

## 완료 체크리스트

프로젝트 보안 설정이 완료되었는지 확인하세요:

### 필수 항목 (Critical)

- [ ] **Secret Scanning** 활성화됨
- [ ] **Push Protection** 활성화됨
- [ ] **Dependabot Alerts** 활성화됨
- [ ] **CodeQL Workflow** 생성 및 실행됨
- [ ] **SECURITY.md** 파일 생성됨
- [ ] **Branch Protection Rules** 설정됨 (main)
- [ ] **Pre-commit Hooks** 모든 팀원이 설치

### 권장 항목 (Recommended)

- [ ] **Dependabot Version Updates** 설정됨 (`.github/dependabot.yml`)
- [ ] **Security Policy** 팀과 공유됨
- [ ] **Incident Response Plan** 수립됨
- [ ] **보안 교육** 팀원 전원 이수
- [ ] **정기 보안 점검** 월 1회 스케줄됨

### 모니터링 (Ongoing)

- [ ] **매주**: Dependabot PR 검토 및 머지
- [ ] **매주**: Secret Scanning Alerts 확인
- [ ] **매월**: CodeQL 결과 검토
- [ ] **분기별**: 보안 정책 업데이트
- [ ] **연간**: 전체 보안 감사

---

## 참고 자료

- [GitHub Secret Scanning Documentation](https://docs.github.com/en/code-security/secret-scanning)
- [GitHub Push Protection Documentation](https://docs.github.com/en/code-security/secret-scanning/push-protection-for-repositories)
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [CodeQL Documentation](https://codeql.github.com/docs/)
- [GitHub Security Best Practices](https://docs.github.com/en/code-security/getting-started/securing-your-repository)

## 문의

보안 관련 문의:
- **이메일**: security@biojuho.com
- **GitHub Issues**: https://github.com/biojuho/BIOJUHO-Projects/issues (보안 취약점 제외)
- **Slack**: #security (내부 팀원만)
