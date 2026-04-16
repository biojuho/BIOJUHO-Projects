# Next Actions

> 세션 종료 시 `/session-workflow`가 이 파일의 갱신을 제안합니다.
> 2026-04-17 08:48 기준 — Backlog 3건 완료. 인프라 안정화 완료.

## 완료 항목

- [x] DailyNews smoke 게이트 `pytest` → `uv run` 수정 (S1-2)
- [x] `run_daily_news.py` JSON manifest 출력 (S2-1)
- [x] Telegram `[PRE-FAIL]/[PARTIAL]/[TOTAL-FAIL]` prefix 분류 (S2-2)
- [x] workflow bare command 금지 lint (S1-2)
- [x] `test_env_loader.py` warning 캐시 leak 수정 (S2-3)
- [x] `run_workspace_smoke` shared/tests/ 커버리지 (이미 존재)
- [x] 독립 감시자 워크플로 배포 (S1-5)
- [x] Notion DB 단일화: config.py에서 `NOTION_TASKS_DATABASE_ID` 미설정 시 `NOTION_REPORTS_DATABASE_ID`로 자동 fallback. 동일 ID 중복 경고 추가.
- [x] `.env`에서 `NOTION_TASKS_DATABASE_ID` 라인 제거 후 CI에서 fallback warning이 정상 출력되는지 확인 → `.env`에 이미 미존재 확인, `test_config_aliases.py` 3 passed
- [x] pytest capture crash 해결: dashboard `api.py`의 `sys.stdout` 교체가 pytest capture 시스템을 파괴하는 버그 수정 → 287 passed (workspace), 417 passed (DailyNews), 690 passed (GDT)
- [x] pytest 8.3.x 핀 고정: 4개 pyproject.toml에서 `>=8.3,<8.4` 범위로 고정 (8.4+ Python 3.13 capture crash 방지)
- [x] DailyNews `news_bot.py` 레거시 의존성 분리: `_is_relevant_to_category`를 `domain/category_filter.py`로 추출. 3개 active 스크립트 import 마이그레이션 완료.
- [x] pytest-asyncio loop scope 경고 해결: `asyncio_default_fixture_loop_scope = "function"` 설정 추가

## Backlog (향후 진행 가능)

- [ ] DailyNews `news_bot.py` 완전 제거 (현재 테스트 2개가 직접 참조 — deprecated mark 후 제거 예정)
- [ ] `biolinker/pyproject.toml`에서 pytest를 `[project.optional-dependencies].dev`로 이동 (현재 main deps에 혼재)
- [ ] Dashboard CI 워크플로 리뷰 및 머지 (GHA workflow 파일 대기 중)
