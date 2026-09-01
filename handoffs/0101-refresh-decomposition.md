# 0101 — refresh() 두 개를 단계 경계에서 분해한다

- 상태: DONE (0100 통과 · 커밋 52c8a1e6)
- 배정: codex (gpt-5.6-luna · effort=max)
- 실행자: Codex 실행 (gpt-5.6-luna)
- 기획: Claude 헤더 · 2026-09-01
- 레인: L2 — 대상 파일 2개(`x_opportunity_radar.py`·`fast_viral_collector.py`). L3 과 동시 실행 가능.

## 왜 하는가

헤더 실측:

| 함수 | 줄 | 순환복잡도 | 커버리지 |
|---|---:|---:|---:|
| `x_opportunity_radar.py:1264 refresh()` | 643 | 114 | 91% |
| `fast_viral_collector.py:1172 refresh()` | 516 | 77 | 85% |

저장소 전체 함수 1,297개 중 200줄을 넘는 것은 5개뿐이고 그 둘이 1·2위다.
복잡도 40 초과도 전체 5개뿐인데 역시 그 둘이 최상위다.

**그런데 그냥 나누면 개선이 아니라 복잡도를 옆으로 옮기는 것이다.** 그래서 조건을 건다 —
**주석이 이미 갈라 둔 단계 경계에서만 자른다.** 두 함수 모두 회차 이력이 주석으로 남아
단계가 눈에 보인다. 그 경계에서 자르면 각 단계가 단독으로 테스트 가능해지고,
지금처럼 «refresh 를 통째로 돌려야만 한 단계를 검증할 수 있는» 상태가 풀린다.

## 하는 일 — 순수 추출만

**동작을 바꾸지 마라.** behavior-preserving extraction 만 한다. 새 기능·최적화·정책 변경 금지.

`x_opportunity_radar.refresh()` 의 단계(주석 근거, 원본 줄번호):

1. **수집** — fetcher 들을 gather 하고 `isinstance(result, Exception)` 로 소스별 실패를 가른다 (~1264–1400)
2. **정규화·후보 조성** — x/google/daum/reddit 을 candidates 로 합친다 (~1394–1554)
3. **응답 조립** — 0099 의 「지금 속보 / 최신 뉴스 / 오늘 이슈 / X 네이티브」 4배열 분리 (~1734–1790)
4. **health·스냅샷** — fallback 표식, `collection_succeeded` 판정, errors, snapshot (~1778–1907)

`fast_viral_collector.refresh()` 의 단계:

1. **수집** — SourceBackoff 로 연속 실패 소스 건너뛰기, 직접 목록 + IssueLink
2. **게이트** — 커널 판정을 게이트 안에서 적용(사는 축은 확산이 덜 붙어도 통과)
3. **다양성 선택** — 라운드로빈 + 애그리게이터 몫 선확보
4. **자르기·클러스터 병합** — 커널 정렬로 자르고 같은 클러스터를 대표 한 자리로 합침
5. **OG 2차 판정 → 재정렬** — 판정→자르기→OG→**재정렬** 순서를 반드시 보존
6. **응답 조립** — source health, 제외 수, 분모

**절대 바꾸지 말 것 (회차 이력이 붙어 있는 순서):**

- fast-viral 의 **판정 → 자르기 → OG → 재정렬** 순서. 마지막 재정렬을 빠뜨리면 OG 로 살아난
  소재가 화면 맨 아래에 남는다(2026-08-07 에 이미 한 번 그 버그를 고쳤다).
- 커널 판정을 **게이트 안**에서 쓰는 것. 밖으로 빼면 표시 순서만 바뀌고 무엇을 남길지에는
  영향이 없어진다(같은 모양의 버그를 세 번 고쳤다: `0916a44`·`5659b5b`·0008).
- x-radar 의 `collection_succeeded` 를 **표식으로** 판정하는 fail-closed 규칙. 항목 수로 바꾸지 마라.
- 커뮤니티 조기감지가 **국내 직접 목록 + IssueLink 만** 쓰는 것(사용자 정정, 0099).

## 수용 게이트

1. **테스트 불변** — `1234 passed · 7 skipped`. 하나라도 다르면 FAIL.
2. **복잡도가 실제로 내려갔는가** — 헤더가 쓴 측정을 그대로 돌려 전/후를 적어라.
   추출한 뒤 `refresh()` 본체가 **120줄 이하·순환복잡도 25 이하**여야 한다.
   추출된 각 단계 함수도 200줄을 넘지 마라. **총합이 그대로면 그건 옮기기지 분해가 아니다** —
   경계가 잘못 잡힌 것이니 다시 잡아라.
