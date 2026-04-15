# Next Actions

> 세션 종료 시 `/session-workflow`가 이 파일의 갱신을 제안합니다.
> 2026-04-15 08:30 기준 — 오늘 아침 DailyNews 스케줄 실패(smoke 게이트 `pytest: command not found`) post-mortem 완료, 수동 발행 완료, fix 적용됨 (미커밋).

## Safe Auto (확인 없이 진행 가능)

- [safe_auto] DailyNews `.github/workflows/dailynews-pipeline.yml` smoke 게이트 `pytest` → `uv run --package DailyNews pytest` 수정 커밋 + 다음 22:00 UTC 스케줄 런 녹색 확인
- [safe_auto] `run_daily_news.py` 종료 시 JSON manifest 출력(published_categories/target_db/first_page) → workflow의 Telegram heartbeat에 포함 (post-mortem §5.1)
- [safe_auto] Telegram 실패 메시지 `[PRE-FAIL]/[PARTIAL]/[TOTAL-FAIL]` prefix 분류 (post-mortem §5.2)
- [safe_auto] workflow yml 내 bare `pytest`/`python` 금지 lint (post-mortem §5.4)
- [safe_auto] `packages/shared/tests/test_env_loader.py::test_no_warning_for_non_root_keys` — 단독 실행 OK지만 shared 전체 실행 시 `assert 1 == 0` 실패 (warning 캐시 leak). 테스트 순서 의존성 제거 필요
- [safe_auto] `run_workspace_smoke`에 `packages/shared/tests/` 커버리지 추가 — 현재 smoke는 workspace-level 테스트만 돌림, shared 내부 회귀는 감지 못함

## Needs Approval (진행 전 확인 필요)

- [needs_approval] 독립 감시자 워크플로: 마지막 DailyNews success가 13h 이상 지났으면 Telegram `[MISSING]` 알림 (신규 workflow 파일 추가, post-mortem §5.3)
- [needs_approval] DailyNews Notion DB 단일화 확정: `.env`에 `NOTION_TASKS_DATABASE_ID`와 `NOTION_REPORTS_DATABASE_ID`가 같은 DB(`bb5cf3c8...16b7`)를 가리킴. tasks용 별도 DB를 만들지 or 단일화로 확정하고 tasks 참조를 코드 전역에서 제거할지 결정 필요 (post-mortem §5.5)
