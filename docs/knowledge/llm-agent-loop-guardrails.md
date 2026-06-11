# LLM 에이전트 자율 루프 가드레일 — 폭주 방지와 협업 규율

- 작성일: 2026-06-11
- 분류: 프로젝트 운영 지식
- 요약: LLM 에이전트가 외부 차단 게이트를 만나면 멈추거나 사람에게 알리는 대신 주변 작업만 무한 반복하는 폭주가 흔히 일어난다. 업계 표준 해법은 정지 조건(stop condition), 반복 예산(iteration budget), 인간 에스컬레이션 트리거, 작업 단위별 커밋이며, 이를 우리 AGENTS.md와 핸드오프 규약에 명문화한다.

## 왜 우리에게 필요한가

우리 프로젝트에서 실제 사고가 있었다. Codex 실행자가 `remoteWorkflowFilesReady=false`라는 외부 차단 게이트(사람이 풀어야 하는 조건)를 만나자, 에스컬레이션하지 않고 이틀간 bug loop 158회 + refactor loop 152회의 메타 작업(제품이 아닌 주변 정비 작업)만 반복했다. 그 사이 미커밋 파일이 108개 쌓였고 제품 작업은 0건이었다. `handoffs/` 핸드오프 프로토콜은 존재했지만 한 번도 사용되지 않았다. 이는 개인의 실수가 아니라 가드레일(자동 안전장치) 부재의 문제이며, 업계에 이미 검증된 처방이 있다.

## 핵심 지식

### 폭주 패턴: 정지 신호 없는 루프와 goal drift

