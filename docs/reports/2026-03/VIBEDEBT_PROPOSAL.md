# VibeDebt: 기술 부채 자동 진단 시스템 도입 제안서

**작성일**: 2026-03-31
**대상**: AI Projects Workspace (17 active units, 254 Python files, 6K+ TS/JS files)
**상태**: 제안 → 구현 대기

---

## 1. 도입 필요성

### 1.1 현재 워크스페이스 진단

이 워크스페이스는 바이브 코딩(Vibe Coding) 방식으로 빠르게 성장했으며, 현재 **17개 활성 유닛**이 운영 중입니다.
기존 QC 인프라는 상당히 성숙한 편이나, **기술 부채 정량화**가 누락된 상태입니다.

| 인프라 영역 | 현재 상태 | 부채 관리 기여도 |
|------------|----------|----------------|
| Smoke Tests (14 checks) | ✅ 성숙 | 기능 회귀만 감지, 부채 미측정 |
| CI/CD (8 workflows) | ✅ 양호 | 빌드/린트 통과 여부만 판단 |
| Prometheus/Grafana (6 dashboards) | ✅ 양호 | 런타임 메트릭만 수집 |
| Pre-commit (9 hooks) | ✅ 양호 | 포맷/시크릿만 차단 |
| Ruff Linter | ✅ 양호 | 스타일 위반만 감지 |
| **코드 복잡도 분석** | ❌ 없음 | — |
| **기술 부채 정량화** | ❌ 없음 | — |
| **타입 체킹 (mypy/pyright)** | ❌ 없음 | — |
| **커버리지 강제** | ⚠️ 60% 권고 (미차단) | — |

### 1.2 바이브 코딩 특유의 부채 패턴 — 우리 워크스페이스에서 관찰된 증거

| 부채 패턴 | 우리 워크스페이스 증거 | 리스크 |
|-----------|---------------------|--------|
| AI 생성 코드 중복 | 프로젝트 간 유사 패턴 반복 (config 로딩, HTTP 클라이언트) | 수정 시 N곳 동시 변경 필요 |
| 컨텍스트 단절 | DailyNews gray-zone closure에 3세션 소요 | 레거시 호환 레이어 잔존 |
| 빠른 프로토타입 고착화 | TODO/FIXME 19개 파일에 산재 | 임시 코드가 프로덕션 경로에 잔류 |
| 문서-코드 불일치 | 월 12+ QC 리포트 생성, 자동 동기화 없음 | 문서가 현실과 괴리 |
| 모듈화 부족 | `packages/shared`에 관측성/프로파일링 모듈 없음 | 횡단 관심사가 각 프로젝트에 분산 |

### 1.3 정량적 리스크 추정

현재 워크스페이스의 **Technical Debt Ratio(TDR)** 추정:

```
수정 비용 추정 = 복잡도 위반 함수 수 × 평균 리팩토링 시간(30분)
               + TODO/FIXME 항목(~50개) × 평균 해결 시간(1시간)
               + 타입 안전성 미비 파일(254 Python) × 타입 추가(15분)
               ≈ 150-200 인시 (개발자 1명 기준 약 5주)

이자 비용 = 주당 추가 디버깅 시간 ≈ 3-5시간 (컨텍스트 재구축, 회귀 추적)
```

**결론**: 현재 부채 수준은 관리 가능하나, 자동 측정 없이는 임계점 도달 시점을 예측할 수 없음.

---

## 2. 도입 목표

### 기존 인프라 위에 얹는 3단계 점진적 확장

우리 시스템에는 이미 smoke test, CI, Grafana가 있으므로 **새 도구를 별도로 설치하는 것이 아닌, 기존 파이프라인에 부채 측정 레이어를 추가**하는 방식으로 진행합니다.

```
Phase 1: VibeDebt Scanner (ops/scripts/)         ← 이번 세션에서 구현
         기존 healthcheck.py / smoke.py 패턴을 따르는 CLI 도구
         radon + custom metrics → JSON 리포트

Phase 2: CI 자동화 (.github/workflows/)           ← 이번 세션에서 구현
         기존 workspace-smoke.yml 패턴과 동일한 구조
         주간 자동 실행 + PR diff 분석

Phase 3: Grafana Dashboard (ops/monitoring/)      ← 이번 세션에서 구현
         기존 대시보드 6개와 동일 패턴으로 추가
         부채 추이 시각화
```

