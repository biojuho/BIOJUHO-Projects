# 핸드오프 0007 — review artifact receipt 비교 helper 리팩터링

- **상태:** DONE
- **기획자:** Codex 기획
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
`review-artifact-view.js`의 receipt comparison 경로에서 check row signature와 pass 판정을 private helper로 분리해, 비교 의도를 이름으로 드러내고 동작은 보존한다.

## 배경
`reviewArtifactReceiptComparison`과 `reviewArtifactReceiptCompareOutput`가 check row 문자열화와 pass 판정을 인라인으로 반복한다. 작은 helper로 묶으면 receipt drift 비교 기준을 한 곳에서 유지할 수 있다.

## 범위
- **건드릴 것:** `review-artifact-view.js`, `handoffs/0007-review-artifact-comparison-refactor.md`, `WORKLOG.md`.
- **건드리지 말 것:** receipt markdown 형식, repair suggestion 문구, app 연결부, release/publish 게이트, 외부 전송.

## 단계
1. 기준선 `npm test` 통과를 확인한다.
2. check row signature/pass helper를 추가하고 기존 조건을 치환한다.
3. syntax/equality smoke/full test를 실행한다.
4. 반환 섹션과 WORKLOG에 결과를 기록한다.

## 수용 게이트
- `node --check review-artifact-view.js`
- HEAD 대비 VM equality smoke
- `npm test`
- `git diff --check`

## 금지사항
- receipt 비교 결과, copy payload, DOM attribute, export surface를 바꾸지 않는다.
- 외부 push, 배포, remote workflow 설치는 하지 않는다.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `review-artifact-view.js`의 receipt check row signature와 pass 판정을 각각 `reviewArtifactReceiptCheckSignature`, `reviewArtifactReceiptChecksPass` private helper로 추출했다. `reviewArtifactReceiptComparison`과 `reviewArtifactReceiptCompareOutput`의 기존 pass/fail 출력은 HEAD 대비 VM equality smoke로 동일함을 확인했다.
- **실행한 게이트:** 기준선 `npm test` pass, `node --check review-artifact-view.js` pass, HEAD 대비 VM equality smoke pass(`reviewArtifactReceiptComparison` pass/fail, `reviewArtifactReceiptCompareOutput` pass/fail), 변경 후 `npm test` pass, `git diff --check` pass.
- **남은 것 / 막힌 곳:** 다른 핸드오프/세션의 공유 dirty tree가 남아 있어 커밋은 보류했다. 외부 push, 배포, remote workflow 설치는 명시 승인 전까지 수행하지 않았다.
