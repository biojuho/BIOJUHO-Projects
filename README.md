# JooPark Workspace v3.0

정적 SPA로 동작하는 개인 워크스페이스입니다. 일정, 할 일, 메모, 습관, 통계, PM 보드, 간트, 팀, 로컬 DB 카탈로그를 한 화면에서 관리하고 모든 사용자 데이터는 브라우저 `localStorage`에 저장합니다.

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

`npm test`는 아래 순서로 실행됩니다.

```bash
npm run test:unit
npm run lint
npm run check:structure
npm run audit:xss
npm run check:vendor
npm run measure:perf
npm run verify:product
npm run test:product
```

`npm run verify:product`는 임시 로컬 정적 서버를 띄우고 데스크톱/모바일/상호작용/접근성 브라우저 스모크를 순차 실행한 뒤 서버를 정리합니다. 개별 스모크를 직접 실행할 때는 먼저 로컬 서버를 켭니다.

기본 `npm run verify`는 `node scripts/verify-workspace.mjs` runner로 release gate만 `--format=summary`로 실행합니다. `npm run verify:full`은 full evidence sync로 `launch_readiness_refresh`, `product_loop_summary_sync`, `productLoopGateParityReady`, `productLoopPublishParityReady`, `summarySyncReady`, `nextCandidatesReady`, `nextCandidateListReady`, `latestExperiment`, `latestDirectionLoop`, `latestDirectionExperiment`, `latestDiscoveryExperiment`, `directionLoopSyncReady`, `latestDirectionExperimentReady`, `latestDiscoveryExperimentReady`를 `autoresearch-results/verify-workspace-summary.json`과 System Status receipt에 남깁니다. `npm run refresh:launch-readiness`와 `node scripts/sync-product-loop-summary.mjs --write --markdown`은 여전히 개별 복구 명령입니다.

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

GitHub Pages 배포 템플릿은 `docs/github-pages-workflow.yml`입니다. 로컬에 설치된 workflow는 `.github/workflows/joopark-pages.yml`이고, CI smoke는 `.github/workflows/joopark-ci.yml`에서 정적 체크, 소스 브라우저 스모크, 패키지 릴리스 스모크를 분리 실행합니다. 후보 drift 확인 템플릿은 `docs/github-drift-watch-workflow.yml`입니다.

수동 dispatch가 허용된 상태에서도 Pages 배포는 대상 ref를 명시해 실행합니다: `gh workflow run --repo OWNER/REPO joopark-pages.yml -f ref=codex/joopark-workspace-release`.

Launch-readiness evidence는 `npm run refresh:launch-readiness`로 갱신합니다. 이 명령은 `scripts/refresh-launch-readiness.mjs`를 실행해 `data/launch-readiness-refresh.json`과 `data/launch-readiness-refresh.md`를 다시 쓰고, `commandCoverage=6`, `decision=keep_b`, `evidenceFreshnessStatus=fresh`, `evidenceMaxAgeHours=24`, `sourceArtifactCount=6`, `outputQualitySourceInputCount=11`, `latestGate`, `outputQualityGateTraceability`, `safeToDispatch`, `readyForExternalClaim`, `dispatchCommandDisposition`, `activeDispatchCommandCount`, `dispatchCommandReferenceCount`, 그리고 `nextAction` 상태를 한 영수증에 남깁니다. 원본 `suggestedDispatchCommandCount`는 dispatch plan provenance/reference로 보존하고, proof-ready 상태에서는 `dispatchCommandDisposition=not_applicable_after_launch_proof` 및 `activeDispatchCommandCount=0`으로 표시해 실행 후보가 아님을 분리합니다. System Status의 `readiness receipt 복사`는 `readyForExternalClaim=true` 전에는 dispatch나 외부 완료 claim을 막는 guard를 그대로 복사하고, pass 상태에서는 `share_launch_proof` 명령을 다음 공유 액션으로 노출합니다.

Publish evidence guard는 `repoEvidenceReady, evidenceFresh, postPublishEvidenceReady`를 공개 claim의 최소 입력으로 표시합니다. Stop condition: do not post public launch copy, archive proof, or claim readyForExternalClaim until all six evidence fields are live, fresh, linked, successful, and readyForExternalClaim=true.

`node scripts/audit-release-readiness.mjs --format=summary`의 `JooPark Release Readiness Summary`는 `External Claim Guard` 아래에 구조화된 `completionAudit` 상태를 함께 내보냅니다. System Status의 Release gate cache 패널과 복사 receipt도 `completionAudit`, `launchCompletionAchieved`, `blockedSignals`를 노출합니다. `launchCompletionAchieved=false`, `readyForExternalClaim=false`, `blockedSignals`가 남아 있으면 release gate가 pass여도 외부 출시 완료 claim은 금지됩니다.