---

## 3. Phase 1: VibeDebt Scanner

### 3.1 설계 원칙

- **Zero new dependencies for basic mode**: Python stdlib + radon (1개 추가)만 사용
- **기존 패턴 준수**: `healthcheck.py`, `run_workspace_smoke.py`와 동일한 CLI 구조
- **workspace-map.json 연동**: 스캔 대상을 워크스페이스 맵에서 자동 결정
- **JSON 출력**: `var/debt/` 디렉토리에 시계열 데이터 축적

### 3.2 측정 지표

| 지표 | 도구 | 임계값 | 근거 |
|------|------|--------|------|
| Cyclomatic Complexity | radon cc | ≤10 per function | 유지보수성 연구 표준 |
| Maintainability Index | radon mi | ≥20 (A/B grade) | SQALE 기준 |
| Code Duplication | custom (hash-based) | ≤5% across project | 수정 비용 선형 증가 |
| TODO/FIXME Density | grep count | ≤2 per 1000 LOC | 임시 코드 잔류 지표 |
| Test Coverage Gap | pytest --cov delta | ≥60% enforced | 기존 목표 강제화 |
| Type Safety Score | file-level annotation % | 점진적 향상 추적 | 런타임 오류 예방 |

### 3.3 부채 점수 공식

```python
# Technical Debt Score (0-100, 낮을수록 건강)
debt_score = (
    0.30 * complexity_violation_ratio    # 복잡도 위반 함수 비율
  + 0.25 * (1 - test_coverage / 100)     # 커버리지 부족률
  + 0.20 * duplication_ratio             # 코드 중복률
  + 0.15 * todo_density_normalized       # TODO 밀도 (정규화)
  + 0.10 * (1 - type_annotation_ratio)   # 타입 미비율
) * 100

# TDR (Technical Debt Ratio)
tdr = estimated_remediation_hours / total_development_hours * 100
```

**건강 등급**:
- A (0-15): 건강 — 정기 모니터링만
- B (16-30): 주의 — 주간 리뷰 권장
- C (31-50): 경고 — 스프린트에 부채 청산 태스크 배정
- D (51+): 위험 — 기능 개발 중단, 리팩토링 우선

---

## 4. Phase 2: CI 자동화

### 4.1 워크플로우 설계

```yaml
# .github/workflows/tech-debt-audit.yml
# 트리거: 주간 월요일 + PR (packages/shared, automation/ 변경 시)
# 출력: GitHub Step Summary + JSON artifact + PR 코멘트
```

### 4.2 PR 게이트 규칙

| 조건 | 동작 | 근거 |
|------|------|------|
| 새 함수의 CC > 15 | ⚠️ Warning comment | 절대 차단 아님, 인지용 |
| 프로젝트 TDR > 10% 증가 | ⚠️ Warning comment | 급격한 부채 증가 경고 |
| 프로젝트 TDR > 30% | 🚫 Required check fail | 심각한 부채 누적 차단 |

> **운영 입장**: smoke test와 동일하게 "경고 우선, 차단은 심각한 경우만". 바이브 코딩의 속도를 해치지 않음.

---

## 5. Phase 3: Grafana Dashboard

기존 `ops/monitoring/grafana/dashboards/` 패턴과 동일하게 JSON 프로비저닝.

### 5.1 패널 구성

