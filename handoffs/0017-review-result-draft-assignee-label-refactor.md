# Handoff 0017 — Review Result Draft Assignee Label Refactor

- **상태:** DONE
- **담당:** Codex 실행
- **시작일:** 2026-06-11

## 목표

`review-result-draft-state.js`의 assignee override 처리에서 issue draft label 재계산 로직을 private helper로 추출한다. `updateIssueDraftAssignee`의 dataset, cell text, panel text, follow-up 제거, toast side effect는 변경하지 않는다.

## 범위

- 수정 가능:
  - `review-result-draft-state.js`
  - `handoffs/0017-review-result-draft-assignee-label-refactor.md`
  - `WORKLOG.md`
- 수정 금지:
  - 공개 API/export surface
  - assignee dataset key와 값
  - label 문자열과 제거 대상
  - owner follow-up 제거 조건
  - toast 문구
  - 외부 배포, push, workflow 변경

## A/B 선택

| 선택지 | 내용 | 장점 | 리스크 |
| --- | --- | --- | --- |
| A | `updateIssueDraftAssignee` 전체를 state model + render apply 단계로 분해 | 장기 유지보수성 큼 | DOM side effect 순서가 바뀔 수 있고 blast radius가 큼 |
| B | label 재계산만 private helper로 추출 | 작고 동등성 검증 가능, 기존 DOM side effect 유지 명확 | 구조 개선 폭은 제한적 |

채택: **B**. 이번 루프는 작은 리팩터 단위 원칙에 맞춰 label split/filter/push 책임만 분리한다.

## 실행 단계

1. 기준 `npm test` green을 확인한다.
2. private helper `issueDraftAssigneeLabels`를 추가한다.
3. `updateIssueDraftAssignee`의 inline label split/filter/push를 helper 호출로 교체한다.
4. HEAD 대비 VM equality smoke로 assignee 지정/미지정 케이스의 dataset, cell text, panel text, follow-up 제거, toast side effect 동일성을 확인한다.
5. `node --check review-result-draft-state.js`, `npm test`, `git diff --check`를 통과시킨다.
6. 이 파일의 반환 섹션과 `WORKLOG.md`를 업데이트한다.

## 수용 게이트

- 기준 `npm test`
- `node --check review-result-draft-state.js`
- HEAD 대비 `updateIssueDraftAssignee` equality smoke 2 cases
- 변경 후 `npm test`
- `git diff --check`

## 반환

- 상태: DONE
- 결과: `updateIssueDraftAssignee`의 issue draft label 재계산을 private `issueDraftAssigneeLabels` helper로 추출했다. 공개 export surface, assignee dataset, cell text, panel copy, follow-up 제거 조건, toast side effect는 변경하지 않았다.
- 실행한 명령:
  - 기준 `npm test`
  - `node --check review-result-draft-state.js`
  - HEAD 대비 VM equality smoke (`updateIssueDraftAssignee` assignee 지정/미지정 2 cases)
  - 변경 후 `npm test`
  - `git diff --check`
- 남은 일: 없음. 공유 dirty tree와 외부 push/workflow 승인 경계 때문에 커밋·push는 보류.