Remote workflow file check는 외부 dispatch 전에 default branch의 workflow YAML이 로컬 템플릿과 같은지 확인하는 guard입니다. 현재 확인 명령은 `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write`이고, 결과는 `data/remote-workflow-file-check.json` 및 System Status의 `Remote workflow file check` 패널에 표시됩니다. `remoteWorkflowFilesReady`가 false이면 `remoteMatchesTemplate`, `remoteBlobSha`, `githubEditFileUrl`, `installAction`, `workflowScopeApprovalHandoff`, `workflowScopeInstallBlocked`, `device-code approval URL`, `one-time device code 저장 금지` 상태를 먼저 확인합니다.

Remote workflow install packet은 System Status에서 `Remote workflow install packet` / `install packet 복사`로 공유합니다. 이 패킷은 `GitHub UI fallback`, `GitHub edit-file URL`, `githubEditFileUrl`, `replace_existing_remote_file`, `remoteBlobSha`, `Post-install verification checklist`, `remoteWorkflowFilesChecked: true`, `remoteWorkflowVisibilityReady: true`, `allDispatchReady: true`를 함께 담아, 없는 파일 생성과 기존 파일 교체를 분리합니다. CLI 설치가 승인된 경우에만 `node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify`를 사용하고, 그 전에는 GitHub UI에서 default branch 파일을 편집한 뒤 다시 check 명령을 실행합니다.

Post-install proof parser는 System Status의 로컬 붙여넣기 검증 도구입니다. `placeholder` 템플릿이나 안내문은 `not dispatch approval`로 남기고, 실제 post-install proof를 붙여넣었을 때만 `postInstallProofParserCoverage=1`, `Fields detected: 6/6` 상태를 표시합니다. Missing field repair hints: `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write`, `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write`, `node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown`. 필수 필드는 `pages_workflow_commit`, `drift_workflow_commit`, `remote_parity_proof`, `actions_visibility_proof`, `dispatch_readiness_proof`, `handoff_verifier_proof`입니다.

## 데이터 경계

| 파일 | 성격 |
| --- | --- |
| `data/repos.json` | 포트폴리오 초기 GitHub snapshot seed |
| `data/adoption-candidates.json` | `seedScope: demo-local-snapshot`인 OSS 후보 benchmark seed |
| `data/github-project-discovery.json` | GitHub/로컬 관련 프로젝트 read-only inventory. 로컬 경로는 `relative-to-local-root`로만 보존 |
| `db-catalog.js` | 브라우저 localStorage DB 카탈로그 UI helper |
| `autoresearch-results/*.json` | 릴리스/검증 cache artifact. 런타임 proof cache로 남겨두며 외부 완료 증거 자체는 아님 |

OSS 후보의 별/포크/커밋 값은 source-backed snapshot입니다. 앱은 이를 live DB나 실시간 GitHub 동기화로 표시하지 않고, 포트폴리오 카드에 `Seed demo snapshot` 경계를 노출합니다. 최신성 확인은 아래 명령으로 분리합니다.

```bash
node scripts/check-candidate-freshness-drift.mjs --snapshot-only
node scripts/check-candidate-freshness-drift.mjs --live
node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift
```

GitHub 관련 프로젝트 전수 확인은 읽기 전용 산출물로 분리합니다. 이 명령은 로컬 `~/Desktop` 하위 Git 체크아웃과 `biojuho` GitHub 저장소 목록을 수집해 `data/github-project-discovery.json` 및 `.md`에 남기며, push·deploy·branch 삭제는 수행하지 않습니다. JSON은 공개 패키지에 들어가도 로컬 절대 경로가 노출되지 않도록 `localPathMode=relative-to-local-root`, `privacy.publicArtifactSafe=true`, `privacy.absoluteLocalPathExposure=false`를 기록하고, System Status 화면의 `GitHub project discovery` 패널에서 같은 guard와 상위 프로젝트를 확인합니다.

```bash
npm run audit:github-projects
```

## 주요 기능