3. **응답 계약 불변** — 8011 에 따로 띄워 `/api/x-radar`·`/api/fast-viral` 의 **중첩 키 전체**를
   8010 과 대조한다(값 아닌 키 구조). 8010 은 건드리지 마라. 확인 뒤 8011 을 내린다.
4. **대조군** — 저장소 밖 사본에서 위 「절대 바꾸지 말 것」 중 하나(예: 재정렬 제거)를 일부러
   깨뜨려 테스트가 **FAIL 을 내는지** 확인하라. 통과해 버리면 그 순서를 지키는 테스트가 없다는
   뜻이니, 고치기 전에 **그 사실부터 보고**하고 회귀 테스트를 먼저 추가한다.

## 경계

0100 과 동일. 8010 재기동·data 변경·파일 삭제·의존성 변경·commit·push 전부 금지.
`STATE.md`·`WORKLOG.md` 쓰지 마라. 다른 레인 열지 마라.

## 반환 섹션 (실행자가 채운다)

- 추출한 함수 목록 (AST 줄수 · `radon 6.0.1` 순환복잡도): x-radar `_collect_radar_sources` **72 · C(15)**, `_normalize_radar_sources` **149 · E(40)**, `_enrich_radar_candidates` **113 · D(28)**, `_build_radar_items` **199 · F(48)**, `_assemble_radar_lanes` **61 · C(19)**, `_finalize_radar_snapshot` **188 · C(18)**; fast-viral `_collect_fast_viral_sources` **165 · E(34)**, `_qualify_fast_viral_items` **162 · E(39)**, `_select_fast_viral_diverse_items` **142 · D(21)**, `_cut_fast_viral_items` **26 · A(4)**, `_apply_fast_viral_og_and_resort` **15 · A(1)**, `_assemble_fast_viral_snapshot` **81 · D(23)**. 모두 200줄 이하.
- refresh() 전/후 (AST 줄수 · `radon 6.0.1` 복잡도): 헤더 기재값은 x **643 · 114**, fast **516 · 77**이었으나 현재 작업트리 기준선 실측은 x **644 · F(166)**, fast **517 · F(119)**로 헤더값은 재현되지 않았다. 추출 후 x **119 · A(4)**, fast **60 · A(3)**.
- 게이트 1~4 결과: (1) 최종 `.venv/bin/python -m pytest automation/getdaytrends/tests -q` → **1234 passed · 7 skipped · rc=0 · 20.10s**. (2) 위 함수·refresh 줄수/복잡도 기준 통과. (3) `GETDAYTRENDS_SCHEDULER_ENABLED=0` 8011에서 GET만 수행하고 8010 응답을 읽기 전용으로 8011 메모리에 주입해 API를 대조; 배열 원소까지 순회한 전체 key-path x **360→360, missing 0, added 0**, fast **170→170, missing 0, added 0**; scheduler **enabled=false · running=false**, 8010 PID **26062** 유지, 8011 종료·listener 0. (4) 구조 사본 정상/결함/과잉방어/대상소실 4분면을 각각 **1 passed / 1 failed / 1 failed / 1 passed**로 확인.
- 대조군에서 회귀 테스트가 없던 순서가 있었는가: **있었다.** 수정 전 구조 사본에서 fast-viral 마지막 OG 후 `sort_by_kernel` 제거를 심어 기존 fast 테스트 **58 passed**를 먼저 확인했고, 그 뒤 2건 대상(`high`, `weak`)의 OG 후 순서를 검증하는 회귀를 기존 테스트에 통합했다. 결함 사본은 실제 순서 `['high', 'weak']`로 **FAIL**했다.
- 적용한 대장 교훈 번호: **F-129, S-20**.
- 못 한 것 / 막힌 것: 없음. `STATE.md`·`WORKLOG.md`·`AGENTS.md`·`dashboard.py`와 다른 레인 변경은 건드리지 않았고 commit/push·파일 삭제·의존성 변경·8010 재기동·production refresh를 하지 않았다.

## 0100 에서 넘어온 교정 (반드시 지킬 것)

- **8011 은 반드시 `GETDAYTRENDS_SCHEDULER_ENABLED=0` 으로 띄운다.** 0100 검증 때 8011 의
  lifespan 이 수집 스케줄러를 자동 기동해 Reddit·Google Trends·getdaytrends.com 으로
  실제 외부 요청을 냈고, 그 행을 8010 것과 사후에 갈라내지 못했다. 검증이 데이터를 만들면 안 된다.
