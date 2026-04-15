# Next Actions

> 세션 종료 시 `/session-workflow`가 이 파일의 갱신을 제안합니다.
> 2026-04-15 12:59 기준 — Sprint 2 완료: warning leak 수정, JSON manifest 추가, Telegram prefix 분류 적용.

## Safe Auto (확인 없이 진행 가능)

- [x] ~~DailyNews `.github/workflows/dailynews-pipeline.yml` smoke 게이트 `pytest` → `uv run --package DailyNews pytest` 수정~~ (S1-2에서 완료)
- [x] ~~`run_daily_news.py` 종료 시 JSON manifest 출력~~ (S2-1에서 완료)
- [x] ~~Telegram 실패 메시지 `[PRE-FAIL]/[PARTIAL]/[TOTAL-FAIL]` prefix 분류~~ (S2-2에서 완료)
- [x] ~~workflow yml 내 bare `pytest`/`python` 금지 lint~~ (S1-2에서 완료)
- [x] ~~`packages/shared/tests/test_env_loader.py::test_no_warning_for_non_root_keys` — warning 캐시 leak 수정~~ (S2-3에서 완료)
- [x] ~~`run_workspace_smoke`에 `packages/shared/tests/` 커버리지 추가~~ (이미 존재 확인)

## Needs Approval (진행 전 확인 필요)

- [x] ~~독립 감시자 워크플로~~ (S1-5에서 완료)
- [needs_approval] DailyNews Notion DB 단일화 확정: `.env`에 `NOTION_TASKS_DATABASE_ID`와 `NOTION_REPORTS_DATABASE_ID`가 같은 DB(`bb5cf3c8...16b7`)를 가리킴. tasks용 별도 DB를 만들지 or 단일화로 확정하고 tasks 참조를 코드 전역에서 제거할지 결정 필요 (post-mortem §5.5)
