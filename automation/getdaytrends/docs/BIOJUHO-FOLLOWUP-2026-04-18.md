# Biojuho Voice Follow-up

## 이번 라운드에서 반영한 것

- 주제 선별에 `persona axis` 게이트를 추가했다.
- usable 외부 소스 수가 부족하면 큐에서 제외되도록 바꿨다.
- `biojuho` 전용 X / Threads / long-form / blog 프롬프트를 분리했다.
- 블로그는 고정 4단 구조 대신 3개 구조 로테이션으로 전환했다.
- X 로그인 셸 페이지와 30일 초과 뉴스는 트렌드 근거로 약하게 보지 않고 제거하도록 조정했다.
- QA에 밈 슬랭, 이모지 과다, clipped ending 반복, AI 프레임 과수렴 감점을 추가했다.

## 회의 후 추가 개선안

### 1. Persona Filter 2차 고도화

- 현재는 키워드 매칭 기반이다.
- 다음 단계는 `axis classifier`를 별도 점수로 분리하는 것이다.
- 권장 방식:
  - `fit_score = topical_fit + audience_fit + voice_fit`
  - `topical_fit`은 rule 기반
  - `audience_fit`은 과거 승인 데이터 기반
  - `voice_fit`은 LLM QA 또는 경량 분류기로 추정

### 2. Internal Metric / Public Copy 완전 분리

- public prompt에서는 viral score 노출을 막았지만, downstream storage와 review 화면도 분리하는 편이 좋다.
- 권장 작업:
  - Notion review DB에는 `internal_score`, `public_copy`, `editor_notes` 컬럼을 분리
  - public export path에서는 internal metrics를 완전히 제거

### 3. Source Diversity Hard Gate

- 지금은 usable source count가 기준이다.
- 다음 단계는 `source_type diversity`를 추가하는 것이다.
- 권장 규칙:
  - `X + News`
  - `Reddit + News`
  - `X + Google Trends`
  - 위 조합 중 하나를 만족하지 못하면 publish queue에 올리지 않음

### 4. Topic Eligibility Layer

- 바이럴 주제라고 해도 계정 정체성과 맞지 않으면 드롭해야 한다.
- 권장 정책:
  - `hard pass`: bio / systems / content engineering / investing / saju
  - `soft pass`: culture topic but can be structurally reinterpreted
  - `hard drop`: fandom-only, meme-only, cosplay-only, patch-note-only topics

### 5. Voice Consistency Memory

- 현재 프롬프트는 voice rules를 강하게 준 상태다.
- 다음 단계는 `approved post bank`를 QA와 generation 모두에 재사용하는 것이다.
- 권장 작업:
  - 최근 승인된 카피 30~50개를 모아 `voice reference bank` 생성
  - generation prompt에는 2~3개만 넣고
  - QA에서는 semantic distance로 `biojuho similarity` 측정

### 6. Review Loop 강화

- 지금 시스템은 생성 품질을 막는 수준까지 왔다.
- 다음 단계는 `쥬팍이 실제로 올린 것 / 보류한 것 / 수정한 것`을 학습하는 것이다.
- 권장 데이터:
  - original draft
  - edited draft
  - final published draft
  - rejected reason
  - performance summary after 24h / 72h

### 7. Blog Structure Pool 확장

- 현재는 3개 구조 풀이다.
- 다음 단계는 최소 6개 구조로 늘리는 편이 좋다.
- 추천 추가 구조:
  - signal -> misread -> correction
  - anecdote -> contradiction -> broader pattern
  - timeline -> inflection point -> forecast

### 8. AI Convergence Guard v2

- 현재는 `AI` 과다 언급을 QA에서 감점한다.
- 다음 단계는 generation stage에서 먼저 막는 편이 더 좋다.
- 권장 규칙:
  - topic이 AI native가 아니면 `AI frame candidate`를 1개 이하로 제한
  - 5개 초안 중 1개는 반드시 non-AI lens로 생성

### 9. Meeting Decision Needed

- 아래 세 가지는 운영 철학에 가까워서 회의에서 확정하는 것이 좋다.
- 결정 항목:
  - `hard drop topic list`를 어디까지 강하게 둘지
  - `investing`과 `saju`를 메인 축으로 얼마나 자주 노출할지
  - public 톤을 어디까지 건조하게 가져갈지

## 추천 실행 순서

1. approved post bank 수집
2. hard drop topic list 확정
3. source diversity hard gate 도입
4. review DB에 edited / rejected feedback 추가
5. voice similarity QA 추가
