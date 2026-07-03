# 핸드오프 0008 — review package boolean attribute helper 리팩터링

- **상태:** DONE
- **기획자:** Codex 기획
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
`review-package-view.js`에서 `"true"`/`"false"` data-attribute 문자열화가 반복되는 지점을 private helper로 묶어, note 발행 상태 attribute 생성 의도를 이름으로 드러내고 동작은 보존한다.

## 배경
review package handoff view는 노트 생성 여부를 여러 data attribute에 같은 방식으로 기록한다. 작은 helper로 정리하면 attribute 값 표현이 한 곳에 모이고, 이후 note 상태 attribute가 추가될 때 같은 표현을 재사용할 수 있다.

## 범위
- **건드릴 것:** `review-package-view.js`, `handoffs/0008-review-package-bool-attr-refactor.md`, `WORKLOG.md`.
- **건드리지 말 것:** DOM attribute 이름, HTML 구조, copy/publish action, export surface, release/publish 게이트, 외부 전송.

## 단계
1. 기준선 syntax/full test 상태를 확인한다.
2. boolean attribute 문자열 helper를 추가하고 기존 조건식을 치환한다.
3. syntax/equality smoke/full test를 실행한다.
4. 반환 섹션과 WORKLOG에 결과를 기록한다.

## 수용 게이트
- `node --check review-package-view.js`
- HEAD 대비 VM equality smoke
- `npm test`
- `git diff --check`

## 금지사항
- review package model, rendered HTML, data attribute 이름/값, export surface를 바꾸지 않는다.
- 외부 push, 배포, remote workflow 설치는 하지 않는다.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `review-package-view.js`의 note 발행 여부 data-attribute 문자열화를 `boolAttr` private helper로 추출했다. `rootAttrs`와 `noteButtonHTML`의 기존 `"true"`/`"false"` attribute 값은 HEAD 대비 VM equality smoke로 동일함을 확인했다.
- **실행한 게이트:** 기준선 `node --check review-package-view.js` pass, 직전 변경 후 `npm test` pass, 변경 후 `node --check review-package-view.js` pass, HEAD 대비 VM equality smoke pass(`reviewPackageHandoffModel`/`reviewPackageHandoffHTML` 3 cases), 변경 후 `npm test` pass, `git diff --check` pass.
- **남은 것 / 막힌 곳:** 다른 핸드오프/세션의 공유 dirty tree가 남아 있어 커밋은 보류했다. 외부 push, 배포, remote workflow 설치는 명시 승인 전까지 수행하지 않았다.
