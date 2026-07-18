# JooPark Workspace v3.0

정적 SPA로 동작하는 개인 워크스페이스입니다. 일정, 할 일, 메모, 습관, 통계, PM 보드, 간트, 팀, 로컬 DB 카탈로그, LLM 위키 지식 베이스를 한 화면에서 관리하고 모든 사용자 데이터는 브라우저 `localStorage`에 저장합니다.

## 실행

```bash
python3 -m http.server 5178
```

브라우저에서 `http://127.0.0.1:5178/`를 엽니다. 저장과 Service Worker 검증은 `http://` 또는 secure context에서 동작합니다.

## 검증

기본 검증은 제품 회귀 중심입니다.

```bash
npm test
```

`npm test`는 정적 게이트만 순서대로 실행합니다(브라우저 불필요, 약 12초).

```bash
npm run test:unit        # 순수 헬퍼 단위 테스트
npm run lint             # node --check 문법 검사
npm run check:structure  # app.js/뷰 모듈 구조 가드
npm run check:docs       # docs/app-architecture.md 정합
npm run audit:xss        # raw() 주입 정적 감사
npm run check:vendor     # vendor SRI/라이선스 정합
npm run check:wiki       # LLM 위키 문서 게이트 17종
npm run measure:perf     # 대용량 데이터 성능 예산
npm run verify:dashboard # 대시보드 모듈 검증
```

브라우저 게이트는 두 계층입니다. `npm run verify:product`는 임시 로컬 정적 서버를 띄우고 데스크톱/모바일/상호작용/접근성 브라우저 스모크를 순차 실행한 뒤 서버를 정리합니다. `npm run test:product`는 `dist/release` 패키지를 다시 빌드해 패키지 대상 스모크를 실행합니다. 릴리스 전 전체 검증은 `npm run verify:full`(= npm test → verify:product → smoke:cockpit → test:product)입니다. 개별 스모크를 직접 실행할 때는 먼저 로컬 서버를 켭니다.

과거의 launch/publish 증거 동기화 기계(audit-release-readiness, verify-workspace, refresh-launch-readiness 등)는 2026-07-18에 `archive/meta-machine/scripts/`로 동결됐습니다. `data/`와 `autoresearch-results/`의 launch receipt JSON은 런타임(System Status)과 서비스워커 프리캐시가 읽는 동결 스냅샷으로 보존되며 더 이상 재생성되지 않습니다.

```bash
BASE_URL=http://127.0.0.1:5178 node scripts/smoke-chrome.mjs
BASE_URL=http://127.0.0.1:5178 node scripts/smoke-mobile.mjs
BASE_URL=http://127.0.0.1:5178 node scripts/smoke-interactions.mjs
BASE_URL=http://127.0.0.1:5178 node scripts/smoke-a11y.mjs
```

느린 환경에서는 `SMOKE_ROUTE_READY_TIMEOUT_MS`와 `MOBILE_SMOKE_ROUTE_READY_TIMEOUT_MS`로 route readiness diagnostics timeout을 조정할 수 있습니다. 실패 로그의 `route not ready:` JSON은 readyState, hash, visible view, view text length를 포함합니다.

## 릴리스

```bash
npm run build
node scripts/verify-release.mjs
```

`dist/release/`는 GitHub Pages, Netlify, Vercel에 그대로 올릴 수 있는 정적 패키지입니다. 패키저는 `release-manifest.json`, `release-provenance.json`, `404.html`, `_headers`, `_redirects`, `vercel.json`, `site.webmanifest`, `sw.js`, vendor 파일, data snapshot, `autoresearch-results/release-readiness-summary.json`, `autoresearch-results/verify-workspace-summary.json`을 함께 넣고 source parity를 검증합니다.

GitHub Pages 배포 템플릿은 `docs/github-pages-workflow.yml`입니다. 로컬에 설치된 workflow는 `.github/workflows/joopark-pages.yml`이고, CI smoke는 `.github/workflows/joopark-ci.yml`에서 정적 체크, 소스 브라우저 스모크, 패키지 릴리스 스모크를 분리 실행합니다. Pages build 잡은 `npm test`(정적 게이트)를 통과해야만 패키징·배포로 진행합니다.

Pages 배포는 push 트리거가 environment 보호 규칙으로 항상 거부되므로, 대상 ref를 명시한 수동 dispatch가 유일한 경로입니다: `gh workflow run --repo OWNER/REPO joopark-pages.yml -f ref=codex/joopark-workspace-release`.

## 데이터 경계

| 파일 | 성격 |
| --- | --- |
| `data/repos.json` | 포트폴리오 초기 GitHub snapshot seed |
| `data/adoption-candidates.json` | `seedScope: demo-local-snapshot`인 OSS 후보 benchmark seed |
| `data/github-project-discovery.json` | GitHub/로컬 관련 프로젝트 read-only inventory. 로컬 경로는 `relative-to-local-root`로만 보존 |
| `db-catalog.js` | 브라우저 localStorage DB 카탈로그 UI helper |
| `autoresearch-results/*.json` | 릴리스/검증 cache artifact. 런타임 proof cache로 남겨두며 외부 완료 증거 자체는 아님 |

OSS 후보의 별/포크/커밋 값은 source-backed snapshot입니다. 앱은 이를 live DB나 실시간 GitHub 동기화로 표시하지 않고, 포트폴리오 카드에 `Seed demo snapshot` 경계를 노출합니다. 후보 드리프트 감시 기계는 2026-07-18에 `archive/meta-machine/`으로 동결됐습니다.

## 주요 기능

