# ENHANCEMENT_LOG — 무한 고도화 루프 누적 기록

> 각 반복: 무엇을 시도했나 · 지표 결과 · 채택/기각 사유 · 출처·라이선스.
> 백로그 정의는 `docs/enhancement-tasks.md`. 작업 한 줄 기록은 `WORKLOG.md`.

---

## 0. 상태 재검증 (2026-06-09) — 문서 drift 교정

루프 시작 시 `docs/enhancement-tasks.md`의 task 상태가 실제 코드보다 뒤처져 있어 실파일을 재조사함. 발견:

- **T2 (브라우저 스모크 게이트)** — 이미 완료. `scripts/verify-product-smoke.mjs` 존재, `package.json#test`와 `joopark-ci.yml`의 `browser-smoke` job에 포함.
- **T9 (CI 강화)** — 이미 완료. `joopark-ci.yml`에 `concurrency`(cancel-in-progress), `setup-node` npm 캐시, 3개 분리 job(static/browser/release) 모두 존재.
- **T4 (CSP)** — 이미 완료. `index.html`에 엄격한 CSP meta(`default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'` …) 존재.
- **T11 (인라인 외부화)** — 인라인 `<script>` 0개(45개 모두 `src=`). **단 SRI/vendor 해시 고정은 미완** — `check-vendor-honesty.mjs`에 해시 검증 없음.
- **T1, T3** — 완료(문서 기록과 일치).
- **구조 가드** — 통과, app.js 12,189줄, 실패·경고 0.

→ 실제 남은 미완: T5·T6·T7·T8 심화·T10·T11(SRI 부분)·T12, 그리고 아래에서 새로 발굴한 **perf 게이트 flakiness**.

---

## 1. perf 게이트 flakiness 제거 (best-of-N 추정기) — 채택 ✅

- **영역(새 발굴)**: 테스트 신뢰성 / DX. 백로그에 없던 항목 — 베이스라인 `npm test` 실행 중 `measure:perf`가 "kanban render 906.61ms > 900ms"로 무작위 red가 되는 것을 발견.
- **현재 문제**: `scripts/measure-large-data-performance.mjs`가 `renderKanbanHTML`을 **단일 샘플** wall-clock으로 측정 후 절대 임계(900ms)와 비교. 측정 노이즈는 한쪽(시간 증가)으로만 작용해 머신 부하에 따라 크게 흔들림.
- **성공 지표**: 동일 입력 반복 측정의 **변동폭**(분산) — 작을수록 우월. 회귀 민감도(임계 헤드룸)는 유지해야 함.
- **A안**: 임계를 900→1500ms로 상향. 단순하나 임의적이고 진짜 회귀를 숨김.
- **B안 (채택)**: 워밍업 2회(JIT 예열, 폐기) + 5회 측정 중 **최소값(best-of-N)** 을 게이트 값으로 사용. 노이즈가 한쪽이므로 min이 진짜 계산 비용에 안정적으로 수렴. 임계값(900/150/250)은 **그대로 유지** → 회귀 민감도 손실 0. median·samples를 요약에 노출.
- **측정 결과**:
  - 변경 전(단일 샘플): kanbanRenderMs **334 / 454 / 666 / 697 / 906ms** (변동 ~2.7배, 900 임계 초과로 flake 발생).
  - 변경 후(best-of-N, 6회 실행): **82.6 / 100.1 / 83.3 / 85.1 / 82.6 / 92.9ms** (변동 ~1.2배). 워밍업으로 절대값도 안정. 임계 900ms 대비 ~9배 헤드룸 → 어떤 현실적 CI 러너에서도 flake 없음.
- **회귀 검증**: `test:unit·lint·check:structure·audit:xss·check:vendor·measure:perf` 전부 green. 브라우저 스모크는 런타임 미변경이라 무관.
- **보류(검증 필요)**: 임계값을 더 조여 회귀 민감도를 높이는 건 **CI 절대 ms 실측 전엔 보류**(섣불리 조이면 느린 CI에서 flake 재발 위험 = 본 작업 목표와 충돌). CI 베이스라인 ms 관측 후 후속.
- **출처/라이선스**: 외부 코드 차용 없음. "min-of-N으로 노이즈 있는 벤치마크를 안정화"는 일반적 벤치마킹 관행(독자 구현).
- **파일**: `scripts/measure-large-data-performance.mjs`.

## 2. 운영 런타임 순수 함수 단위 테스트 (T10) — 채택 ✅

