# DailyNews 2026-04-15 아침 발행 실패 Post-Mortem + 개선안

작성일: 2026-04-15 KST
관련 파일: [dailynews-pipeline.yml](/.github/workflows/dailynews-pipeline.yml)
선행 계획: [DAILYNEWS_GHA_PIPELINE_IMPROVEMENT_PLAN_2026-04-14.md](./DAILYNEWS_GHA_PIPELINE_IMPROVEMENT_PLAN_2026-04-14.md)

## 1. 증상

사용자 리포트: "오늘도 노션에 뉴스가 안 들어왔다. 계속 되는 문제 같다."

## 2. 타임라인 (UTC 기준)

| 시각 | 이벤트 |
| --- | --- |
| 2026-04-14 20:08 | Safe Auto 인프라 안정화 커밋 (4e4c201) — smoke 게이트 포함된 어제 수정안이 main 반영됨 |
| 2026-04-14 22:00 | `0 22 * * *` cron 예정 시각 (= 07:00 KST 2026-04-15, 아침 브리프) |
| 2026-04-14 22:33 | GitHub Actions가 지연 후 스케줄 실행 시작 (run 24426293342) |
| 2026-04-14 22:33:53 | "Run DailyNews smoke tests" 단계에서 `pytest: command not found` (exit 127) |
| 2026-04-14 22:33:53 | "Run DailyNews pipeline" 단계가 skipped, Telegram FAIL 알림 전송 |
| 2026-04-14 23:28~23:34 | 사용자 세션에서 로컬 `--force` 수동 실행, 6개 카테고리 정상 발행 (2026-04-15 리포트) |

## 3. 근본 원인

`.github/workflows/dailynews-pipeline.yml` line 117~121의 스모크 테스트 게이트가 `pytest ...`를 직접 호출.

```yaml
- name: Run DailyNews smoke tests
  run: |
    pytest automation/DailyNews/tests/test_run_daily_news.py ... -q
```

GHA 러너에서는 `uv sync --package DailyNews`로 설치된 pytest가 uv가 만든 가상환경 안에만 존재한다. 러너 쉘의 PATH에는 잡히지 않으므로 `pytest` 커맨드가 절대 해결되지 않는다. 결과:

```
/home/runner/work/_temp/<hash>.sh: line 1: pytest: command not found
##[error]Process completed with exit code 127.
```

이 게이트는 2026-04-14 개선 패스에서 "pre-run smoke gate"로 추가됐다. 로컬(사용자 환경)에서는 시스템 또는 프로젝트 venv에 pytest가 있기 때문에 YAML parse + 로컬 pytest 실행만 검증됐고, 실제 GHA 러너에서는 첫 스케줄 실행 때 바로 터졌다.

**실패 확산 경로**: 게이트 step 실패 → `Run DailyNews pipeline` step이 `if` 없이 선언돼 있으므로 기본 `success()` 조건에 의해 skipped → Notion 업로드 0건 → 사용자 입장에서 "뉴스가 안 들어왔다".

### 3.1. 이 증상이 "반복되는 문제"로 느껴진 이유

사용자가 "계속 되는 문제" 라고 인식한 배경을 메모리로 재구성:

1. 2026-04-12: Notion DB ID 중복, union 리턴 문제 (일부 해결됐으나 "가짜 success" 잔재)
2. 2026-04-13: GHA가 getdaytrends DB로 잘못 발행, 전용 시크릿으로 분리. "fake success로 마감되는 문제"가 남음
3. 2026-04-14: 6건 수정 (KST label, Name, partial-fail, cron catch-up, 누락 deps, msg 정확도) + smoke 게이트 신설
4. 2026-04-15: 바로 그 smoke 게이트 자체가 오늘 아침 실패의 원인

즉 전혀 다른 근본 원인 3건이 같은 "Notion에 오늘 글이 없다"라는 표면 증상으로 관측됐고, 매번 다른 레이어에서 수정됐다. **증상 동일성으로 재발처럼 보이지만 원인은 매번 새롭다.** 핵심 문제는 원인이 아니라 **관찰성 부족**이다. "발행됐는가 / 어디에 발행됐는가 / 몇 건인가"를 Notion 밖에서 한눈에 확인할 채널이 없다.

## 4. 즉시 조치 (이번 세션에 적용)

### 4.1. smoke 게이트 수정 (커밋 예정)

`pytest` → `uv run --package DailyNews pytest`.

```diff
- name: Run DailyNews smoke tests
  env:
    PYTHONUTF8: "1"
  run: |
-   pytest automation/DailyNews/tests/test_run_daily_news.py automation/DailyNews/tests/unit/test_config_aliases.py -q
+   uv run --package DailyNews pytest automation/DailyNews/tests/test_run_daily_news.py automation/DailyNews/tests/unit/test_config_aliases.py -q
```

검증 방법: 다음 스케줄 런이 녹색이면 해결. 수동 검증은 workflow_dispatch로 즉시 가능.

### 4.2. 오늘자 (2026-04-15) 수동 발행

로컬에서 `uv run python scripts/run_daily_news.py --force --max-items 5` 실행 완료. Notion DB `bb5cf3c8d2bb4b8ba866ba9ea86f16b7`에 6개 카테고리(Tech, Economy_KR, Economy_Global, Crypto, Global_Affairs, AI_Deep) 페이지 생성 확인.

## 5. 구조적 개선안 (다음 세션들)

### 5.1. 관찰성 — "발행됐는가"를 Notion 밖에서 확인 가능하게