| 패널 | 데이터 소스 | 시각화 |
|------|-----------|--------|
| Workspace Debt Score (종합) | var/debt/*.json | Gauge (0-100) |
| Per-Project TDR 추이 | var/debt/*.json | Time series |
| Complexity Hotspot Top 10 | radon output | Table |
| TODO/FIXME Trend | grep count history | Time series |
| Coverage Delta | pytest-cov history | Bar chart |
| 부채 등급 이력 | computed | Stat panel |

---

## 6. 아이디어 매핑: 3개 제안 → 우리 시스템 적용

사용자가 제안한 3개 아이디어를 우리 워크스페이스에 맞게 재해석합니다.

### VibeDebt Auditor → `ops/scripts/tech_debt_scanner.py`

| 원안 | 우리 적용 | 이유 |
|------|----------|------|
| SonarQube + LangChain | radon + custom Python | 17개 유닛에 SonarQube 도입은 과잉; radon이면 충분 |
| VS Code 확장 | CLI + CI 통합 | 이미 pre-commit/CI 파이프라인이 성숙 |
| 리팩토링 PR 자동 생성 | 부채 리포트 + 수동 판단 | 자동 PR은 바이브 코딩 흐름을 방해 |

### VibeDoc Sync → 기존 HANDOFF.md/TASKS.md 자동화 강화

| 원안 | 우리 적용 | 이유 |
|------|----------|------|
| Obsidian 지식 그래프 | HANDOFF.md + CONTEXT.md 자동 갱신 | 이미 핸드오프 체계가 작동 중 |
| ADR 자동 생성 | 부채 스캔 결과를 QC 리포트에 통합 | 기존 `docs/reports/` 패턴 활용 |
| Neo4j GraphRAG | workspace-map.json 기반 의존성 추적 | 그래프 DB는 과잉 |

### VibeGuard Dashboard → Grafana 대시보드 확장

| 원안 | 우리 적용 | 이유 |
|------|----------|------|
| Next.js + Vercel SaaS | Grafana 패널 추가 | 이미 6개 대시보드 운영 중 |
| 별도 웹 대시보드 | 기존 Prometheus 파이프라인 | 인프라 중복 방지 |
| "이자 비용" 시각화 | TDR 추이 패널 | 동일 개념, 기존 도구로 |

---

## 7. 구현 로드맵

### 이번 세션 (즉시 구현)

- [x] `ops/scripts/tech_debt_scanner.py` — CLI 스캐너
- [x] `.github/workflows/tech-debt-audit.yml` — 주간 CI
- [x] `ops/monitoring/grafana/dashboards/tech-debt.json` — Grafana 대시보드

### Week 1 후속

- [ ] `radon` 의존성 추가 (`pyproject.toml` dev-dependencies)
- [ ] 첫 번째 전체 스캔 실행 → 베이스라인 리포트 생성
- [ ] 부채 점수 임계값 팀 합의 (현재 제안: A/B/C/D 등급)

### Week 2-4 확장

- [ ] PR 게이트 활성화 (warning only 모드로 시작)
- [ ] mypy strict mode 점진적 도입 (프로젝트별)
- [ ] 커버리지 60% floor 강제 (`--cov-fail-under=60`)
- [ ] 월간 부채 트렌드 리포트 자동 생성

---

## 8. 비용-효과 분석

| 항목 | 도입 비용 | 기대 효과 |
|------|----------|----------|
| 스캐너 스크립트 | 1회 개발 (이번 세션) | 수동 리뷰 3-5시간/주 → 자동화 |
| CI 워크플로우 | 1회 설정 (이번 세션) | PR 리뷰 시 부채 인지 자동화 |
| Grafana 대시보드 | 1회 설정 (이번 세션) | 부채 추이 가시화, 임계점 조기 경고 |
| radon 의존성 | pip install 1줄 | 복잡도 분석 정확도 향상 |
| **총 운영 비용** | **월 ~30분** (리포트 리뷰) | **주 3-5시간 절약** (디버깅/컨텍스트 재구축 감소) |

**ROI**: 첫 달 내 투자 회수, 이후 순 효익.

---

## 9. 결론

> 바이브 코딩의 속도를 유지하면서 부채를 관리하는 핵심은 **마찰 최소화(low-friction)**입니다.
>
> 이 제안은 새로운 도구를 도입하는 것이 아니라, **이미 검증된 인프라(smoke test, CI, Grafana) 위에
> 부채 측정 레이어를 한 겹 추가**하는 것입니다. 개발자는 기존 워크플로우를 변경할 필요 없이,
> 부채 점수를 자연스럽게 인지하게 됩니다.