- **영역**: 테스트 / 안정성. 백로그 T10.
- **현재 문제**: `review-issue-payload.js`·`review-execution-checklist.js`·`review-result-state.js` 등 운영 런타임의 마크다운 생성·검증·정규화 로직에 단위 테스트 0건. 회귀가 조용히 통과.
- **성공 지표**: 순수 함수 ≥6개 커버 + 빈/잘못된 shape 거부 assert 포함, `test:unit` 녹색(DoD).
- **작업**: `scripts/test-pure-helpers.mjs`에 vm 기반 3개 테스트 추가 —
  - 실행 체크리스트: 문자열/객체 항목 정규화, 진행률 산술·한국어 라벨 경계, GitHub task-list 마크다운, dedup+8개 cap, 파싱 불가 시 빈 배열, 필수 dep 누락 throw.
  - 이슈 페이로드: 마크다운 섹션 추출(존재/부재/빈 입력), 운영 준비도 기본값, due-date 산술(0·비유한 거부), 본문 섹션 조립, 필수 dep 누락 throw.
  - 결과 상태: repair 스냅샷 fail/empty/기타 상태 경계, 스냅샷 없을 때 null, 필수 dep 누락 throw.
- **함정 발견**: vm 컨텍스트 반환 객체/배열은 prototype이 달라 `assert.deepStrictEqual` 실패 → 필드별/`join`/`length` 비교로 교정(기존 테스트도 동일 패턴).
- **결과**: `test:unit` 녹색. 순수 함수 14개+ 커버, 모든 모듈에 dep-거부·경계 assert 포함.
- **출처/라이선스**: 외부 차용 없음. 기존 `loadRuntime` vm 패턴 재사용.
- **파일**: `scripts/test-pure-helpers.mjs`.

## 3. T5-T12 완료 패스 (2026-06-09) — 채택 ✅

- **영역**: 구조 / 성능 / 보안 / 운영 문서. 백로그 T5-T12.
- **작업**:
  - T5: `ops-runtime-loader.js` 추가. release/review/operations 계열 16개 스크립트를 route 진입 시 지연 로드. 초기 runtime script는 44개에서 29개로 감소.
  - T6: `workspace-seed-data.js`, `home-view.js` 분리. `app.js` 구조 guard 기준 10,864줄, 상한 11,000줄로 통과.
  - T7: Kanban/Todo/DB catalog 대량 리스트 render cap과 virtual note를 적용하고 `measure:perf`로 5,000 issue/2,500 storage item 기준을 검증.
  - T8: backup import guard가 string clamp, enum fallback, nullable date, 배열 cap, record limit을 정규화/거부.
  - T11: vendor 3종에 SHA-256 SRI를 고정하고 `check-vendor-honesty.mjs`가 `package.json`과 `index.html`을 함께 검증.
  - T12: `docs/app-architecture.md`, README 구조 절, `scripts/check-doc-architecture.mjs`, CI static job을 연결.
- **측정 결과**:
  - `check:structure`: pass, `app.js` totalLines 10,864, maxAppLines 11,000.
  - `check:docs`: pass, initialRuntimeScripts 29, lazyRuntimeScripts 16.
  - `measure:perf`: pass, kanbanRenderedCards 320, kanbanVirtualNotes 4, storageBytes 811,971.
  - `smoke-release`: pass, release package/manifest/header/fallback/desktop/mobile/interaction/delete-undo/a11y.
  - `package-release`: pass, files 80, 약 3.04MB.
  - `verify-release dist/release`: pass, files 80, sourceDirty true, sourceParityFiles 60, provenanceDependencyCount 57.
- **회귀 검증**: `npm run test:unit`, `npm run lint`, `npm run check:structure`, `npm run check:docs`, `npm run audit:xss`, `npm run check:vendor`, `npm run measure:perf`, `node scripts/verify-product-smoke.mjs`, `node scripts/smoke-release.mjs`, `node scripts/package-release.mjs`, `node scripts/verify-release.mjs dist/release` 통과.
- **출처/라이선스**: 외부 코드 차용 없음. 기존 로컬 모듈 패턴과 Node 표준 API만 사용.
- **파일**: `app.js`, `ops-runtime-loader.js`, `workspace-seed-data.js`, `home-view.js`, `kanban-view.js`, `todo-view.js`, `db-catalog.js`, `backup-import-guards.js`, `scripts/*`, `docs/app-architecture.md`, `docs/enhancement-tasks.md`, `README.md`.