현재 Telegram heartbeat는 `[OK] DailyNews #74 completed` 수준. 부족한 정보:

- 발행된 카테고리 수
- 실제 Notion page_id / URL
- DB 대상 (잘못된 DB에 가더라도 heartbeat는 성공)

**제안**: `run_daily_news.py`가 종료 시 structured manifest를 STDOUT 또는 artifact로 남기고, workflow의 "Telegram heartbeat on success" step이 그 manifest를 읽어 다음 내용을 붙인다.

```
[OK] DailyNews #74 (morning-window)
published: 6/6 categories, 58 articles
target_db: bb5cf3c8...16b7
first_page: https://www.notion.so/<page_id>
```

`target_db`를 heartbeat에 넣어두면 secret 오설정(2026-04-13 문제)도 즉시 드러난다.

### 5.2. 실패 분류 — "어느 층에서 막혔나"

현재 `if: failure()` 블록 하나가 모든 실패를 같은 포맷으로 알린다. 다음 3단계로 분리:

1. **Pre-run failure** (checkout / uv install / smoke tests): 인프라/코드 문제. 재시도 의미 없음.
2. **Pipeline partial** (일부 카테고리만 실패): 일부 기능 저하. 수동 재실행 권장.
3. **Pipeline total failure** (전 카테고리 실패 또는 업로드 0건): 즉시 수동 발행 필요.

Telegram 메시지 prefix를 `[PRE-FAIL]` / `[PARTIAL]` / `[TOTAL-FAIL]`로 구분. 셋 다 `failure()`이지만 근본 원인 분류가 다르다.

### 5.3. Schedule 지연 / skip 감지

GHA free tier cron은 흔히 5~30분 지연되고 드물게 skip된다. 현재 "안 뛰었다"와 "실패했다"를 구분하지 못한다.

**제안**: 별도 GHA workflow 또는 외부 cron (Cloud Scheduler)이 매 시간 "가장 최근 DailyNews success가 13시간 이내인가"를 체크하고, 아니면 Telegram `[MISSING]` 알림. 이 감시자는 DailyNews 파이프라인과 완전히 독립된 채널로 운영한다 (같은 이유로 죽지 않도록).

### 5.4. 로컬과 GHA의 실행 동치성 확보

오늘 사고의 본질은 "로컬에서는 되는데 GHA에서는 안 된다". 재발 방지:

1. 모든 pytest/python 호출을 `uv run` 접두로 통일. 게이트에 lint 룰 추가.
2. 사전 커밋 훅 또는 CI에 "workflow yml YAML parse + grep for bare `pytest |python ` outside uv run" 체크 (단순 regex 게이트면 충분).
3. 기존 `ops/scripts/` 에 `check_workflow_runners.py` 정도의 유효성 검증 스크립트 추가.

### 5.5. DB ID 단일화 검증

현재 `.env`의 `NOTION_TASKS_DATABASE_ID`와 `NOTION_REPORTS_DATABASE_ID`가 **동일** (`bb5cf3c8...16b7`). 2026-04-12 메모리의 "Notion DB ID 중복" 이슈가 구조적으로는 그대로 남아있다.

- 의도적 단일화인지 분리가 필요한지 확정
- 분리가 필요하면 tasks용 별도 DB 생성 + `DAILYNEWS_NOTION_TASKS_DB_ID` 시크릿 등록
- 단일화가 의도면 `NOTION_TASKS_DATABASE_ID`를 env에서 제거하고 코드 전역에서 `NOTION_REPORTS_DATABASE_ID` 한 개만 참조하도록 정리

2026-04-14 계획의 "Outstanding operator follow-up" 과 동일한 항목이지만 **아직 미해결**.

## 6. 작업 큐 (next-actions.md 연동)

| 우선순위 | 항목 | 유형 |
| --- | --- | --- |
| P0 | smoke 게이트 `uv run` 수정 커밋 + 다음 cron 런 관찰 | safe_auto |
| P1 | `run_daily_news.py`가 manifest(JSON) 출력 → workflow step이 heartbeat에 포함 | safe_auto |
| P1 | `[PRE-FAIL]/[PARTIAL]/[TOTAL-FAIL]` 실패 분류 Telegram 메시지 | safe_auto |
| P2 | 독립 감시자 워크플로 (발행 지연 13h 감지) | needs_approval (새 workflow) |
| P2 | workflow yml 내 bare pytest/python 금지 lint | safe_auto |
| P3 | DB ID 단일화 최종 결정 (사용자 판단 필요) | needs_approval |

## 7. 검증 체크리스트

- [x] 오늘자 2026-04-15 Notion 발행 6개 카테고리 확인
- [x] `dailynews-pipeline.yml` smoke 게이트 수정
- [ ] 커밋 + 다음 스케줄 런 녹색 확인 (22:00 UTC 2026-04-15)
- [ ] P1 manifest/heartbeat 강화 작업 착수

## 8. 메모리 업데이트 제안

`project_dailynews_morning_fix_2026-04-14.md` 업데이트 또는 새 메모리 `project_dailynews_smoke_gate_fix_2026-04-15.md` 생성:

- 어제 추가한 smoke 게이트가 `pytest` bare call이어서 오늘 아침 실행을 전부 막았음
- GHA uv 환경에서 python tool 호출은 반드시 `uv run` 필요
- "계속 되는 문제"로 인식되는 아침 발행 실패는 매번 다른 레이어가 원인이므로 관찰성/분류 강화가 근본 해법