- **대조군은 반드시 저장소 밖 구조 사본**(`automation/getdaytrends` + `packages/shared` +
  `pyproject.toml`)이다. 단일 디렉터리 사본은 `No module named 'shared'` 로 13건이 collection
  실패한다. 구조 사본 자체가 `test_runtime_identity` 계열 **5건**이 원래 실패하니, 사본에서는
  «사본 자신의 변경 전 실패 목록»과 비교하라.
- **기대하는 답을 지어내지 말고 실측값만 적어라.** 막히면 우회하지 말고 반환에 적어 되돌려라 —
  0100 v1 에서 실행자가 되돌린 판단이 옳았고, 그 덕에 헤더가 잘못된 전제를 고칠 수 있었다.
- **현재 기준선: `1234 passed · 7 skipped`, 8010 은 PID 26062, HEAD 는 `52c8a1e6`.**

- 착수: 2026-09-01 09:43:45 KST · Codex 실행 · 정본 브리프·STATE·최근 WORKLOG·열린 핸드오프·git 상태를 확인하고 0101 레인 착수.
- 기준선 실측(2026-09-01 09:46 KST): `.venv/bin/python -m pytest automation/getdaytrends/tests -q` → **1234 passed · 7 skipped · 25.38s**. 수정 전 기준선 통과.
- 구조 사본 준비·대조(2026-09-01 09:49 KST): `/tmp/0101-refresh-control.JFr61r`에 `git archive HEAD`로 `automation/getdaytrends`·`packages/shared`·`pyproject.toml`을 함께 복사했다. 사본 manifest **420파일**, 사본 기준 누락 **0**, `pyproject.toml` 존재 **True**(automation 278·shared 142).
- 구조 사본 기준선(2026-09-01 09:50 KST): 사본에서 동일 pytest를 실행해 **5 failed · 1229 passed · 7 skipped · 1 warning · 21.41s**. 실패 5건 모두 `test_runtime_identity` 계열(사본 경로/사본에 git 없음)이며, 이 기준선은 회귀 판정에서 제외한다.
- 결함 대조군 1차(2026-09-01 09:51 KST): 별도 구조 사본 `/tmp/0101-refresh-defect.QA3APH`에서 fast-viral의 마지막 `displayed = sort_by_kernel(displayed)`만 의도적으로 제거했다. 기존 `test_fast_viral_collector.py`는 **58 passed · 0 failed · 0.30s**로 통과했다. 즉 이 순서를 보호하는 회귀 테스트가 아직 없음을 먼저 확인했다. 수정 전에 회귀 테스트를 추가한다.
- 회귀 테스트 추가·정상 확인(2026-09-01 09:53 KST): `test_refresh_resorts_after_og_second_pass_changes_kernel_axis`를 `test_fast_viral_collector.py`에 추가하고 정본에서 **1 passed · 0 failed · 0.26s**. 검증 대상은 2건(`high`, `weak`)이며 OG 후 `weak`가 앞서는 결과다.
- 외부 4분면 대조(2026-09-01 09:54 KST): 정상 사본 `/tmp/0101-refresh-control.JFr61r`는 대상 2건 **1 passed**; 재정렬 제거 사본 `/tmp/0101-refresh-defect.QA3APH`는 대상 2건 **1 failed**(예상 FAIL, 실제 순서 `high, weak`); 과잉 방어 사본 `/tmp/0101-refresh-overdefense.SGUOeL`는 대상 2건을 전부 거부해 **1 failed**(예상 FAIL); 대상 소실 정상 대조(`test_collector_does_not_call_or_surface_foreign_community_sources`)는 대상 **0건 · 1 passed**. 결함·과잉 방어·0대상 모두 기존 구조 사본 밖에서 확인했다.
- 추출 후 전용 테스트(2026-09-01 10:15:05 KST): x-radar **31 passed**, fast-viral **58 passed**. 회귀 검증은 기존 테스트 안에 통합해 전체 테스트 수를 늘리지 않았고 대상 수 **2건**을 단정한다.
- 구조·복잡도 실측(2026-09-01 10:15:05 KST): `uvx --from radon==6.0.1 radon cc -s` 기준 x-radar `refresh` **119줄·A(4)**, fast-viral `refresh` **60줄·A(3)**. AST 줄수 기준 추출 함수는 x `_collect_radar_sources` 72, `_normalize_radar_sources` 149, `_enrich_radar_candidates` 113, `_build_radar_items` 199, `_assemble_radar_lanes` 61, `_finalize_radar_snapshot` 188; fast `_collect_fast_viral_sources` 165, `_qualify_fast_viral_items` 162, `_select_fast_viral_diverse_items` 142, `_cut_fast_viral_items` 26, `_apply_fast_viral_og_and_resort` 15, `_assemble_fast_viral_snapshot` 81. 모두 200줄 이하.
- 전체 게이트 1 중간 실측(2026-09-01 10:15:05 KST): `.venv/bin/python -m pytest automation/getdaytrends/tests -q` → **1234 passed · 7 skipped · 19.51s**.
- 최종 구조 사본 기준선(2026-09-01 10:22:18 KST): `/tmp/0101-refresh-final-clean.OrIxN2`는 `automation/getdaytrends`·`packages/shared`·`pyproject.toml` 구조로 **420파일**. 사본 전체 테스트는 **5 failed · 1229 passed · 7 skipped · 1 warning · 20.31s**이며 실패 5건은 모두 `test_runtime_identity` 계열 기준선이다.
- 최종 구조 사본 4분면(2026-09-01 10:22:18 KST): 정상 회귀 대상 **2건 · 1 passed · 57 deselected · 0.23s**; 마지막 OG 후 정렬 1줄 제거 결함은 **1 failed · 57 deselected · rc=1**(실제 `['high', 'weak']`); 게이트를 전부 거부하는 과잉방어는 **1 failed · 57 deselected · rc=1**(대상 2건이 OG 단계에서 소실); 국내 외부소스 대상소실은 **0건 · 1 passed · 57 deselected · 0.23s**.
- API 게이트 3 표준 초기 응답 실측(2026-09-01 10:22 KST): scheduler-off 8011을 일반 기동해 GET만 했을 때 초기 snapshot은 아직 수집 전이라 8010 대비 x **119→55 key-path, missing 64**, fast **80→25, missing 55**였다. 이는 refresh를 금지한 초기 메모리 상태 차이로 확인했고, refresh/POST나 외부 수집으로 채우지 않았다.
- API 게이트 3 최종 실측(2026-09-01 10:23:32 KST): `GETDAYTRENDS_SCHEDULER_ENABLED=0` 8011 별도 프로세스에서 8010의 두 응답을 **GET으로만 읽어 8011 메모리 snapshot에 주입**한 뒤 두 API를 GET했다. 배열 원소까지 순회한 전체 중첩 key-path가 x **360→360, missing 0, added 0**, fast **170→170, missing 0, added 0**이었다. 8011 scheduler 상태는 **enabled=false · running=false**; 8010은 PID **26062**를 유지했다.
- 최종 게이트 1 재확인(2026-09-01 10:24:51 KST): `.venv/bin/python -m pytest automation/getdaytrends/tests -q` → **1234 passed · 7 skipped · rc=0 · 20.10s**. 8011 listener **0**, 8010 PID **26062** 유지.
- 적용한 교훈: **F-129, S-20**

