# Workspace Status - 2026-03-22

작성 시각: 2026-03-22 KST

## 요약

2026-03-21부터 진행한 워크스페이스 정합성 점검 및 품질 게이트 복구 작업을 기록한다.
이번 작업의 목표는 "문서상 통과"가 아니라 실제 로컬 스모크 체크가 끝까지 통과하는 상태를 만드는 것이었다.

현재 상태:

- workspace smoke: 14/14 PASS
- desci frontend lint: PASS
- desci biolinker smoke: PASS
- DailyNews unit tests: PASS
- getdaytrends compile/tests: PASS

## 이번에 반영한 정리

### 1. 루트 pytest 기본 동작 복구

루트 `pytest.ini`의 기본 `addopts`에 `--cov-config=pytest.ini`가 포함되어 있었고, 현재 로컬 `.venv`에는 `pytest-cov`가 설치되어 있지 않아 기본 `pytest` 실행 자체가 실패했다.

조치:

- `pytest.ini`에서 커버리지 옵션을 제거
- 기본 회귀 테스트와 BioLinker smoke가 별도 옵션 없이 실행되도록 조정

영향:

- 루트 테스트 명령의 신뢰도 회복
- smoke 스크립트가 환경 의존성 때문에 거짓 실패를 내던 문제 해소

### 2. DeSci frontend lint 실패 해소

`desci-platform/frontend/src/components/PricingPage.jsx`에서 `useAuth()`로부터 받은 `user` 변수가 사용되지 않아 lint가 실패하고 있었다.

조치:

- 미사용 `user` 제거

영향:

- `desci` 스코프 smoke 전부 정상화

### 3. Smoke 범위와 문서 일치화

`docs/QUALITY_GATE.md`에는 `DailyNews`와 `getdaytrends`가 품질 게이트에 포함된다고 적혀 있었지만, 실제 `scripts/run_workspace_smoke.py`에는 해당 체크가 구현되어 있지 않았다.

조치:

- `DailyNews/tests/unit` 추가
- `getdaytrends` compile 추가
- `getdaytrends/tests` 추가
- `--scope getdaytrends` 지원 추가
- smoke 테스트 문서/검증 코드 동기화

영향:

- 문서와 실제 자동 점검 범위 일치
- 핵심 운영 프로젝트가 smoke에서 빠지는 문제 해소

## 검증 결과

실행 명령:

```powershell
.\\.venv\\Scripts\\python.exe scripts/run_workspace_smoke.py --scope all --json-out logs/workspace_smoke_after_fixes_2026-03-21.json
```

결과:

- passed=14
- failed=0
- total=14

포함된 체크:

1. workspace regression tests
2. desci frontend lint
3. desci frontend unit tests
4. desci frontend build
5. desci bundle budget
6. desci biolinker smoke
7. agriguard frontend lint
8. agriguard frontend build
9. agriguard backend compile
10. notebooklm compile
11. github-mcp compile
12. DailyNews unit tests
13. getdaytrends compile
14. getdaytrends tests

세부 리포트:

- `logs/workspace_smoke_after_fixes_2026-03-21.json`

## 남은 TODO

### 운영 확인

- DailyNews 첫 자동 실행 로그 확인
- DailyNews Notion 반영 여부 확인
- DailyNews X 수동 발행 워크플로우 확인

### 후속 개선

- `scripts/healthcheck.py`가 dependency drift를 발견해도 `healthy=false`로 내리지 않는 구조 개선
- `notebooklm-automation`을 workspace gate에 포함할지 여부 결정
- 현재 다수의 untracked/modified 변경을 작업 단위별로 정리

## 관련 파일

- `pytest.ini`
- `scripts/run_workspace_smoke.py`
- `tests/test_workspace_smoke.py`
- `docs/QUALITY_GATE.md`
- `desci-platform/frontend/src/components/PricingPage.jsx`
