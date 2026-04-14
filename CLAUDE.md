# AI Projects Workspace

Multi-project workspace for product apps, automation pipelines, MCP servers, and shared tooling.

## Canonical layout

- `apps/desci-platform`
- `apps/AgriGuard`
- `apps/dashboard`
- `automation/DailyNews`
- `automation/getdaytrends`
- `automation/content-intelligence`
- `mcp/*`
- `packages/shared`
- `ops/scripts`
- `ops/monitoring`
- `docs`
- `archive`
- `var`

## Bootstrap contract

Run this after clone and before using legacy paths:

```bash
python bootstrap_legacy_paths.py
```

This generates local compatibility aliases such as:

- `scripts/` -> `ops/scripts/`
- `DailyNews/` -> `automation/DailyNews/`
- `getdaytrends/` -> `automation/getdaytrends/`
- `shared/` -> `packages/shared/`

## Main projects

| Unit | Path | Purpose |
| --- | --- | --- |
| BioLinker API | `apps/desci-platform/biolinker` | RFP matching and research backend |
| DeSci frontend | `apps/desci-platform/frontend` | Web UI for the DeSci platform |
| DeSci contracts | `apps/desci-platform/contracts` | Smart contracts |
| AgriGuard backend | `apps/AgriGuard/backend` | Supply chain tracking API |
| AgriGuard frontend | `apps/AgriGuard/frontend` | Supply chain web UI |
| Dashboard | `apps/dashboard` | Workspace dashboard app |
| DailyNews | `automation/DailyNews` | News and publishing automation |
| GetDayTrends | `automation/getdaytrends` | Trend analysis and content generation |

## Root commands

```bash
python ops/scripts/run_workspace_smoke.py --scope all
python ops/scripts/healthcheck.py
npm run build:all
npm run test:all
npm run lint:all
npm run typecheck:all
docker compose config
```

## Local development

### BioLinker

```bash
cd apps/desci-platform/biolinker
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### DeSci frontend

```bash
cd apps/desci-platform/frontend
npm install
npm run dev
```

### AgriGuard backend

```bash
cd apps/AgriGuard/backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

### GetDayTrends

```bash
cd automation/getdaytrends
pip install -r requirements.txt
python main.py --one-shot --dry-run --verbose
```

### DailyNews

```bash
cd automation/DailyNews
pip install -e .           # pyproject.toml is source of truth for deps
python -m pytest tests/ -q --tb=short   # 180+ tests, ~45s
python scripts/run_daily_news.py --mode full
```

- Package: `src/antigravity_mcp/`, entry point `antigravity-mcp`
- State: SQLite at `data/pipeline_state.db` (WAL mode)
- `tests/test_qc_pipeline_fix.py` queries live DB — may flake on stale data
- Linter auto-adds helper functions on save; verify edits persisted

## Shared and ops paths

- `packages/shared` for common LLM, telemetry, and utility modules
- `ops/scripts` for orchestration, smoke, healthcheck, and reporting utilities
- `ops/monitoring` for Grafana and Prometheus config
- `ops/nginx` for shared nginx assets
## 수정 모드 프로토콜 (Defensive Edit)

기존 코드를 수정·리팩토링할 때 반드시 아래 순서를 따른다:

1. **영향 범위 먼저 보고**
   - 직접 수정 파일, 간접 영향 파일, 변경 불가 파일을 명시
   - `shared/` 모듈 수정 시 소비자 프로젝트 목록 필수
2. **수정 전 테스트 확인**: 수정 대상에 기존 테스트가 있으면 먼저 실행
3. **한 커밋 = 한 논리 변경**: 기능 추가 + 리팩토링 분리
4. **diff 최소화**: 3개 이상 파일 동시 수정 시 계획을 먼저 보고

### 금지 (명시적 지시 없이)

