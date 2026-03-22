# Set Up CI/CD Pipeline

**Labels**: `devops`, `infrastructure`, `ci-cd`
**Priority**: 📊 **Medium** - 1개월 내

---

## Description

GitHub Actions를 통한 기본 CI/CD 파이프라인을 구축합니다.

---

## Pipeline Stages

1. **Lint**: Ruff (Python), ESLint (JS/TS), Solidity linter
2. **Test**: pytest, Vitest, Hardhat test
3. **Security**: CodeQL, Dependency Review, Gitleaks
4. **Build**: Docker images
5. **Deploy**: (스테이징 환경 준비 후)

---

## Tasks

- [ ] `.github/workflows/ci.yml` 생성
- [ ] Python 프로젝트 CI (lint + test)
- [ ] Node.js 프로젝트 CI (lint + test + build)
- [ ] Solidity 프로젝트 CI (compile + test)
- [ ] Security 스캔 통합
- [ ] Docker 이미지 빌드 및 push (GHCR)
- [ ] Path-based filtering (변경된 프로젝트만 빌드)
- [ ] Matrix strategy (Python 3.13/3.14, Node 22)
- [ ] 캐싱 최적화 (pip, npm, Hardhat)

---

## Example Workflow

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

---

## Acceptance Criteria

- ✅ PR마다 자동으로 CI 실행
- ✅ 모든 스테이지 통과 시 merge 가능
- ✅ 실행 시간 < 10분 (캐싱 최적화 후)
- ✅ 팀원들이 CI 결과를 PR에서 확인 가능

---

**Estimated Time**: 3-5일
