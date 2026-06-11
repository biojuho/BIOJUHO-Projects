# 핸드오프 0006 — review handoff readiness 조건 리팩터링

- **상태:** DONE
- **기획자:** Codex 기획
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
`review-handoff.js` 내부의 반복되는 payload/field readiness 문자열 판정을 helper로 모아, 외부 동작을 유지한 채 review package 제출 경로의 가독성과 유지보수성을 높인다.

## 배경
`review-handoff.js`는 깨끗한 git 상태의 큰 모듈이며, tracker field, external form, receipt, submission update 경로에서 `missing`/`Confirm`/`Set after` placeholder 판정이 반복된다. 반복 조건을 그대로 helper에 모으면 동작 변경 없이 조건 의미를 한 곳에서 확인할 수 있다.

## 범위
- **건드릴 것:** `review-handoff.js`, `handoffs/0006-review-handoff-readiness-refactor.md`, `WORKLOG.md`.
- **건드리지 말 것:** app 연결부, release/publish 게이트, 기존 테스트 완화, 외부 전송.

## 단계
1. 기준선 `npm test` 통과를 확인한다.
2. readiness predicate helper를 추가하고 기존 반복 조건을 동일한 의미로 치환한다.
3. syntax/focused/full test를 재실행한다.
4. 반환 섹션과 WORKLOG에 결과를 기록한다.

## 수용 게이트
- `node --check review-handoff.js`
- `npm test`
- `git diff --check`

## 금지사항
- review package 출력 문자열, ready/pass 조건, schema version, export surface를 바꾸지 않는다.
- 외부 push, 배포, remote workflow 설치는 하지 않는다.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `review-handoff.js`의 반복 readiness 문자열 판정을 `reviewPackageText`와 `reviewPackageReadyValue` helper로 모았다. tracker field, external tracker payload/form, closeout summary, external receipt, submission update 경로의 기존 `missing`/`Confirm`/`Set after` 판정은 같은 조건으로 유지했고 export surface와 schema version은 바꾸지 않았다. 오토리서치 비교: A안(인라인 조건 유지)은 diff가 작지만 predicate drift가 누적된다; B안(private helper 추출)은 조건 의미가 한 곳에 모이고 현재 VM equality smoke로 출력 동일성을 확인할 수 있어 채택했다.
- **실행한 게이트:** 기준선 `npm test` pass. 변경 후 `node --check review-handoff.js` pass. HEAD 대비 VM equality smoke pass(`reviewPackagePastePreviewTargets`, `reviewPackageTrackerFieldPacket`, `reviewPackageSubmitSequence`, `reviewPackageSubmissionCloseoutSummary`, `reviewPackageExternalReceiptTemplate` 출력 동일). 변경 후 `npm test` pass. `git diff --check` pass.
- **남은 것 / 막힌 곳:** 다른 세션/기존 handoff의 dirty tree와 외부 publish/workflow 승인 차단은 그대로 남아 있어 이 handoff에서는 커밋·push를 하지 않았다.
