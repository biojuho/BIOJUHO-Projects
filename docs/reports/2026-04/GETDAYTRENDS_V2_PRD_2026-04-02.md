# getdaytrends V2.0 PRD

작성일: 2026-04-02
상태: 승인 전 초안
범위: `automation/getdaytrends` 중심 워크플로우 재정렬

## 1. 제품 한 줄 정의

`getdaytrends`는 실시간 트렌드를 수집·검증·스코어링하여, 사람이 안전하게 검토하고 발행할 수 있는 `publish-ready draft`까지 만드는 트렌드 인텔리전스 파이프라인이다.

## 2. 이번 리셋의 목적

지금까지는 스키마 복구, 캐시, 모니터링, smoke, publisher 연결 같은 주변 안정화 작업이 빠르게 쌓이면서, 정작 `getdaytrends`의 최종 가치가 무엇인지가 흐려졌다.

이번 V2.0 리셋의 목적은 다음 세 가지다.

1. `getdaytrends`의 최종 산출물을 명확히 정의한다.
2. 위험한 자동 발행을 기본 경로에서 제거한다.
3. `수집 -> 검증 -> 생성 -> 승인 큐 -> 성과 학습`의 닫힌 루프를 제품 단위로 다시 고정한다.

## 3. North Star

매 실행 주기마다:

1. 가치 있는 트렌드를 수집하고
2. 노이즈와 중복을 제거하고
3. 콘텐츠 초안을 자동 생성하고
4. 품질/정책/사실성 게이트를 통과한 결과만
5. `사람이 검토 가능한 발행 준비 상태`로 저장하며
6. 발행 이후의 성과를 다시 다음 생성 전략에 반영한다

이 흐름이 안정적으로 반복되는 것이 V2.0의 목표다.

## 4. 핵심 사용자

주 사용자:

- 트렌드를 빠르게 보고 콘텐츠 방향을 잡아야 하는 운영자
- 최종 발행 전 품질과 리스크를 통제하고 싶은 1인 팀/소규모 팀

보조 사용자:

- Notion/대시보드에서 초안을 검토하고 승인하는 편집자
- 성과 데이터를 보고 다음 생성 전략을 조정하는 운영자

## 5. 문제 정의

현재 `getdaytrends`는 많은 기능을 이미 갖고 있지만, 제품 관점에서 보면 아직 아래가 완전히 고정되지 않았다.

- 어떤 데이터가 "유효한 트렌드"인지
- 어떤 기준을 통과해야 "발행 준비 완료"인지
- 자동 생성과 사람이 개입하는 경계가 어디인지
- 성과 데이터가 어떻게 다시 스코어링/프롬프트/시간대 전략으로 돌아가는지

가장 중요한 운영 원칙은 다음과 같다.

> `getdaytrends`의 기본 목표는 자동 발행이 아니라, 안전한 발행 준비 상태를 만드는 것이다.

## 6. 범위 정의

### In Scope

- 트렌드 수집
- 근거/신뢰도/중복 검증
- 점수화와 우선순위화
- 짧은 글/긴 글/채널별 초안 생성
- QA, 규제, 사실성, 형식 검증
- `publish-ready draft queue` 생성
- Notion 또는 내부 리뷰 허브 적재
- 게시 후 성과 수집 및 전략 피드백

### Out of Scope

- X 완전 자동 발행
- 사람 승인 없이 외부 채널에 자동 업로드
- 계정 정지 위험이 있는 우회/비공식 자동화 경로의 기본 채택
- `getdaytrends` 밖의 다른 앱 축을 이번 마일스톤 핵심으로 포함하는 것

## 7. 중요한 제품 원칙

1. `publish-ready`와 `auto-published`는 다른 상태다.
2. 외부 플랫폼 발행은 기본적으로 `human-in-the-loop`여야 한다.
3. X는 기본 발행 채널이 아니라 `선택적 수동 승인 채널`이다.
4. 테스트 통과는 필요조건이지만, 제품 완료조건은 아니다.
5. 스코어링과 생성보다도 먼저 입력 데이터의 신뢰도가 보장되어야 한다.

## 8. 성공 지표