| 메뉴 | 기능 |
| --- | --- |
| Home | 오늘 일정/할 일, 실행 큐, 운영 관제판, AutoResearch loop, 공개 준비 요약, 로컬 데이터 상태 |
| Calendar | 월간 일정, 반복 일정, 선택일 아젠다 |
| Todo | 빠른 추가, 우선순위, 마감일, 상태 필터, 삭제/undo |
| Notes | Markdown 메모, pin, 색상, XSS 소독 렌더링 |
| Habits | 7일 체크, streak, 주간 목표 |
| Stats | 전체 완료율, 요일별 완료 분포, 일정 분류 분포, 습관 streak |
| Portfolio | 프로젝트 CRUD, OSS 후보 seed, benchmark handoff |
| Kanban | 컬럼 이동, 순서 저장, 키보드 이동, 마우스/터치 drag |
| Gantt | 작업 CRUD와 일정 막대 |
| Team | 멤버 CRUD와 프로젝트 참조 정리 |
| Pipeline | 자산 × 워크스트림 파이프라인 보드, 셀 드릴다운(마일스톤·WBS·위키 딥링크) |
| DB Catalog | 로컬 인스턴스/스키마/쿼리/백업/마이그레이션 문서화 |
| LLM Wiki | 8개 카테고리 48개 마크다운 문서 지식 베이스(기초 개념~프로젝트 운영), 검색, 문서에서 할 일/메모/이슈 만들기 |
| Settings/System | 백업, 가져오기 guard, 저장 실패 recovery, dashboard receipt, release evidence, PWA 상태 |

저장 실패 시 Settings/System에 긴급 백업 다운로드와 일반 export 버튼이 표시됩니다. `workspace-storage.js`는 실패 payload를 recovery JSON으로 만들고, `storage-status-view.js`가 복구 UX를 렌더링합니다. Dashboard intelligence는 `dashboardInsights`, `dashboardResearchLoops`, `dashboardImprovementCandidates`, `dashboardDecisionReceipts`, `dashboardEvidenceSnapshots`, `dashboardHealthChecks` localStorage 컬렉션에 retention을 걸어 저장하며 JSON export/import guard와 함께 이동합니다.

Review package issue drafts keep tracker-ready metadata visible before submission. The issue sheet and smoke coverage verify `assignee`, `due`, `estimate`, `tracker-ready`, and owner/timebox fields so generated review plans can be copied into an external tracker without rewriting.

## 보안/렌더링

HTML은 `html()` 템플릿 헬퍼에서 기본 escape되고, 검토된 HTML 조각만 `raw()`로 주입합니다. Markdown은 `[marked](https://github.com/markedjs/marked) | 18.0.5`로 변환한 뒤 `[DOMPurify](https://github.com/cure53/DOMPurify) | 3.4.11`로 소독합니다. 정적 감사는 다음 명령입니다.

```bash
npm run audit:xss
```

## Vendored OSS

npm runtime dependency는 없습니다. 브라우저에서 필요한 OSS는 `vendor/`에 원본 UMD 파일로 동봉하고 `vendor/LICENSES.md`와 `package.json#vendoredDependencies`가 같은 내용을 기록합니다.

| 라이브러리 | 버전 | 라이선스 | 파일 |
| --- | --- | --- | --- |
| Fuse.js | 6.6.2 | Apache-2.0 | `vendor/fuse.min.js` |
| marked | 18.0.5 | MIT | `vendor/marked.umd.js` |
| DOMPurify | 3.4.11 | Apache-2.0 / MPL-2.0 | `vendor/purify.min.js` |

검증:

```bash
npm run check:vendor
```

## 성능 기준

대량 데이터 기준은 `scripts/measure-large-data-performance.mjs`에 고정되어 있습니다. 현재 기준은 Kanban model 5,000건, Kanban render 5,000건, storage JSON 2,500건입니다.

```bash
npm run measure:perf
```

## 구조

`app.js`는 아직 SPA orchestration을 담당하지만 주요 view/helper는 별도 파일로 분리되어 있습니다. 파일별 책임 맵은 `docs/app-architecture.md`에 있고, 구조 guard는 line budget, action dispatch map, module extraction 상태를 확인합니다.

```bash
npm run check:structure
npm run check:docs
```

주요 runtime helpers: `workspace-seed-data.js`, `home-view.js`, `dashboard-view.js`, `dashboard-insights-engine.js`, `dashboard-prioritization.js`, `dashboard-autoresearch-loop.js`, `dashboard-evidence-receipts.js`, `dashboard-storage.js`, `llm-wiki-view.js`, `calendar-view.js`, `todo-view.js`, `notes-view.js`, `habits-view.js`, `stats-view.js`, `portfolio-view.js`, `kanban-view.js`, `gantt-view.js`, `team-view.js`, `pipeline-view.js`, `workspace-storage.js`, `storage-status-view.js`, `settings-view.js`, `system-status-view.js`, `command-palette.js`, `keyboard-shortcuts.js`, `interaction-setup.js`, `event-reminders.js`, `footer-clock.js`, `db-catalog.js`, `runtime-error-boundary.js`, `pwa-runtime.js`, `ops-runtime-loader.js`.

System Status의 `Ops runtime diagnostics` 패널은 `ops-runtime-loader.js`의 지연 로드 상태를 그대로 노출합니다. `loaded lazy files`, `ready groups`, pending/failed count, group별 release/review 로드 상태가 smoke와 release audit에서 검증됩니다.

## 아카이브

장문 launch/proof/meta 운영 기록은 루트 README에서 제거했습니다. 기존 전문은 `archive/meta-machine/README.full-before-slim.md`에 보존되어 있고, 반복 product loop 기록은 `docs/product-direction.md`, 이전 개선 로그는 `docs/improvement-roadmap.md`에 남아 있습니다. 이 아카이브는 현재 앱 실행 경로가 아니라 이력 확인용입니다.
