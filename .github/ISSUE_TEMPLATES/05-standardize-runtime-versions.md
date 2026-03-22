# Standardize Python/Node.js Runtime Versions

**Labels**: `devops`, `high-priority`, `infrastructure`
**Priority**: 🔥 **High** - 2주 내 완료

---

## Description

현재 Python 3.14.2와 Node.js v24.13.0을 사용 중이나, CLAUDE.md는 Python 3.12/3.13을 명시합니다. 런타임 기준을 통일합니다.

---

## Current State vs Recommendation

| Runtime | Current Local | CLAUDE.md | Recommendation | Reason |
|---------|---------------|-----------|----------------|--------|
| **Python** | 3.14.2 | 3.12/3.13 | **3.13.3** | langchain 호환 + 최신 안정 버전 |
| **Node.js** | v24.13.0 | 18+ | **22.12.0+** | Vite 7 + 향후 Hardhat 3 대비 |

---

## Tasks

### 1. 버전 표준 파일 생성

- [ ] `.python-version` 파일 생성 (pyenv 호환)
- [ ] `.nvmrc` 파일 생성 (nvm 호환)
- [ ] `runtime.txt` 파일 생성 (Heroku/Docker 호환)

### 2. CLAUDE.md 업데이트

- [ ] Python 버전 요구사항: **3.13.3** (필수)
- [ ] Python 3.14 canary CI 테스트 언급
- [ ] Node.js 버전 요구사항: **22.12.0+** (필수)
- [ ] Gotchas 섹션에 호환성 이슈 추가

### 3. CI/CD 설정

- [ ] GitHub Actions matrix에 Python 3.13 + 3.14 추가
- [ ] GitHub Actions matrix에 Node.js 22.12 추가
- [ ] 버전 불일치 시 경고 표시

### 4. 팀 공지 및 마이그레이션

- [ ] 팀원들에게 로컬 환경 업데이트 가이드 공유
- [ ] pyenv/nvm 설치 가이드 작성
- [ ] 팀원 3명 이상이 업데이트 완료 확인

---

## Files to Create

### `.python-version`

```
3.13.3
```

### `.nvmrc`

```
22.12.0
```

### `runtime.txt` (Heroku/Docker)

```
python-3.13.3
```

---

## pyenv/nvm Installation Guide

### pyenv (Python 버전 관리)

**macOS/Linux**:
```bash
# pyenv 설치
curl https://pyenv.run | bash

# Python 3.13.3 설치
pyenv install 3.13.3

# 프로젝트 디렉토리로 이동
cd "d:\AI 프로젝트"

# Python 버전 자동 전환 (. python-version 파일 기반)
pyenv local 3.13.3

# 확인
python --version  # Python 3.13.3
```

**Windows**:
```powershell
# pyenv-win 설치
Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"; &"./install-pyenv-win.ps1"

# Python 3.13.3 설치
pyenv install 3.13.3
pyenv local 3.13.3
```

### nvm (Node.js 버전 관리)

**macOS/Linux**:
```bash
# nvm 설치
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# Node.js 22.12.0 설치
nvm install 22.12.0

# 프로젝트 디렉토리로 이동
cd "d:\AI 프로젝트"

# Node.js 버전 자동 전환 (.nvmrc 파일 기반)
nvm use

# 확인
node --version  # v22.12.0
```

**Windows**:
```powershell
# nvm-windows 설치 (관리자 권한 필요)
# https://github.com/coreybutler/nvm-windows/releases 에서 설치 파일 다운로드

nvm install 22.12.0
nvm use 22.12.0
```

---

## CI/CD Configuration

### `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test-python:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.13', '3.14']  # 3.14 canary
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements.txt
      - run: pytest

  test-node:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: ['22.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
      - run: npm install
      - run: npm test
```

---

## Compatibility Matrix

### Python Libraries

| Library | 3.12 | 3.13 | 3.14 | Notes |
|---------|------|------|------|-------|
| **langchain** | ✅ | ✅ | ⚠️ | 3.14는 일부 서브 패키지 호환 문제 |
| **FastAPI** | ✅ | ✅ | ✅ | - |
| **SQLAlchemy** | ✅ | ✅ | ✅ | - |
| **google-generativeai** | ✅ | ✅ | ⚠️ | 3.14는 테스트 중 |

### Node.js Frameworks

| Framework | 18 LTS | 20 LTS | 22 LTS | 24 (Current) | Notes |
|-----------|--------|--------|--------|--------------|-------|
| **Vite 7** | ✅ | ✅ | ✅ | ✅ | Node 18+ 요구 |
| **React 19** | ✅ | ✅ | ✅ | ✅ | - |
| **Hardhat 2.x** | ✅ | ✅ | ✅ | ✅ | Node 18+ 요구 |
| **Hardhat 3.x** | ❌ | ⚠️ | ✅ | ✅ | Node 22+ 권장 |

---

## Migration Timeline

### Week 1
- [ ] 표준 파일 생성 및 커밋
- [ ] CI/CD 업데이트
- [ ] 팀 공지

### Week 2
- [ ] 팀원 로컬 환경 업데이트 (3명 이상)
- [ ] CLAUDE.md 업데이트
- [ ] 호환성 테스트 완료

---

## Acceptance Criteria

- ✅ `.python-version`과 `.nvmrc` 파일이 커밋됨
- ✅ CI가 Python 3.13/3.14 + Node.js 22.12로 실행됨
- ✅ CLAUDE.md가 업데이트됨 (필수 버전 명시)
- ✅ 팀원 3명 이상이 로컬 환경 업데이트 완료
- ✅ 모든 테스트가 Python 3.13 + Node.js 22.12에서 통과

---

## Rollback Plan

버전 업그레이드 후 문제 발생 시:

```bash
# Python 롤백
pyenv local 3.12.0

# Node.js 롤백
nvm use 18
```

---

## References

- [pyenv](https://github.com/pyenv/pyenv)
- [nvm](https://github.com/nvm-sh/nvm)
- [Python 3.13 Release Notes](https://docs.python.org/3.13/whatsnew/3.13.html)
- [Node.js 22 Changelog](https://nodejs.org/en/blog/release/v22.12.0)

---

**Estimated Time**: 2-3일
**Blockers**: 팀원 스케줄 조율
**Next Steps**: CI/CD Pipeline 설정 (Issue #7)