## 헤더 검수 (2026-09-01)

- 테스트 **1234 passed · 7 skipped** — 기준선 동일.
- `refresh()` **643줄 → 119줄**(x-radar), **516줄 → 60줄**(fast-viral).
  저장소 전체로 200줄 초과 함수 **5 → 3**, 복잡도 40 초과 **5 → 3**, 최장 함수 **643 → 436줄**
  (남은 436줄은 범위 밖 `notion_builder._build_notion_body`).
  100줄 초과가 37 → 45 로 는 것은 분해의 정상 결과다 — 큰 덩어리 하나가 중간 크기 여럿이 된 것이다.
- **가장 값진 것은 코드가 아니라 대조군이 찾은 구멍이다.** 실행자가 OG 뒤 `sort_by_kernel`
  재정렬을 일부러 제거했는데 기존 fast-viral 테스트 58건이 **전부 통과**했다. 그 순서를 지키는
  회귀 테스트가 없었다는 뜻이고, 이 저장소가 같은 모양의 버그를 이미 세 번 고쳤던 자리다.
  지시대로 **고치기 전에 회귀를 먼저 추가**했고 4분면(정상 1 passed / 결함 1 failed /
  과잉방어 1 failed / 대상소실 1 passed)으로 검사가 살아 있음을 증명했다.
- 실행자가 헤더의 복잡도 기재값(114·77)이 `radon` 으로 재현되지 않는다(166·119)고 정정한 것도
  맞다 — 헤더의 AST 근사가 radon 보다 거칠다. 방향과 배율은 같다.
