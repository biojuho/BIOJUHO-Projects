# getdaytrends V2.0 Workflow

작성일: 2026-04-02
상태: 승인 전 운영 설계안

## 1. 워크플로우 원칙

이 워크플로우의 기본 철학은 단순하다.

`getdaytrends`는 자동 발행기가 아니라, 고품질 트렌드 기반 콘텐츠를 안전한 검토 큐까지 밀어 올리는 시스템이다.

따라서 기본 경로는 아래와 같다.

`Collect -> Validate -> Score -> Generate -> Safety Gate -> Ready Queue -> Human Review -> Publish -> Learn`

## 2. 운영 모드

| 모드 | 허용 여부 | 설명 |
|---|---|---|
| Draft-only | 허용 | 초안만 생성하고 외부 발행 없음 |
| Ready-queue | 기본 | QA 통과 결과를 Notion/내부 허브에 적재 |
| Manual-assisted Publish | 허용 | 사람이 최종 승인 후 외부 채널 발행 |
| Fully automated X publish | 금지 | 계정 정지/삭제 리스크 때문에 V2.0 기본 경로에서 제외 |

## 3. V2.0 단계별 워크플로우

| Phase | 입력 | 핵심 작업 | 출력 | Owner | Hard Gate |
|---|---|---|---|---|---|
| Phase 1. Collect | 소스별 raw trend | X/뉴스/기타 소스 수집, 중복 후보 기록 | `raw_trends` | `getdaytrends.collectors` | 소스 수집 실패율 기록 |
| Phase 2. Validate | `raw_trends` | freshness 체크, dedup, source evidence 정리, malformed 데이터 격리 | `validated_trends` | intake/validation layer | invalid trend는 quarantine |
| Phase 3. Score | `validated_trends` | confidence, viral potential, velocity, source quality 계산 | `scored_trends` | analyzer | 점수 산식 설명 가능해야 함 |
| Phase 4. Generate | `scored_trends` | 플랫폼별 초안 생성, prompt version 기록 | `drafts` | generator/shared.llm | 필수 메타데이터 누락 시 fail |
| Phase 5. Safety Gate | `drafts` | QA, fact, policy, format, persona/tone 점검 | `ready_drafts`, `rejected_drafts` | QA/review layer | 미통과 draft는 발행 금지 |
| Phase 6. Queue | `ready_drafts` | Notion/내부 허브 적재, 체크리스트 부착 | `publish_ready_queue` | publishing workflow | queue 적재 실패는 운영 장애로 기록 |
| Phase 7. Human Review | `publish_ready_queue` | 사람이 승인/보류/반려 결정 | `approved_drafts` | editor/operator | 승인 없는 외부 발행 금지 |
| Phase 8. Publish | `approved_drafts` | 수동 또는 보조 발행, URL/receipt 기록 | `publish_receipts` | human operator + adapter | X 자동 발행 금지 |
| Phase 9. Learn | `publish_receipts`, metrics | 성과 수집, 실패 분류, prompt/persona/timing 개선 | `feedback_summary` | analytics/review | 피드백 누락률 추적 |

## 4. 상태 전이

| 상태 | 의미 | 다음 상태 |
|---|---|---|
| `collected` | 원시 수집 완료 | `validated`, `quarantined` |
| `validated` | 검증 통과 | `scored` |
| `scored` | 우선순위 계산 완료 | `drafted` |
| `drafted` | 초안 생성 완료 | `ready`, `rejected` |
| `ready` | 게이트 통과, 발행 준비 완료 | `approved`, `rejected`, `expired` |
| `approved` | 사람이 발행 허용 | `published` |
| `published` | 외부 게시 완료 | `measured` |
| `measured` | 성과 수집 완료 | `learned` |
| `learned` | 다음 전략 반영 완료 | next cycle |

## 5. 필수 검증 체크포인트

| 체크포인트 | 확인 내용 | 실패 시 처리 |
|---|---|---|
| Intake Check | source ref, freshness, schema, duplicate state | quarantine + reason 저장 |
| Draft Check | 길이, 형식, 필수 필드, prompt_version | draft reject |
| Safety Check | QA score, fact, policy, hallucination signal | ready 진입 금지 |
| Queue Check | Notion/내부 허브 적재 성공 | retry + ops alert |
| Review Check | 사람 승인 여부 | publish blocked |
| Feedback Check | metrics 회수, receipt 연결 | metrics gap 보고 |

## 6. X 정책

### 허용

- X용 draft 생성
- X용 체크리스트 생성
- 사람이 승인한 후 수동 발행
- 발행 후 URL/성과 기록

### 금지

- 사람 승인 없는 자동 포스팅
- 계정 정책 리스크가 있는 우회성 자동 발행을 기본 경로로 채택
- "토큰만 있으면 된다"는 식의 운영 판단

### V2.0 공식 입장

> X는 자동 발행 채널이 아니라, 승인 후 선택적으로 사용하는 수동 운영 채널이다.

## 7. 운영 산출물

매 실행 주기마다 반드시 남겨야 하는 산출물:

1. `validated_trends`
2. `scored_trends`
3. `draft_batch`
4. `ready_queue_snapshot`
5. `review_decision_log`
6. `publish_receipts`
7. `feedback_summary`

## 8. 실패 처리 규칙

| 실패 유형 | 규칙 |
|---|---|
| 수집 실패 | 부분 실패 허용, 실패 source 기록 |
| 검증 실패 | 다음 단계 전달 금지 |
| 생성 실패 | fallback 가능하되 degraded mode 기록 |
| QA 실패 | draft는 저장하되 ready 진입 금지 |
| queue 적재 실패 | 운영 장애로 승격 |
| 발행 실패 | receipt와 실패 원인 저장, 자동 재발행 금지 |
| metrics 실패 | 다음 주기 보강 시도, coverage 경고 |

## 9. 골든 시나리오

V2.0에서 첫 번째로 보장해야 할 골든 시나리오는 다음이다.

1. 트렌드 1건 수집
2. 검증 통과
3. short-form draft 1건 생성
4. QA/policy/fact gate 통과
5. Notion 또는 내부 허브의 `Ready` 큐에 적재
6. 사람이 승인
7. 수동 발행 후 URL 기록
8. 48시간 내 성과 이벤트 회수

이 시나리오가 안정적으로 돌아가야 그 다음 확장을 허용한다.

## 10. Phase별 실행 우선순위

| 우선순위 | 작업 |
|---|---|
| P0 | `publish-ready` 정의와 queue 기준 확정 |
| P0 | X 자동 발행 제외를 운영 정책으로 고정 |
| P1 | intake validation과 safety gate를 코드/문서 기준으로 일치 |
| P1 | Notion/내부 허브 Ready 큐를 canonical output으로 확정 |
| P2 | feedback loop와 성과 attribution 강화 |

## 11. 승인 후 바로 만들 것

1. `publish-ready` DTO
2. `review decision` schema
3. `publish receipt` schema
4. `feedback summary` schema
5. 골든 E2E 체크리스트
