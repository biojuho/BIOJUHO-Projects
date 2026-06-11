# 핸드오프 0001 — 런치 차단 해제: 미커밋 변경 커밋·푸시 후 디스패치 게이트 재검증

- **상태:** DONE
- **기획자:** Claude Code
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
`remoteWorkflowFilesReady=true`, `allDispatchReady=true`가 되어 `gh workflow run`(사용자 승인 대기) 직전 상태까지 도달한다.

## 배경
2026-06-11 종합 점검(`docs/improvement-plan-2026-06.md`) 결과, 차단의 진짜 원인은 리모트 드리프트가 아니라 **커밋 누락**이다:
- 작업 트리의 `.github/workflows/joopark-pages.yml`(SHA `7d47ffeb…`)은 템플릿 `docs/github-pages-workflow.yml`과 일치하지만, 로컬 HEAD(`71a78beb…`)와 리모트(`8ea83aa0…`)는 구버전.
- 미커밋 파일 108개(76 수정 + 32 미추적)가 쌓여 있음.
- 리모트 이름은 `origin`이 아니라 **`biojuho-projects`** (`git remote -v` 확인). origin을 가정한 명령은 실패한다.
- GitHub 측 준비는 끝남: Pages 활성(`has_pages=true`), gh CLI에 workflow scope 있음.
- 참고 지식: `docs/knowledge/github-pages-actions-deploy.md`

## 범위
- **건드릴 것:** git 커밋·푸시(브랜치 `main` → 리모트 `biojuho-projects`), `data/remote-workflow-file-check.json`·`data/publish-dispatch-plan.json`·`data/launch-readiness-refresh.*` 등 게이트 산출물 재생성, WORKLOG.md 기록.
- **건드리지 말 것:** 앱 소스 코드(이번 핸드오프에서 기능 수정 금지), `.github/workflows/joopark-pages.yml` 내용(이미 템플릿과 일치 — 수정하지 말 것), GitHub 리포 설정.

## 단계
1. `git status`로 108개 변경을 훑고 논리 단위로 커밋한다. 최소 분리 기준:
   - ① 워크플로 파일 (`.github/workflows/joopark-pages.yml`) — 최우선 단독 커밋
   - ② 앱 소스 리팩터 결과 (app.js 및 *-view.js 등)
   - ③ 스크립트·게이트 산출물 (scripts/, data/, autoresearch-results/)
   - ④ 문서 (docs/, README.md, WORKLOG.md 등)
   - 미추적 파일 32개는 내용 확인 후 포함 여부 판단 — 생성 아티팩트 캐시면 커밋하지 않고 반환 섹션에 목록을 적는다.
2. `git push biojuho-projects main` (origin 아님에 주의).
3. `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write` 실행 → `remoteWorkflowFilesReady=true` 확인.
4. `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` 실행 → `allDispatchReady=true` 확인.
5. `npm run refresh:launch-readiness` 로 readiness 산출물 동기화.
6. **여기서 정지.** `gh workflow run`은 실행하지 않는다(아래 금지사항). 반환 섹션에 게이트 값과 다음 단계(사용자 승인 후 디스패치 명령)를 적는다.

## 수용 게이트
- `git status --short | wc -l` 결과가 5 이하 (의도적으로 남긴 미추적 파일 제외, 반환 섹션에 사유 명시)
- `data/remote-workflow-file-check.json`에서 pages·drift-watch 모두 `remoteMatchesTemplate=true`
- `data/publish-dispatch-plan.json`에서 `allDispatchReady=true`
- `npm test` 통과 (커밋 전 1회)

## 금지사항
- **`gh workflow run` 등 실제 디스패치(게시) 금지** — 사용자 명시 승인 후 별도 진행.
- 강제 푸시(`--force`) 금지. 리모트 브랜치 삭제 금지.
- 비밀키·토큰 출력 금지.
- 범위 밖(기능 수정·리팩터) 작업 금지. 막히면 반환 섹션에 적고 되돌린다.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** 실행하지 않고 차단 상태로 반환한다. 현재 워크트리는 `0003-product-declutter`, `0005-quality-gate-promotion`이 `CLAIMED`인 상태에서 미커밋 변경 116개가 남아 있어 이 handoff가 요구하는 전체 변경 묶음 커밋을 안전하게 소유할 수 없다. 또한 2단계 `git push biojuho-projects main`은 사용자 명시 승인 없는 외부 전송에 해당한다.
- **실행한 게이트:** `git status --short | wc -l` 확인 결과 116개 변경, `rg`로 handoff 상태 확인, `ps`로 다른 `npm test`/smoke 프로세스 실행 중 확인. push, dispatch, remote write 실행 없음.
- **남은 것 / 막힌 곳:** 사용자에게 `git push biojuho-projects main` 승인 여부를 먼저 받아야 한다. 그 전에는 `0003`/`0005` 실행자가 완료·커밋하거나 반환해 미커밋 변경 소유권이 정리되어야 한다. 승인과 소유권 정리 전에는 `remoteWorkflowFilesReady=true`/`allDispatchReady=true` 달성 작업을 진행하지 않는다.
