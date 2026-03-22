# Add Gitleaks Pre-commit Hook

**Labels**: `security`, `critical`, `devops`
**Priority**: 🚨 **Critical** - 이번 주 완료 필수

---

## Description

로컬 커밋 단계에서 시크릿 노출을 방지하기 위해 Gitleaks pre-commit hook을 추가합니다.

---

## Tasks

- [ ] `.pre-commit-config.yaml` 파일 생성
- [ ] Gitleaks hook 추가
- [ ] `scripts/check_security.py` hook 통합
- [ ] Python/JS 린터 hook 추가 (Ruff, ESLint)
- [ ] 팀원들에게 설치 가이드 공유
- [ ] CI에서도 동일 체크 실행 (우회 방지)

---

## Configuration

### `.pre-commit-config.yaml`

```yaml
repos:
  # Gitleaks - 시크릿 스캐닝
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks

  # 커스텀 보안 스캐너
  - repo: local
    hooks:
      - id: check-security
        name: Custom Security Scanner
        entry: python scripts/check_security.py
        language: system
        pass_filenames: false

      # Python 린팅
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

  # 기본 체크
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=500']
```

---

## Installation Guide

### 팀원 설치 방법

```bash
# 1. Pre-commit 설치
pip install pre-commit

# 2. Git hooks 설치
pre-commit install

# 3. 모든 파일에 대해 실행 (첫 설치 시)
pre-commit run --all-files
```

### 테스트

```bash
# 테스트용 시크릿 추가 (실제로 커밋되지 않음)
echo "API_KEY=sk-1234567890abcdef" > test_secret.txt
git add test_secret.txt
git commit -m "test"  # Gitleaks가 차단해야 함
```

---

## CI Integration

### `.github/workflows/pre-commit.yml`

```yaml
name: Pre-commit Checks

on:
  push:
    branches: [main]
  pull_request:

jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - uses: pre-commit/action@v3.0.0
```

---

## Acceptance Criteria

- ✅ 시크릿이 포함된 커밋 시도 시 pre-commit이 차단
- ✅ CI에서 동일 검사 실행 확인
- ✅ 팀원 3명 이상이 설치 및 테스트 완료
- ✅ `docs/PRE_COMMIT_SETUP.md` 문서 업데이트

---

## Troubleshooting

### Gitleaks False Positive

`.gitleaksignore` 파일에 허위 양성 추가:

```
# 테스트 파일의 더미 키
tests/fixtures/dummy_api_key.txt:generic-api-key
```

### 너무 느린 경우

특정 디렉토리 제외:

```yaml
exclude: ^(node_modules/|\.venv/|dist/)
```

---

## References

- [Gitleaks](https://github.com/gitleaks/gitleaks)
- [pre-commit](https://pre-commit.com/)
- `docs/PRE_COMMIT_SETUP.md`

---

**Estimated Time**: 2-3시간
**Blockers**: None
