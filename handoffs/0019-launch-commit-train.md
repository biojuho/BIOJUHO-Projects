# 핸드오프 0019 — 런치 커밋 트레인 (미커밋 139개 → 논리 단위 9커밋, 푸시 없음)

- **상태:** CLAIMED
- **기획자:** Claude Code
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표

워크트리의 미커밋 변경 139개(수정 88 + 미추적 51)가 의도가 드러나는 논리 단위 커밋 ①~⑨로 정리되어 `git status --porcelain`이 5줄 이하가 된다. **푸시는 하지 않는다** — 푸시(U1)는 사용자 승인 후 핸드오프 0021에서 별도 진행한다. 이 트레인이 끝나면 handoff 0001이 차단 반환됐던 "워크트리 소유권 불명" 문제가 해소된다.

## 배경

- 2차 플랜: `docs/improvement-plan-2026-06-r2.md` (Phase L1). 1차 플랜 Phase 1의 차단(handoff 0001 반환)을 푸는 선행 작업이다.
- **handoff 0001의 `git push biojuho-projects main` 명령은 무효다.** 로컬 main과 리모트 main은 공통 조상이 없고, 추적 브랜치는 `biojuho-projects/codex/joopark-workspace-release`다. 이 핸드오프에서는 어떤 push도 하지 않으므로 해당 명령을 실행할 일이 없다.
- 0014~0018 자가 발급 리팩터 핸드오프의 변경분(review-*.js 등)은 이 트레인의 review 묶음(커밋 ⑥)에 흡수한다.

## 선행 조건

1. **0018(`0018-review-creation-note-defaults-refactor.md`)이 CLAIMED 진행 중이면 먼저 반환 종료한다.** 진행 중 변경분은 커밋 ⑥에 흡수한다. 트레인 시작 후에는 완료까지 다른 어떤 핸드오프도 착수하지 않는다.
2. AGENTS.md 개정판(발급 권한·모라토리엄 조항)을 읽고 따른다.

## 범위

- **건드릴 것:** `.gitignore`(아래 전처리 2줄 제거만), git 커밋 작업 전부, `WORKLOG.md`(기록 1줄), 이 핸드오프의 반환 섹션.
- **건드리지 말 것:** 앱·스크립트의 코드 내용(이 트레인은 **커밋만** 한다 — 기능 수정·리팩터·삭제 금지), 리모트(`git push`/`git fetch --prune` 등 원격 변경 일절 금지), `git rm --cached`류 추적 해제(Phase M·0023의 몫).

## 단계

1. **전처리:**
   - `.gitignore`에서 `data/github-project-discovery.json`·`data/github-project-discovery.md` 2줄을 제거한다. 이 두 파일은 `sw.js:74`(APP_SHELL_ASSETS — `cache.addAll`은 하나라도 404면 SW 설치 전체 실패)와 `scripts/verify-release.mjs:84` 필수 목록에 있는 배포 필수 자산이므로 **추적에 추가**해야 한다.
   - `npm test` 전체 1회 실행 → baseline pass 확인.
2. **커밋 ①** `.github/workflows/joopark-pages.yml` **단독**. 리모트 워크플로 드리프트(`remoteWorkflowFilesReady=false`)를 해소하는 최소 단위 — 문제가 생기면 단독 revert 가능해야 한다.
3. **커밋 ②** `.github/workflows/joopark-ci.yml` **단독** (신규 CI — 푸시 시 트리거 부수효과가 있는 파일이므로 분리).
4. **커밋 ③** 신규 런타임 자산 (index.html·sw.js가 로드하는 미추적 파일 — 빠지면 배포 즉사):
   `dashboard-autoresearch-loop.js`, `dashboard-evidence-receipts.js`, `dashboard-insights-engine.js`, `dashboard-prioritization.js`, `dashboard-storage.js`, `dashboard-view.js`, `event-reminders.js`, `footer-clock.js`, `home-view.js`, `interaction-setup.js`, `keyboard-shortcuts.js`, `ops-runtime-loader.js`, `runtime-error-boundary.js`, `workspace-seed-data.js`, 그리고 `.gitignore` + `data/github-project-discovery.json` + `data/github-project-discovery.md`(전처리 결과).
5. **커밋 ④** 수정된 코어: `app.js`, `index.html`, `styles.css`, `sw.js`, `pwa-runtime.js`, `workspace-storage.js` 등 코어 런타임. 너무 크면 ④a/④b로 쪼개되 같은 검증 사이클 안에서 처리.
6. **커밋 ⑤** 수정된 뷰·제품 계열: `*-view.js`, `db-catalog.js`, `dialog-shell.js`, `global-search.js`, `command-palette.js`, `project-picker.js`, `backup-import-*.js` 등.
7. **커밋 ⑥** review·운영 런타임 계열: `review-*.js`, `release-status.js`, `operations-copy-actions.js` (0014~0018 리팩터 결과물 포함).
8. **커밋 ⑦** `scripts/` 전체(수정+신규) + `package.json`.
9. **커밋 ⑧** `data/`(discovery 제외 나머지) + `autoresearch-results/` 게이트 증거.
10. **커밋 ⑨** 운영·문서: `AGENTS.md`, `ENHANCEMENT_LOG.md`, `handoffs/`, `docs/`, `README.md`, `WORKLOG.md`, `archive/`, 기타 잔여 파일.
11. **마감:** `npm test` 전체 재실행 → pass. `git status --porcelain | wc -l` ≤ 5. `git diff --check` 통과. WORKLOG에 1줄 기록.

커밋 사이 검증은 `npm run lint && npm run check:structure`로 경량화한다(전체 test는 시작·종료 2회만). 커밋 메시지는 묶음의 의도가 드러나게 쓴다. 일부 커밋은 20파일을 넘을 수 있으나, 커밋 케이던스 규칙의 목적(미커밋 누적 방지)에 부합하므로 논리 단위를 우선한다.

## 수용 게이트

- 전처리·마감 `npm test` 모두 pass.
- `git status --porcelain | wc -l` ≤ 5.
- `git diff --check` 통과.
- 커밋 ①이 `joopark-pages.yml` 단독, 커밋 ②가 `joopark-ci.yml` 단독임을 `git show --stat`으로 확인.

## 금지사항

- **push 금지** (어떤 리모트 ref로도). 디스패치(`gh workflow run`) 금지.
- 코드 내용 수정 금지(커밋만), `git rm --cached` 금지, 파일 삭제 금지.
- 트레인 완료까지 다른 핸드오프 착수 금지. 막히면 추측 대신 반환 섹션에 적어 되돌릴 것.
- 비밀키 노출 금지.

---

## 반환 섹션 (실행자가 채운다)

- **결과:**
- **실행한 게이트:**
- **사용자 가시 변화 한 줄:**
- **남은 것 / 막힌 곳:**
