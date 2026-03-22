# Add pytest Coverage Reporting

**Labels**: `testing`, `quality`, `backend`
**Priority**: 📊 **Medium** - 1개월 내

---

## Description

pytest 커버리지 측정 및 리포팅을 설정하여 테스트 품질을 모니터링합니다.

---

## Current vs Target

| Timeline | Coverage | Goal |
|----------|----------|------|
| **Current** | Unknown | Measurement |
| **1개월** | 50% | Core APIs |
| **3개월** | 70% | Production-ready |

---

## Tasks

- [ ] `pytest-cov` 의존성 추가
- [ ] `pytest.ini` 또는 `pyproject.toml`에 커버리지 설정
- [ ] CI에 커버리지 리포트 추가
- [ ] Codecov 또는 Coveralls 연동
- [ ] PR에 커버리지 변화 코멘트 자동 추가
- [ ] 프로젝트별 커버리지 목표 설정
- [ ] 미커버 코드 우선순위 분석

---

## Configuration

### `pyproject.toml`

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "--cov=shared",
    "--cov=DailyNews/src",
    "--cov=desci-platform/biolinker",
    "--cov=AgriGuard/backend",
    "--cov-report=term-missing",
    "--cov-report=xml",
    "--cov-fail-under=50",
]
```

---

## Acceptance Criteria

- ✅ CI에서 커버리지 리포트 생성 확인
- ✅ Codecov 대시보드에서 프로젝트별 커버리지 확인
- ✅ PR에 커버리지 변화 표시
- ✅ 커버리지 < 50% 시 CI 실패

---

**Estimated Time**: 2-3일
