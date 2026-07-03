# 핸드오프 0023 — remote pages workflow mismatch blocker

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표

`remoteWorkflowFilesReady=false` 외부 launch blocker를 재현하고, 로컬 코드로 고칠 수 있는 버그인지 외부 승인 필요 상태인지 판별한다.

## 배경

0022 이후 local release readiness는 `verify_command_gate_only` fail 없이 `blocked` 상태로 정리됐다. 남은 핵심 blocker는 remote workflow file parity다.

## 범위

- **건드릴 것:** `handoffs/0023-remote-workflow-mismatch-blocker.md`, `WORKLOG.md`.
- **건드리지 말 것:** 원격 GitHub 파일 수정, workflow install, workflow dispatch, push, public launch claim.

## 단계

1. 읽기 전용 remote workflow check를 실행한다.
2. pages/drift-watch 각각의 remote/template SHA를 비교한다.
3. 로컬 템플릿과 로컬 `.github/workflows` 파일 parity를 확인한다.
4. 수정 가능 여부와 승인 필요 작업을 반환한다.

## 수용 게이트

- `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects`가 현재 mismatch를 보여야 한다.
- 로컬 파일 SHA parity가 확인되어야 한다.
- 외부 쓰기 없이 완료해야 한다.

## 금지사항

- 사용자 명시 승인 없이 `install-remote-workflow-files.mjs --write`, `gh workflow run`, `git push`, GitHub UI 편집을 실행하지 않는다.

---

## 반환 섹션 (실행자가 채운다)

- **결과:** 재현 완료. `pages` 원격 `.github/workflows/joopark-pages.yml`은 존재하지만 remote SHA-256 `8ea83aa0d99b303beb6b42976429acc207492d34de461a2ac9c026fbc4cb7574`가 local template SHA-256 `7d47ffeb39201dacff42a52825e7988d20aa28e81d2d54dfcf628a3c1e39619e`와 달라 `remoteWorkflowFilesReady=false`다. `drift-watch` 원격 파일은 local template과 일치한다. 로컬 `docs/github-pages-workflow.yml`과 `.github/workflows/joopark-pages.yml`은 같은 SHA라 로컬 코드 불일치가 아니라 remote default branch 파일 drift다.
- **실행한 게이트:** `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects` pass with blocker, local SHA comparison pass, `git diff --check -- WORKLOG.md handoffs/0022-verify-summary-sync-repair.md ...` pass.
- **사용자 가시 변화 한 줄:** 사용자 화면 변화는 없고, 남은 launch blocker가 로컬 코드가 아니라 원격 workflow 파일 drift임을 확정했다.
- **남은 것 / 막힌 곳:** 근본 수정은 `biojuho/BIOJUHO-Projects` default branch의 `.github/workflows/joopark-pages.yml`을 local template으로 교체하고 재검증하는 외부 쓰기다. 사용자 승인 없이는 실행하지 않았다.
