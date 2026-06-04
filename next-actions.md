# Next Actions

> 2026-06-04 AutoResearch cycle: Canva OAuth local path verified to external approval boundary. Cleared stale `dist/server/stdio.js` listener on port `8001`, `doctor:canva` now passes callback binding, auth smoke generated a fresh PKCE URL with redirect `http://localhost:8001/auth/callback`, and headless browser evidence showed Canva/Cloudflare challenge with no redirect mismatch text. Remaining blocker is real user Canva login/consent. Report: `docs/reports/2026-06/AUTO_RESEARCH_CANVA_OAUTH_BOUNDARY_2026-06-04.md`.
> 2026-06-04 AutoResearch cycle: DeSci manifest-managed browser path fixed and verified. `dev_server_control.py` now reuses live managed dependencies during wait-ready, `desci-api` has a 5s target probe budget, managed start reached `2/2 ready`, browser smoke passed `7/7`, click evidence had `0` console warnings/errors, DeSci smoke passed `8/8`, workspace smoke passed `8/8`, and managed stop returned `0/2 ready`. Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_DEV_SERVER_CONTROL_2026-06-04.md`.
> 2026-06-04 AutoResearch cycle: Adopted manifest-backed dev-server control in `ops/scripts/dev_server_control.py`. Live proof started Canva preview on `5176`, clicked theme/candidate/search/editor flows with `0` console warnings/errors, tailed logs, stopped the managed process, passed focused tests `17 passed`, and workspace smoke `8/8 PASS` via `var/workspace-smoke-workspace-dev-server-control-2026-06-04.json`. Durable report: `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_CONTROL_2026-06-04.md`.
> 2026-06-04 AutoResearch cycle: AgriGuard live browser QA found and fixed a real CORS/runtime gap between `http://127.0.0.1:5174` and Docker backend `8002`. Adopted variant recorded in `docs/reports/2026-06/AUTO_RESEARCH_AGRIGUARD_CORS_DOCKER_BROWSER_2026-06-04.md`; evidence includes fixed CORS GET/preflight headers, rebuilt `agriguard-backend`, Playwright clicks through Dashboard/Registry/Supply Chain/Scanner/camera toggle with `0` console warnings/errors, targeted backend tests `31 passed`, dev-server status `2/2 ready`, and AgriGuard smoke `5/5 PASS` via `var/workspace-smoke-agriguard-auto-research-cors-fix-2026-06-04.json`.

> 2026-06-04 기준 — 관찰성 게이트(Phase 1–3) 완성품화 완료 (브랜치 `feat/observability-finalize-2026-06`, clean fork from `fa9c7e8`). 오프라인 계약 검증기 `ops/scripts/verify_observability.py`(6/6) + `tests/test_verify_observability.py`(7 pass) 추가, `docs/runbook.md` §관찰성 게이트 운영/롤백 문서화, PR draft operational-smoke 체크 + Phase 3.x turnkey 스펙 기록. 로컬 재검증: shared/llm 76 + getdaytrends 21 + DailyNews 113(+1 respx skip) pass, ruff clean, healthcheck 6/6. 증거 `var/observability-verify-2026-06-04.json`, 리포트 `docs/reports/2026-06/OBSERVABILITY_COMPLETION_2026-06-04.md`. **잔여 deferred**: Phase 3.x desci `llm_clients.py`(untracked WIP, main 안착 후), Phase 4 BackendManager deprecation(별도 결정), 라이브 트레이스 스모크(인프라 필요). 머지/배포는 사용자 결정.
> 2026-05-21 기준 — PR #117 + PR #120 CI 게이트 정리 완료 (16+ commits, py/zizmor 50+ alerts 처리). PR #120: 22/22 PASS, mergeable=CLEAN. PR #117: 15 pass / 3 fail (CodeQL aggregate 캐시는 다음 commit 시 refresh, zizmor 0 findings 로컬 확인).
> 2026-05-21 기준 전체 시스템 QC 완료 (`run_workspace_smoke.py --scope all`, 25/25 PASS, report: `docs/reports/2026-05/SYSTEM_WIDE_QC_2026-05-21.md`)
> 2026-05-20 기준 전체 시스템 QC 완료 (`run_workspace_smoke.py --scope all`, 25/25 PASS, report: `docs/reports/2026-05/SYSTEM_WIDE_QC_2026-05-20.md`)

