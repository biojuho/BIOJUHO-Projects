# Pre-commit Hooks 설치 가이드

이 가이드는 AI Projects Workspace의 Pre-commit hooks를 설치하고 사용하는 방법을 설명합니다.

## 목차

1. [Pre-commit이란?](#pre-commit이란)
2. [설치](#설치)
3. [사용법](#사용법)
4. [Hook 목록](#hook-목록)
5. [문제 해결](#문제-해결)

## Pre-commit이란?

Pre-commit은 Git commit 전에 자동으로 실행되는 스크립트 모음입니다. 코드 품질, 보안, 스타일을 자동으로 검사하여 문제가 있는 코드가 커밋되는 것을 방지합니다.

### 우리 프로젝트의 Pre-commit Hooks

- **Gitleaks**: API 키, 비밀번호 등 민감 정보 검사
- **Ruff**: Python 코드 린팅 및 포매팅
- **Custom Security Scanner**: 추가 보안 검사 (`scripts/check_security.py`)
- **YAML Validation**: YAML 파일 문법 검사
- **Trailing Whitespace**: 불필요한 공백 제거

## 설치

### 1. Pre-commit 설치

```bash
pip install pre-commit
```

### 2. Git Hooks 설치

프로젝트 루트 디렉토리에서 실행:

```bash
pre-commit install
```

성공 메시지:
```
pre-commit installed at .git/hooks/pre-commit
```

### 3. 설치 확인

```bash
pre-commit --version
```

예상 출력:
```
pre-commit 3.x.x
```

## 사용법

### 자동 실행 (권장)

`git commit` 실행 시 자동으로 hooks가 실행됩니다:

```bash
git add .
git commit -m "feat: 새로운 기능 추가"
```

Hooks 실행 예시:
```
Gitleaks.............................................................Passed
Ruff.................................................................Passed
Ruff Format..........................................................Passed
Check Yaml...........................................................Passed
Trim Trailing Whitespace.............................................Passed
Custom Security Scanner..............................................Passed
```

### 수동 실행

전체 파일에 대해 hooks 실행:

```bash
pre-commit run --all-files
```

특정 파일에 대해 hooks 실행:

```bash
pre-commit run --files shared/llm/config.py
```

특정 hook만 실행:

```bash
pre-commit run gitleaks --all-files
pre-commit run ruff --all-files
```

### Hooks 건너뛰기 (긴급 상황만)

```bash
git commit -m "emergency fix" --no-verify
```

⚠️ **경고**: `--no-verify`는 보안 검사를 우회하므로 매우 신중하게 사용해야 합니다.

## Hook 목록

### 1. Gitleaks (보안)

**목적**: API 키, 비밀번호 등 민감 정보 누출 방지

**검사 항목**:
- API Keys (AWS, Google, GitHub, OpenAI, 등)
- Private Keys (RSA, SSH, PGP)
- Database 연결 문자열
- JWT 토큰
- OAuth Secrets

**실패 시 조치**:
```bash
# 잘못 커밋된 비밀 정보를 .env로 이동
mv hardcoded_key .env

# .gitignore에 추가 확인
cat .gitignore | grep .env
```

### 2. Ruff (Python 린팅)

**목적**: Python 코드 품질 및 스타일 검사

**검사 항목**:
- PEP 8 스타일 가이드 준수
- 사용하지 않는 import 제거
- 문법 오류 검사
- 코드 복잡도 검사

**자동 수정**:
```bash
# Ruff가 자동으로 수정 가능한 문제를 수정
ruff check --fix .
ruff format .
```

**실패 시 조치**:
```bash
# 특정 파일 수정
ruff check --fix shared/llm/config.py

# 전체 프로젝트 포매팅
ruff format .
```

### 3. Custom Security Scanner

**목적**: 프로젝트별 보안 규칙 검사

**검사 항목** (`scripts/check_security.py`):
- `.env` 파일이 Git에 커밋되지 않았는지 확인
- Private key 파일 (`.pem`, `.key`) 검사
- 하드코딩된 API 키 패턴 검사
- 민감한 파일명 검사

**실패 시 조치**:
```bash
# 민감 파일 Git에서 제거
git rm --cached .env
git rm --cached **/*.pem

# .gitignore에 추가
echo ".env" >> .gitignore
echo "*.pem" >> .gitignore
```

### 4. YAML Validation

**목적**: YAML 파일 문법 검사

**검사 대상**:
- `.github/workflows/*.yml`
- `docker-compose.yml`
- `.pre-commit-config.yaml`

**실패 시 조치**:
```bash
# YAML 문법 검사
python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"
```

### 5. Trailing Whitespace

**목적**: 불필요한 공백 제거

**자동 수정**: 파일 끝의 공백을 자동으로 제거합니다.

## 문제 해결

### 문제 1: Pre-commit이 설치되지 않음

**증상**:
```
pre-commit: command not found
```

**해결**:
```bash
# Python 환경 확인
python --version  # Python 3.13.3 권장

# pip로 설치
pip install pre-commit

# 또는 시스템 패키지 매니저 사용 (Linux/Mac)
brew install pre-commit  # macOS
sudo apt install pre-commit  # Ubuntu
```

### 문제 2: Gitleaks가 false positive 보고

**증상**:
```
Gitleaks.............................................................Failed
- hook id: gitleaks
- exit code: 1

Detecting hardcoded secrets...
Finding:     GOOGLE_API_KEY=AIza...
```

**해결**:

`.gitleaksignore` 파일 생성:
```bash
echo "path/to/false/positive.py:1" >> .gitleaksignore
```

또는 `.pre-commit-config.yaml`에서 제외:
```yaml
- repo: https://github.com/gitleaks/gitleaks
  rev: v8.18.2
  hooks:
    - id: gitleaks
      exclude: ^tests/fixtures/.*$  # 테스트 파일 제외
```

### 문제 3: Ruff가 너무 많은 오류 보고

**증상**:
```
Ruff.................................................................Failed
- hook id: ruff
- exit code: 1

100+ errors found
```

**해결**:

단계별 수정:
```bash
# 1. 자동 수정 가능한 문제만 수정
ruff check --fix .

# 2. 포매팅 적용
ruff format .

# 3. 남은 문제 확인
ruff check .

# 4. 특정 규칙 비활성화 (필요 시)
# pyproject.toml 또는 ruff.toml에 추가
[tool.ruff]
ignore = ["E501"]  # line too long
```

### 문제 4: Hooks가 너무 느림

**증상**:
```
Gitleaks takes 30+ seconds...
```

**해결**:

파일 제외 설정 추가:
```yaml
# .pre-commit-config.yaml
- repo: https://github.com/gitleaks/gitleaks
  rev: v8.18.2
  hooks:
    - id: gitleaks
      exclude: |
        (?x)^(
          .*\.min\.js$|
          .*\.min\.css$|
          node_modules/.*|
          .venv/.*
        )$
```

### 문제 5: Windows에서 Gitleaks 실행 오류

**증상**:
```
FileNotFoundError: [WinError 2] The system cannot find the file specified: 'gitleaks'
```

**해결**:

Gitleaks 수동 설치:
```powershell
# Chocolatey 사용
choco install gitleaks

# 또는 GitHub Release에서 다운로드
# https://github.com/gitleaks/gitleaks/releases
# gitleaks.exe를 PATH에 추가
```

### 문제 6: Pre-commit 업데이트

**최신 버전으로 업데이트**:
```bash
# Hooks 정의 업데이트
pre-commit autoupdate

# Pre-commit 자체 업데이트
pip install --upgrade pre-commit
```

## 고급 사용법

### CI/CD 통합

GitHub Actions에서 pre-commit 실행:

```yaml
# .github/workflows/pre-commit.yml
name: Pre-commit Checks

on:
  pull_request:
  push:
    branches: [main]

jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - uses: pre-commit/action@v3.0.1
```

### 커스텀 Hook 추가

`.pre-commit-config.yaml`에 local hook 추가:

```yaml
- repo: local
  hooks:
    - id: check-secrets
      name: Check for secrets
      entry: python scripts/check_security.py
      language: system
      pass_filenames: false
```

### 특정 브랜치에서만 실행

```bash
# .git/hooks/pre-commit 수정
#!/bin/bash

# main 브랜치에만 pre-commit 실행
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" = "main" ]; then
  pre-commit run --all-files
fi
```

## 팀 가이드라인

### 필수 사항

✅ **모든 팀원이 설치해야 함**
- 프로젝트 클론 후 즉시 `pre-commit install` 실행
- 매주 `pre-commit autoupdate` 실행

✅ **커밋 전 확인 사항**
- Pre-commit hooks가 모두 통과했는지 확인
- `--no-verify`는 팀 리더 승인 후에만 사용

✅ **실패 시 조치**
- Hook 실패 원인 확인 후 코드 수정
- 수정 불가능한 false positive는 팀에 공유

### 권장 사항

🔹 **매일 실행**
```bash
pre-commit run --all-files
```

🔹 **커밋 메시지에 Hook 결과 포함**
```bash
git commit -m "feat: 새 기능 추가 (pre-commit: passed)"
```

🔹 **정기 업데이트**
```bash
# 매주 월요일
pre-commit autoupdate
git add .pre-commit-config.yaml
git commit -m "chore: update pre-commit hooks"
```

## 참고 자료

- [Pre-commit 공식 문서](https://pre-commit.com/)
- [Gitleaks GitHub](https://github.com/gitleaks/gitleaks)
- [Ruff 공식 문서](https://docs.astral.sh/ruff/)
- [프로젝트 보안 가이드](./SECURITY.md)

## 문의

문제가 해결되지 않으면 다음 채널로 문의하세요:
- GitHub Issues: https://github.com/biojuho/BIOJUHO-Projects/issues
- Slack: #dev-support
- 이메일: dev-team@example.com