에이전트는 "환경 피드백을 보고 도구를 반복 호출하는 루프"로 동작하기 때문에, Anthropic은 "최대 반복 횟수 같은 정지 조건을 포함해 통제를 유지하라"고 명시한다. 자율성이 높을수록 비용과 오류가 복리로 누적되기 때문이다([Building effective agents — Anthropic](https://www.anthropic.com/engineering/building-effective-agents)). 또 하나의 패턴이 goal drift(목표 표류: 원래 목표에서 조금씩 벗어나는 현상)다. 평가 연구에 따르면 테스트한 모든 모델이 어느 정도 목표 표류를 보였고, 컨텍스트(대화 기록)가 길어질수록 패턴 매칭 성향이 커지며 표류가 심해진다([Evaluating Goal Drift in Language Model Agents — arXiv](https://arxiv.org/abs/2505.02709)). 우리 사고는 두 패턴의 결합이다: 차단 게이트 앞에서 멈추지 못하고, 목표가 "제품 출시"에서 "루프 돌리기 자체"로 표류했다.

### 정지 조건과 반복 예산은 프레임워크 기본 사양

OpenAI Agents SDK는 에이전트 루프에 `max_turns`(최대 턴 수) 상한을 두고, 초과하면 `MaxTurnsExceeded` 예외를 던져 강제 종료한다 — 하드캡이 선택이 아니라 기본 내장이라는 뜻이다([Running agents — OpenAI Agents SDK](https://openai.github.io/openai-agents-python/running_agents/)). Anthropic의 멀티 에이전트 시스템도 작업 유형별 노력 예산을 명문화한다: 단순 사실 확인은 에이전트 1개·도구 호출 3-10회, 직접 비교는 서브에이전트 2-4개·각 10-15회 식으로, 과잉 작업으로 빠지는 것을 규칙으로 막는다([How we built our multi-agent research system — Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)).

### 인간 에스컬레이션 트리거: 실패 한도 초과

OpenAI 공식 가이드는 인간 개입이 필요한 1차 트리거로 "실패 한도 초과(Exceeding failure thresholds)"를 꼽는다: 재시도·행동 횟수에 한도를 정하고, 이를 넘으면(예: 여러 번 시도해도 진전이 없으면) 인간에게 에스컬레이션하라. 코딩 에이전트라면 제어권을 사용자에게 돌려주는 것이 우아한 실패다([A practical guide to building agents — OpenAI, PDF p.31](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf)). 같은 차단 메시지를 N회 반복해서 만나면 그것이 곧 "진전 없음" 신호다.

### planner-executor 핸드오프와 범위 제한(scope guard)

Anthropic은 기획자(orchestrator)가 실행자(subagent)에게 일을 넘길 때 "각 서브에이전트에는 목표(objective), 출력 형식, 도구 사용 지침, 명확한 작업 경계(task boundaries)가 필요하다"고 못박는다. 상세한 작업 기술이 없으면 "에이전트들은 작업을 중복하고, 빈틈을 남기고, 필요한 정보를 찾지 못한다"([How we built our multi-agent research system — Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)). 핸드오프 문서는 형식적 절차가 아니라 폭주를 막는 범위 울타리다.

### 커밋 케이던스: 작업 단위별 커밋과 진행 기록

Anthropic의 장기 실행 에이전트 하니스 가이드는 "한 번에 한 기능만" 구현하고, 테스트·문서화 후 커밋하고 나서 다음으로 넘어가는 절차를 핵심으로 제시한다. git 이력과 진행 파일(claude-progress.txt)이 다음 세션이 상태를 복원하는 유일한 다리이고, 망가진 변경은 git으로 되돌려 작동 상태를 복구한다([Effective harnesses for long-running agents — Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)). Claude Code 공식 모범 사례도 탐색→계획→구현→커밋을 한 사이클로 묶고, 같은 문제를 두 번 교정해도 안 되면 세션을 리셋하라는 진행도 휴리스틱을 제시한다([Best practices — Claude Code Docs](https://code.claude.com/docs/en/best-practices)). 미커밋 108개 파일은 이 케이던스가 완전히 무너졌다는 증거다.

## 우리 프로젝트에 적용하기

1. **AGENTS.md에 정지 조건 명문화** — `AGENTS.md`에 추가: "동일 차단 게이트(예: `remoteWorkflowFilesReady=false`)를 3회 연속 확인하면 즉시 중단하고, 해당 핸드오프의 반환 섹션에 차단 사유를 적어 기획자에게 반환한다. 게이트를 우회하는 메타 작업은 범위 초과다."
2. **루프 예산(제품:메타 비율)** — AGENTS.md에 "세션당 메타 작업(리팩터·정리·감사)은 제품 작업 1건당 최대 2건. 제품 작업 0건인 세션을 2회 연속 반복 금지" 명시. 세션 종료 시 `WORKLOG.md`에 제품/메타 건수를 함께 기록해 비율을 측정 가능하게 한다.
3. **커밋 케이던스(미커밋 20파일 한도)** — "기능 1개 완료 = 커밋 1개. `git status --porcelain | wc -l` 결과가 20을 넘으면 신규 작업을 시작하지 말고 커밋부터 한다"를 AGENTS.md와 `handoffs/TEMPLATE.md` 체크리스트에 추가.
4. **핸드오프에 scope guard 필드 추가** — `handoffs/TEMPLATE.md`에 목표·출력 형식·작업 경계·정지 조건(이 게이트를 만나면 중단) 4개 필드를 필수화. 차단 시 상태를 DONE이 아닌 BLOCKED로 표기하고 반환한다.
5. **세션 시작 절차** — 실행자는 시작 시 `WORKLOG.md` 최근 기록과 열린 핸드오프를 읽고, 미커밋 파일 수를 먼저 확인한다(이미 전역 지침에 있는 규칙을 AGENTS.md에도 복제해 실행자가 반드시 보게 한다).

## 주의사항 / 흔한 실수

- 정지 조건을 프롬프트 권고문으로만 두면 무시될 수 있다. 가능하면 스크립트·훅처럼 모델 바깥에서 기계적으로 강제하라(Claude Code 문서도 CLAUDE.md 지침은 권고적, 훅은 결정적이라고 구분한다).
- 활동량을 진행도로 착각하지 마라. 루프 횟수·수정 파일 수가 아니라 커밋된 기능 수로 측정한다.
- 에스컬레이션을 실패로 취급하는 분위기가 폭주를 만든다. OpenAI 가이드처럼 "제어권 반환"을 설계된 정상 동작으로 정의하라.
- 차단 게이트를 만나면 게이트 주변을 정비하는 메타 작업으로 도피하기 쉽다. 게이트 해소는 사람 몫이며, 실행자의 올바른 행동은 기록 후 중단이다.
- 한도를 지나치게 빡빡하게 잡으면 정상 작업까지 끊긴다. 정상 작업의 평균 소요를 관찰한 뒤 여유를 두고 상한을 정하고, 운영하며 조정한다(초기 수치는 가설로 표기).
- 핸드오프 문서는 존재만으로는 작동하지 않는다(우리 사고에서 증명됨). 세션 시작 절차에 "열린 핸드오프 확인"을 강제 단계로 넣어야 한다.

## 출처

(모두 접근일 2026-06-11)

- [Building effective agents — Anthropic Engineering](https://www.anthropic.com/engineering/building-effective-agents)
- [Effective harnesses for long-running agents — Anthropic Engineering](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [How we built our multi-agent research system — Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- [A practical guide to building agents — OpenAI (PDF)](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf)
- [Running agents — OpenAI Agents SDK Docs](https://openai.github.io/openai-agents-python/running_agents/)
- [Technical Report: Evaluating Goal Drift in Language Model Agents — arXiv:2505.02709](https://arxiv.org/abs/2505.02709)
- [Best practices for Claude Code — Claude Code Docs](https://code.claude.com/docs/en/best-practices)
