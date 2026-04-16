# Next Actions

> 세션 종료 시 `/session-workflow`가 이 파일의 갱신을 제안합니다.
> 2026-04-16 09:47 기준 — Backlog 항목 1 완료 + pytest capture crashfix 적용.

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

## Backlog (향후 진행 가능)

- [ ] DailyNews `news_bot.py` (v1 레거시 파이프라인) 점진적 deprecation 검토
- [ ] 나머지 dirty worktree 정리 및 논리적 커밋 분류 (biolinker, agriguard, shared 등 ~26 파일)
- [ ] pytest 8.3.5 → pyproject.toml 핀 고정 (현재 수동 설치)