| 지표 | 정의 | 초기 목표 |
|---|---|---|
| Valid Trend Yield | 수집된 후보 중 검증 통과 비율 | >= 50% |
| Draft Readiness Rate | 생성 결과 중 publish-ready 상태 도달 비율 | >= 40% |
| QA Pass Rate | 초안 중 QA/정책 게이트 1차 통과 비율 | >= 60% |
| Review Latency | draft 생성 후 리뷰 큐 적재까지 걸리는 시간 | <= 10분 |
| Feedback Coverage | 게시 후 48시간 내 성과 데이터 회수 비율 | >= 90% |

## 9. 최종 산출물 정의

V2.0에서 `getdaytrends`의 최종 산출물은 다음 네 가지다.

1. `Validated Trend Set`
2. `Channel-specific Draft Set`
3. `Publish-Ready Draft Queue`
4. `Performance Feedback Summary`

즉, V2.0의 성공은 "자동으로 X에 올라갔다"가 아니라,
"리스크 없이 검토/발행 가능한 고품질 draft queue가 안정적으로 생성된다"로 판단한다.

## 10. 채널 정책

| 채널 | V2.0 기본 정책 | 비고 |
|---|---|---|
| Notion | 포함 | 내부 저장 및 검토 허브 역할 |
| Internal Review Hub / Dashboard | 포함 | 기본 운영 채널 |
| X | 자동 발행 제외 | 수동 승인 후 수동/보조 발행만 허용 |
| 기타 소셜 채널 | 제외 또는 추후 검토 | V2.0 핵심 범위 아님 |

## 11. 핵심 리스크

| 리스크 | 설명 | 대응 원칙 |
|---|---|---|
| 노이즈 입력 | 의미 없는 트렌드가 생성 단계로 유입 | intake validation 강화 |
| 계약 드리프트 | 모듈 간 필드/시그니처 불일치 | DTO/이벤트 계약 고정 |
| 잘못된 자동 발행 기대 | 기술 가능성과 운영 가능성을 혼동 | X 자동 발행 기본 제외 |
| 품질 착시 | smoke green인데 실제 draft 품질은 낮음 | publish-ready gate 명확화 |
| 피드백 단절 | 게시 후 결과가 다음 전략으로 안 돌아감 | 성과 수집을 코어 범위로 포함 |

## 12. V2.0 Phase

| Phase | 목적 | 구체 작업 | 산출물 | 종료 조건 |
|---|---|---|---|---|
| Phase 1 | Intake Reset | 수집 소스, freshness, dedup, evidence 기준 재정의 | validated intake spec | 잘못된 입력이 뒤 단계로 안 넘어감 |
| Phase 2 | Scoring Reset | viral score, confidence, source quality, velocity 재정의 | scoring rubric | 우선순위 기준이 설명 가능 |
| Phase 3 | Draft Engine | 채널별 draft 생성 규칙과 prompt 버전 고정 | draft generator contract | 같은 입력에 재현 가능한 초안 생성 |
| Phase 4 | Safety Gate | QA, fact, policy, format, persona 기준 통합 | publish-ready gate | 통과/차단 사유가 구조화됨 |
| Phase 5 | Review Queue | Notion/내부 허브에 Ready 큐 생성 | review queue | 사람이 검토 가능한 상태 확보 |
| Phase 6 | Manual Publish Ops | 승인 후 수동 발행 체크리스트 운영 | publish ops checklist | 외부 발행 리스크가 통제됨 |
| Phase 7 | Feedback Loop | 게시 성과와 실패 사유를 전략에 반영 | feedback summary | 다음 실행 품질이 개선됨 |

## 13. 승인 전 확인할 질문

1. V2.0의 공식 최종 산출물을 `publish-ready draft queue`로 확정할 것인가?
2. X를 `수동 승인 채널`로만 유지할 것인가?
3. V2.0의 기본 운영 채널을 `Notion + Internal Review Hub`로 고정할 것인가?
4. 첫 골든 시나리오를 `트렌드 1건 -> QA 통과 -> Ready 큐 적재 -> 성과 회수`로 잡을 것인가?

## 14. 구현 재개 조건

아래가 승인되기 전까지는 큰 구현을 재개하지 않는다.

1. V2.0 범위
2. 채널 정책
3. publish-ready 정의
4. phase별 완료 기준
