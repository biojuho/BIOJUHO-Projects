# Handoff 0016 — Review Artifact Receipt Count Refactor

- **상태:** DONE
- **담당:** Codex 실행
- **시작일:** 2026-06-11

## 목표

`review-artifact-state.js`의 receipt compare 상태 설정에서 pass/repair/count 계산을 private helper로 추출한다. `setReceiptCompareState`의 DOM dataset, status text, output HTML side effect는 변경하지 않는다.

## 범위

- 수정 가능:
  - `review-artifact-state.js`
  - `handoffs/0016-review-artifact-receipt-count-refactor.md`
  - `WORKLOG.md`
- 수정 금지:
  - 공개 API/export surface
  - receipt compare state 이름과 dataset key
  - status/toast 문구
  - repair/apply/undo 동작
  - 외부 배포, push, workflow 변경

## A/B 선택

| 선택지 | 내용 | 장점 | 리스크 |
| --- | --- | --- | --- |
| A | receipt compare state 전체를 model 객체로 재구성 | 향후 확장성 큼 | DOM side effect 범위가 넓어져 회귀 위험 증가 |
| B | pass/repair/count 계산만 private helper로 추출 | 작고 검증 가능하며 기존 side effect 유지가 명확함 | 구조 개선 폭은 제한적 |

채택: **B**. 현재 중복과 인지 부하는 count 계산에 집중되어 있고, DOM 출력 계약은 그대로 두는 것이 안전하다.

## 실행 단계

1. 기준 `node --check review-artifact-state.js` 통과를 확인한다.
2. private helper `receiptCompareCounts`를 추가한다.
3. `setReceiptCompareState`에서 기존 count 계산을 helper 호출로 대체한다.
4. HEAD 대비 VM equality smoke로 empty/fail/no-output 케이스의 dataset, status text, output HTML side effect 동일성을 확인한다.
5. `npm test`, `git diff --check`를 통과시킨다.
6. 이 파일의 반환 섹션과 `WORKLOG.md`를 업데이트한다.

## 수용 게이트

- `node --check review-artifact-state.js`
- HEAD 대비 `setReceiptCompareState` equality smoke 3 cases
- `npm test`
- `git diff --check`

## 반환

- 상태: DONE
- 결과: `setReceiptCompareState`의 receipt compare count/pass/repair 계산을 private `receiptCompareCounts` helper로 추출했다. 공개 export surface, dataset key, status text, output HTML side effect는 변경하지 않았다.
- 실행한 명령:
  - `node --check review-artifact-state.js`
  - HEAD 대비 VM equality smoke (`setReceiptCompareState` empty/fail/no-output 3 cases)
  - `npm test`
  - `git diff --check`
- 남은 일: 없음. 공유 dirty tree와 외부 push/workflow 승인 경계 때문에 커밋·push는 보류.