> 2026-05-20 기준 — DeSci VC DB 시드/배포 완료 (vc_firms 테이블 + repository + /vcs API + Investors 페이지, release gate 12/12 green)
> 2026-05-20 기준 — getdaytrends 최적화 패스 완료 (commit cf53319, DeepEval gate, 765 tests 242.72s→102.51s -57.7%)
> 2026-05-20 기준 — getdaytrends 제품완성형 패스 완료 (commits 48109f1+e5585a2+6fe16ed, 764 tests green, docs aligned)
> 2026-05-15 기준 — zizmor 보안 자동 픽스 완료 (브랜치 ci/zizmor-safe-fixes, 77건 -63%)

## Backlog (미완료)

- [x] ~~QA Review S101 false positive 수정~~ — commit 244ea18 (PR #117에 통합, 별도 PR 대신). per-file-ignores 추가 + 두 test 파일 I001/F401 정리 + contract 테스트 갱신. GHA 재검증 진행 중.
- [ ] **Canva token 브라우저 재인증 최종 확인** (인증 서버 기동 테스트 완료됨)
- [ ] **X 수동 발행**: Economy_Global 최종 문안 게시
- [x] **DeSci Platform — DB Population (50 VCs)** ✅ 2026-05-20 (commits TBD, 17+7 tests, release gate 12/12)
- [ ] **DeSci Platform — Production Deployment (Railway/Vercel)** (계정/도메인 필요)
- [ ] **DeSci Platform — Polygon Amoy Testnet `DeSciToken` 배포** (펀딩된 지갑/RPC 필요)
- [x] ~~**PR #120 머지 대기**~~ ✅ **READY TO MERGE** 2026-05-21 (22/22 checks PASS, mergeStateStatus=CLEAN). 머지 명령만 남음.
- [ ] **PR #117 머지 — CodeQL aggregate 캐시 refresh 후 가능**: 알림 50건 전부 처리 (실수정 + dismiss), 다음 commit push 시 게이트 자동 회복 예상.
- [ ] **GITLEAKS_LICENSE secret 설정**: Gitleaks-action v2가 org repo에서 라이센스 필요. PR #120 머지 후 secret 추가하면 Secret Scan 다시 동작.

## 시스템 고도화 후속 작업 (zizmor 잔여 findings)

- [x] ~~**artipacked 36건**~~ — commit 04dd45d, `persist-credentials: false` 일괄 추가, 36→0 (100%)
- [x] ~~**template-injection (Plan B) 부분**~~ — commit 04dd45d, env block 패턴으로 변환, 53→12 (77%, 단순 케이스 처리)
- [x] ~~**template-injection 잔존 12건**~~ ✅ 2026-05-20 commit 1eedd9d (sec(gha): harden workflows by adding concurrency, strict permissions and fixing template injections)
- [x] ~~**secrets-outside-env 120건**~~ ✅ 2026-05-20 commit 1eedd9d
- [x] ~~**excessive-permissions 33건**~~ ✅ 2026-05-20 commit 1eedd9d
- [x] ~~**concurrency-limits 19건**~~ ✅ 2026-05-20 commit 1eedd9d
- [x] ~~**로컬 zizmor 검증**~~ ✅ 2026-05-21 `uvx zizmor==1.24.1 --persona=auditor .github/workflows/` → 0 findings
- [ ] [needs_approval] **Plan P0-1 Langfuse self-host** — Supabase 옆 컨테이너로 LLM observability 도입
- [ ] [needs_approval] **Plan P0-2 LiteLLM proxy** — 7개 LLM 백엔드 통합 게이트웨이
- [ ] [needs_approval] **Plan P1-uv workspaces** — apps/automation/mcp/packages 단일 lockfile

## 다음 세션 복붙 메모

```text
GHA 공급망 보안 강화 완료 (2026-05-08):
- pinact: 26 workflows + 1 composite action SHA 핀 (commit 1437793)
- zizmor 게이트: workflow-audit job 추가, unpinned-uses 회귀 hard-fail (commit 0e3a006)
- zizmor HIGH 108 → 25 (-83), unpinned-uses 100% 제거
- 잔여 25 HIGH = template-injection 22 + excessive-permissions 3 → Plan B에서 처리
- var/zizmor.json (전), var/zizmor-after.json (후) 비교 가능
- pinact 도구는 ~/go/bin/pinact.exe (Windows), zizmor는 uvx로 ephemeral 실행
```
