# Next Actions

> 세션 종료 시 `/session-workflow`가 이 파일의 갱신을 제안합니다.
> 2026-04-18 06:51 기준 — QC PASS 1,981 tests (286+542+463+690). DeSci CI 빌드 스텝 추가, scratch 정리, Canva 토큰 갱신 절차 문서화 완료.

## 완료 항목

- [x] DailyNews smoke 게이트 `pytest` → `uv run` 수정 (S1-2)
- [x] `run_daily_news.py` JSON manifest 출력 (S2-1)
- [x] Telegram `[PRE-FAIL]/[PARTIAL]/[TOTAL-FAIL]` prefix 분류 (S2-2)
- [x] workflow bare command 금지 lint (S1-2)
- [x] `test_env_loader.py` warning 캐시 leak 수정 (S2-3)
- [x] `run_workspace_smoke` shared/tests/ 커버리지 (이미 존재)
- [x] 독립 감시자 워크플로 배포 (S1-5)
- [x] Notion DB 단일화: config.py에서 `NOTION_TASKS_DATABASE_ID` 미설정 시 `NOTION_REPORTS_DATABASE_ID`로 자동 fallback
- [x] pytest capture crash 해결: dashboard `api.py`의 `sys.stdout` 교체가 pytest를 파괴하는 버그 수정
- [x] pytest 8.3.x 핀 고정: 4개 pyproject.toml에서 `>=8.3,<8.4` 범위로 고정
- [x] DailyNews `news_bot.py` 레거시 의존성 분리: `category_filter.py` 추출 + 3개 active 스크립트 마이그레이션
- [x] pytest-asyncio loop scope 경고 해결
- [x] DailyNews `report-economy_global` 수동 보강 + Notion 재동기화
- [x] **pipeline_state.db stale running job 정리** — `refresh_dashboard` 좀비 → `failed` 전환 (2026-04-17)
- [x] **biolinker pytest → `[project.optional-dependencies].dev` 이동** (2026-04-17)
- [x] **news_bot.py 완전 제거** — 1,222줄 삭제 + test_category_filter_migration.py 7개 테스트 재작성 (2026-04-17)
- [x] **`run_scheduled_insights.ps1` manual-only 정렬** — `Auto-publishing` 문구 제거 + `--approval-mode manual` 반영 (2026-04-17)

## Backlog (향후 진행 가능)

- [x] Economy_Global 갱신본 X 초안 검토 후 실제 발행 여부 결정
- [x] Economy_Global Canva 카드 생성/디자인 검수 후 게시 자산 확정
- [x] DailyNews 수동 큐레이션 경로에 "기존 Notion 페이지 overwrite + channel_publications refresh" 자동화 추가
- [x] Dashboard CI 워크플로 리뷰 및 머지 (GHA workflow 파일 대기 중)
- [x] `category_filter.py` docstring "deprecated 2026-03-04" 문구를 "Originally extracted from…" 으로 업데이트 (LOW, ~2분)
- [x] `proofreader.py`, `sentiment_analyzer.py` 주석의 news_bot.py 참조 정리 (LOW, ~5분)
- [x] DeSci Platform Frontend CI 빌드 스텝 추가 + 로컬 빌드 검증 (2026-04-18)
- [ ] `.smoke-tmp/` 및 `.test-tmp/` 내 permission-denied 잔류 디렉토리 정리 (관리자 PowerShell 필요)
- [x] scratch 파일 정리: `automation/DailyNews/scratch_*.py` 3개 삭제 완료 (2026-04-18)
- [ ] X 수동 발행: Economy_Global 최종 문안 + posting 이미지 → X 게시 후 URL 기록
- [x] Canva `invalid_grant` 진단 완료 — `canva_auth_server.py` PKCE 갱신 절차 문서화 (2026-04-18)
- [ ] 미커밋 DailyNews CLI + getdaytrends 변경 정리/커밋

## 다음 세션 복붙 메모

```text
DailyNews Economy_Global 후속 진행:
- Canva 카드 수정본 저장 완료. 편집 링크: https://www.canva.com/d/boGsMspzVS9l_5B
- 수동 큐레이션 재동기화 자동화 추가 완료.
- 재실행 커맨드: uv run python -m antigravity_mcp ops resync-report --report-id report-economy_global-20260416T220508Z
- 최신 Notion 백업: automation/DailyNews/data/notion_backups/report-economy_global-20260416T220508Z.before-notion-resync-20260417T020633Z.json
- 최신 Canva 디자인 확인: DAHHEnyVbfQ (IMF 3.1% / Fed war shock / U.K. GDP beats estimates)
- 게시용 자산 확정: automation/DailyNews/output/Economy_Global_Card_posting.png (1080x1350)
- 참고: 기존 automation/DailyNews/output/Economy_Global_Card.png 는 최신 Canva 수정본 이전의 stale 로컬 산출물
- 정책 기록: X 업로드는 계정 리스크 때문에 자동화하지 않고 수동 발행만 유지
- 확인 결과: `channel_publications` 기준 X는 아직 `draft` 이고 `external_url` 이 비어 있음
- 확인 결과: 공개 웹 검색 기준 최종 문안과 일치하는 X 게시물은 `2026-04-17 20:35:49 +09:00` 시점까지 확인되지 않았음
- 확인 결과: Canva connector 메타데이터상 최신 디자인 `updated_at` 은 `2026-04-17 19:56:06 +09:00` 이지만 connector 노출본은 `400x500` thumbnail 뿐이었음
- 확인 결과: `automation/DailyNews/scripts/canva_generator.py` export 재시도는 여전히 `invalid_grant` 로 실패
- 이번 세션 추가: `uv run python -m antigravity_mcp ops record-manual-x-post --report-id report-economy_global-20260416T220508Z --post-url "<ACTUAL_X_URL>" --posted-at "2026-04-17T00:00:00+09:00"` 명령 추가 완료
- 이번 세션 확인: 위 명령은 `content_reports.drafts_json`, `channel_publications`, `x_tweet_metrics` 를 함께 갱신하므로 이후 `resync-report` 에 덮어써지지 않음
- 정책 정렬: `run_scheduled_insights.ps1` 는 이제 manual-only 표현과 `--approval-mode manual` 을 사용
- 최종 X 권장 문안: IMF가 2026년 세계 성장률 전망을 3.3%에서 3.1%로 낮췄습니다. 연준 윌리엄스는 전쟁 충격이 성장률을 2%대에 묶고 물가를 3% 안팎에 남길 수 있다고 경고했습니다. 영국 GDP가 예상보다 강했어도, 시장의 초점은 다시 스태그플레이션 리스크로 이동 중입니다. #글로벌경제 #매크로
- 권장 다음 액션:
  1. 준비된 이미지와 위 최종 문안을 수동으로 계정에 복사하여 X에 발행
  2. 게시 직후 `record-manual-x-post` 명령으로 실제 X URL/시각을 로컬 상태에 반영
  3. 가능하면 최신 Canva 디자인에서 원본 비율로 수동 export 받아 로컬 posting asset 교체
  4. HANDOFF.md에 실제 X 발행 URL과 최종 게시 시각 기록
```
