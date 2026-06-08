# JooPark Workspace 개선 로드맵

> 작성일 2026-06-08 · 개선 방향성 검토 결과 및 실행 권고

## 1. 진단 — 개선 루프의 목적함수가 뒤집혀 있다

자율 autoresearch 루프가 **제품을 개선하는 대신 "막힌 배포를 관리하는 메타 기계"를 무한 증식**시키는 상태에 빠졌다.

| 지표 | 규모 |
|---|---|
| 실제 제품 (app.js + 뷰) | 18,731줄 |
| scripts/ (릴리스·런치·감사·drift 31개) | **26,938줄** — 제품 본체보다 큼 |
| product-loop.md / release-gates.json | **722KB / 540KB** |
| 커밋 96개 중 메타(release·launch·dispatch·drift) | **81개** / 제품 15개 |
| 최근 40개 커밋 | **전부 "Sync … release"** |
| 루프 실험 347개 중 거부(reject) | **0개** (전부 keep) |
| loop가 양산한 `codex/joopark-*` 브랜치 | **143개** |

### 핵심 문제 3가지
1. **자기참조 팽창** — GitHub 토큰에 `workflow` scope 하나가 없어 Pages 배포가 막혔는데, 풀지 않고 그 주위에 `blocker-resolver → evidence-intake → proof-parser → handoff-verifier → quick-proof-receipt` 레이어를 계속 쌓았다. README 403줄 중 실제 제품 설명은 한 단락.
2. **스코프 크리프** — 개인 워크스페이스 앱인데 외부 OSS 44개(AFFiNE·AppFlowy·Outline·OpenProject 등)를 "adoption candidate"로 등록·commit SHA 단위 "drift watch"하는 경쟁 인텔리전스 기계가 PM 뷰에 들어왔다.
3. **제품 정체** — 진짜 사용자 가치 방치: 모바일 0/10(`min-width:1180px` 하드코딩), 캘린더 주간/일 뷰 없음, 칸반 드래그 미완성, undo/휴지통 없음, DB 카탈로그 전부 mock.

> **한 줄 요약: "출시 준비는 100% 완벽하게 증명됐지만, 출시는 안 됐고, 제품은 그대로다."**

---

## 2. 권고 방향: B → C → A

막힌 것을 먼저 풀어 루프를 닫고(B), 자기참조 기계를 걷어내 시야를 확보한 뒤(C), 그 동력을 전부 제품 사용성(A)으로 돌린다.

### Phase B — 배포를 실제로 끝내고 launch 기계를 닫는다

**핵심 통찰:** GitHub Pages는 워크플로 없이 **브랜치에서 직접 서빙** 가능 → `repo` scope만 필요(현재 토큰이 이미 보유). `workflow` scope·dispatch·evidence 기계 **전부 불필요**. 현 배포가 "monorepo 서브디렉터리 + 루트 워크플로 + no-common-history 브리지"로 얽힌 건 루프가 만든 골판지 기계일 뿐이다.

**권고 경로 — 전용 repo + 브랜치 Pages:**
1. 전용 repo 생성 (예: `biojuho/joopark-workspace`) — monorepo 서브디렉터리/orphan-branch 브리지 회피
2. 루트 self-contained 정적 파일(40개 + `vendor/` + `icons/`)을 그 repo `main`에 push
3. repo Settings → Pages → **"Deploy from a branch"** → `main` / `/ (root)`
4. 라이브: `https://biojuho.github.io/joopark-workspace/`
5. 결과: workflow yml·dispatch·evidence·handoff 전부 불필요 → Phase C에서 일괄 제거

**대안:** 비-GitHub 정적 호스트(Netlify/Cloudflare Pages drop) — `dist/release/` 드래그앤드롭.

- 사용자 액션 필요: repo 생성·push·Pages 설정(외부 인증·웹 설정이라 대행 불가)
- 도와줄 수 있는 것: 배포 산출물 self-contained 검증, push 스크립트 준비, 로컬 동작 확인
- 현 검증 상태: GitHub CLI 토큰에 `workflow` scope가 없어 기존 workflow 설치 경로는 `blocked` 상태다. `remoteWorkflowFilesReady=false`, `remoteWorkflowVisibilityReady=false`, `allDispatchReady=false`, `safeToDispatch=false`가 실제 원격 검사에서 재확인되었고, `gh workflow run`은 계속 보류한다.

### Phase C — 메타 기계 정리 (repo를 제품 중심으로 복귀)

- **C1. 아카이브** (삭제 아닌 격리 → `archive/autoresearch-meta/` 또는 별도 브랜치)
  - `autoresearch-results/` (1MB+)
  - `data/`의 launch·publish·dispatch·evidence·audit·workflow·main-bridge JSON
  - `scripts/`의 release·launch·dispatch·drift·candidate·veritas·handoff·audit 계열 (≈25개)
  - 메타 런타임 JS: `review-*.js`, `release-status.js`, `operations-copy-actions.js`
  - `index.html`에서 위 메타 런타임 `<script>` 태그도 함께 제거
- **C2. README 슬림화** — 403줄 → 제품 설명 + 로컬 실행 + 짧은 배포 안내. workflow/dispatch/evidence 단락 전부 삭제
- **C3. `npm run verify` 재정의** — 현재 = release 게이트 감사. → 실제 제품 스모크(`smoke-chrome` + `smoke-interactions` + `smoke-mobile` + `smoke-a11y`)로 교체
- **C4. PM 포트폴리오 시드 정리** — OSS adoption-candidate/drift 데이터(`data/adoption-candidates.json`, `data/repos.json`)는 제품과 무관 → 제거하거나 "데모 데이터"로 명시
- **C5. 원격 브랜치 prune** — `codex/joopark-*` 143개 중 머지/폐기분 정리(사용자 확인 후)

### Phase A — 제품 사용성 (동력을 여기로)

| 우선 | 상태 | 항목 | 대상 파일 |
|---|---|---|---|
| ★ 최우선 | 완료 | 모바일 반응형 — 전역 `min-width:1180px` 제거, 사이드바 collapse, 그리드 브레이크포인트 | `styles.css` |
| ★ | 완료 | 캘린더 주간/일 뷰 | `calendar-view.js` |
| ★ | 완료 | 파괴적 삭제 보호 — undo 토스트 + 최근 삭제 복구함 | `app.js` delete 핸들러, `dialog-shell.js` |
| ○ | 완료 | 칸반 드래그앤드롭 상태 이동 + 카드 순서 조정 | `app.js` Kanban drag-and-drop |
| ○ | 완료 | DB 카탈로그 정직성 — local catalog/no live connection, sample/manual/imported provenance 표시 | `db-catalog.js` |
| 중기 | 미완료 | `app.js` 10K줄 분해 — 거대 click 핸들러 switch를 뷰별 모듈로 | `app.js` |

---

## 3. 검증 방법

- **B:** 배포 URL이 16개 라우트(`#cal`~`#system`)에서 콘솔/네트워크 오류 없이 로드되는지 확인. `node scripts/smoke-chrome.mjs`를 배포 URL 대상으로 재실행.
- **C:** 아카이브 후 `python3 -m http.server 5178`로 로컬 앱이 동일하게 동작하는지(메타 런타임 제거가 제품에 영향 없음) 확인. README가 제품만 설명하는지 검토.
- **A:** 각 항목별 `smoke-mobile.mjs`(반응형), 수동 클릭 테스트(주간 뷰·undo·드래그), `smoke-a11y.mjs`(접근성 회귀) 통과 확인.