- public API 시그니처 변경
- DB 스키마 변경 (테이블/컬럼 추가·삭제)
- 의존성 추가·삭제 (requirements.txt, pyproject.toml)
- `.github/workflows/` 변경
- 보안 관련 파일 (auth.py, .env, .gitleaks.toml)
- generated/auto 파일

## Smart Continue (바이브 자동 진행)

"해줘", "진행해", "계속", "다음", "ㄱㄱ" 등 짧은 진행 명령 시:

### 액션 결정 순서

1. `next-actions.md`의 첫 `[safe_auto]` 항목 확인
2. `session-history/` 최신 파일의 "다음 TODO" 참조
3. 사용자 피드백 미반영 사항 → 확인된 문제점
4. 개선 축 자동 판단: 버그 수정 > 구조 개선 > 기능 확장 > 품질 향상

### 자동 진행 조건 (전부 만족)

- 같은 기능/모듈 경계 내 작업
- 변경 대상 7파일 이하, 순수 추가 코드 ~250줄 이하
- 같은 개선 축 3회 연속 후 강제 전환

### 확인 필요 (한 줄 승인 요청)

- 새 패키지/라이브러리 설치 (pyproject.toml, requirements.txt 변경)
- DB 스키마 변경 (테이블 추가/삭제/컬럼 수정)
- 인증/보안/권한 로직 변경
- 공개 API·인터페이스 계약 변경
- 인프라/CI 설정 변경
- 기존 파일 3개 이상 동시 구조 변경

### 실행 프로토콜

1. Self-Validation: 실질적 개선인가? 기존 기능 깨뜨리지 않는가?
2. 2~3줄 브리핑 후 바로 생성 (질문 금지)
3. 결과 끝에 변경 요약 부착:
   - 📌 변경사항 + ✅ 확인한 것 + 🔜 다음 safe step + ⚠️ 승인 필요

### 금지 사항

- "뭐부터 할까요?" 질문
- 실질적 변경 없이 버전만 올리기 (변수명/주석만 변경은 개선 아님)
- 파일 삭제 (사용자 명시 요청만), 시크릿 하드코딩

### Persistent Memory

- `next-actions.md` — 승인된 작업 큐 (`[safe_auto]` / `[needs_approval]`)
- `LESSONS.md` — 크로스 세션 교훈 축적 (5회차+ 또는 반복 패턴 시)
- 3파일 합산 150줄 이내 유지, 사용자 승인 없이 자동 수정 금지

## 세션 위생 (Session Hygiene)

### 시간 경고
- 세션이 30분 이상 지속되면: "새 세션 시작을 권장합니다" 알림
- 주제가 2회 이상 전환되면: "컨텍스트 분리를 위해 새 세션이 안전합니다" 알림

### 세션 종료 전 필수
- 변경된 파일 목록 + diff 크기 요약
- 이전 수정과 현재 수정이 충돌할 가능성이 있으면 명시 경고
- `next-actions.md` 갱신 (완료 항목 제거, 새 TODO 추가)

### PR 셀프 리뷰 (머지 전)
변경이 3파일 이상이거나 shared/ 수정을 포함하면 아래 8개 관점으로 셀프 리뷰:
1. 계약 위반: public API, 타입 시그니처 변경 여부
2. 부수 효과: 의도하지 않은 다른 동작 영향
3. 테스트 커버리지: 변경된 코드 중 테스트 없는 경로
4. 에러 핸들링: 새 실패 경로의 처리 여부
5. 보안: 하드코딩 비밀, 열린 권한, 입력 미검증
6. 의존성: 새 의존성과 그 이유
7. 되돌림: revert 시 깨끗하게 되돌아가는지
8. 네이밍: 변수/함수/파일 이름이 변경을 반영하는지

결과를 🔴 반드시 수정 / 🟡 권장 / 🟢 괜찮음으로 분류.

## Notes

- `workspace-map.json` is the source of truth for active units and legacy aliases
- `archive/` is excluded from normal smoke and package discovery
- `var/` holds runtime data, logs, snapshots, and generated smoke output

