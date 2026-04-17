# Biojuho Execution Priorities

## Priority 1

### Source Diversity Hard Gate

- 목적: usable source count만으로 통과시키지 않고, 실제 조합 품질까지 확인한다.
- 완료 조건:
  - `twitter + news`
  - `reddit + news`
  - `twitter + reddit`
  - 위 조합 중 하나를 만족해야 publish queue에 진입
- 이유:
  - 단일 뉴스 소스 + 얕은 보조 신호 조합을 막는 효과가 가장 크다.
  - 현재 파이프라인 구조에서 구현 난도가 낮고 회귀 테스트가 쉽다.

## Priority 2

### Hard Drop Topic Policy

- 목적: 바이럴이 높아도 계정 정체성과 충돌하는 주제를 초반에 제거한다.
- 예시:
  - fandom-only
  - cosplay-only
  - patch-note-only
  - meme-only

## Priority 3

### Approved Post Bank

- 목적: 실제 승인된 카피만으로 voice reference bank를 구축한다.
- 필요 데이터:
  - original draft
  - edited draft
  - final published draft
  - reject reason

## Priority 4

### Review Loop Data Upgrade

- 목적: 쥬팍의 수정 습관을 구조화해 다음 생성과 QA에 반영한다.
- 필요 컬럼:
  - edited_by_human
  - edit_distance
  - publish_decision
  - 24h performance
  - 72h performance

## Priority 5

### Voice Similarity QA

- 목적: 생성 결과가 `biojuho` voice bank와 얼마나 가까운지 자동 평가한다.
- 방식:
  - lexical check
  - banned slang check
  - embedding similarity
  - editor override

## 이번 라운드 진행 범위

1. Priority 1 구현
2. 관련 테스트 추가
3. 검증 통과

## Status Update

- Priority 1 implemented
- Priority 2 implemented
- Next recommended priority: Priority 3 Approved Post Bank