| 메뉴 | 기능 |
| --- | --- |
| Home | 오늘 일정/할 일, 실행 큐, 운영 관제판, AutoResearch loop, 공개 준비 요약, 로컬 데이터 상태 |
| Calendar | 월간 일정, 반복 일정, 선택일 아젠다 |
| Todo | 빠른 추가, 우선순위, 마감일, 상태 필터, 삭제/undo |
| Notes | Markdown 메모, pin, 색상, XSS 소독 렌더링 |
| Habits | 7일 체크, streak, 주간 목표 |
| Portfolio | 프로젝트 CRUD, OSS 후보 seed, benchmark handoff |
| Kanban | 컬럼 이동, 순서 저장, 키보드 이동, 마우스/터치 drag |
| Gantt | 작업 CRUD와 일정 막대 |
| Team | 멤버 CRUD와 프로젝트 참조 정리 |
| DB Catalog | 로컬 인스턴스/스키마/쿼리/백업/마이그레이션 문서화 |
| Settings/System | 백업, 가져오기 guard, 저장 실패 recovery, dashboard receipt, release evidence, PWA 상태 |

저장 실패 시 Settings/System에 긴급 백업 다운로드와 일반 export 버튼이 표시됩니다. `workspace-storage.js`는 실패 payload를 recovery JSON으로 만들고, `storage-status-view.js`가 복구 UX를 렌더링합니다. Dashboard intelligence는 `dashboardInsights`, `dashboardResearchLoops`, `dashboardImprovementCandidates`, `dashboardDecisionReceipts`, `dashboardEvidenceSnapshots`, `dashboardHealthChecks` localStorage 컬렉션에 retention을 걸어 저장하며 JSON export/import guard와 함께 이동합니다.

Review package issue drafts keep tracker-ready metadata visible before submission. The issue sheet and smoke coverage verify `assignee`, `due`, `estimate`, `tracker-ready`, and owner/timebox fields so generated review plans can be copied into an external tracker without rewriting.

## 보안/렌더링

HTML은 `html()` 템플릿 헬퍼에서 기본 escape되고, 검토된 HTML 조각만 `raw()`로 주입합니다. Markdown은 `[marked](https://github.com/markedjs/marked) | 18.0.5`로 변환한 뒤 `[DOMPurify](https://github.com/cure53/DOMPurify) | 3.4.8`로 소독합니다. 정적 감사는 다음 명령입니다.

```bash
npm run audit:xss
```

## Vendored OSS

npm runtime dependency는 없습니다. 브라우저에서 필요한 OSS는 `vendor/`에 원본 UMD 파일로 동봉하고 `vendor/LICENSES.md`와 `package.json#vendoredDependencies`가 같은 내용을 기록합니다.

| 라이브러리 | 버전 | 라이선스 | 파일 |
| --- | --- | --- | --- |
| Fuse.js | 6.6.2 | Apache-2.0 | `vendor/fuse.min.js` |
| marked | 18.0.5 | MIT | `vendor/marked.umd.js` |
| DOMPurify | 3.4.8 | Apache-2.0 / MPL-2.0 | `vendor/purify.min.js` |

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

주요 runtime helpers: `workspace-seed-data.js`, `home-view.js`, `dashboard-view.js`, `dashboard-insights-engine.js`, `dashboard-prioritization.js`, `dashboard-autoresearch-loop.js`, `dashboard-evidence-receipts.js`, `dashboard-storage.js`, `llm-wiki-view.js`, `calendar-view.js`, `todo-view.js`, `notes-view.js`, `habits-view.js`, `stats-view.js`, `portfolio-view.js`, `kanban-view.js`, `gantt-view.js`, `team-view.js`, `workspace-storage.js`, `storage-status-view.js`, `settings-view.js`, `system-status-view.js`, `command-palette.js`, `keyboard-shortcuts.js`, `interaction-setup.js`, `event-reminders.js`, `footer-clock.js`, `db-catalog.js`, `runtime-error-boundary.js`, `pwa-runtime.js`, `ops-runtime-loader.js`.

System Status의 `Ops runtime diagnostics` 패널은 `ops-runtime-loader.js`의 지연 로드 상태를 그대로 노출합니다. `loaded lazy files`, `ready groups`, pending/failed count, group별 release/review 로드 상태가 smoke와 release audit에서 검증됩니다.

## 아카이브

장문 launch/proof/meta 운영 기록은 루트 README에서 제거했습니다. 기존 전문은 `archive/meta-machine/README.full-before-slim.md`에 보존되어 있고, 반복 product loop 기록은 `docs/product-direction.md`, 이전 개선 로그는 `docs/improvement-roadmap.md`에 남아 있습니다. 이 아카이브는 현재 앱 실행 경로가 아니라 이력 확인용입니다.
