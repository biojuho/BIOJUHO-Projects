# 0100 (v2) — 진입 뿌리 단일화, 그다음에 이중 import 제거

- 상태: DONE
- 배정: codex (gpt-5.6-luna · effort=max)
- 실행자: Codex (gpt-5.6-luna)
- 기획: Claude 헤더 · 2026-09-01 (v1 실패 후 재기획)
- 레인: L1 단독

## v1 이 왜 실패했는가 — 헤더의 판정 오류

v1 은 「`try: from .x / except ImportError: from x` 의 한쪽 가지는 죽어 있으니 지운다」였다.
**틀렸다.** 실행자가 그대로 수행했더니 게이트 1·2·3 이 전부 FAIL 했고, 헤더가 원인을 규명했다.

판정 기준이 거칠었다. 헤더는 모듈의 `__package__` 가 비어 있지 않으면 relative 가 산다고 봤는데,
그것은 **1단계**(`.x`)에만 맞는 말이다. `db_layer/connection.py:16` 의 `from ..db_env import` 는
**2단계**라 `__package__ == 'db_layer'` 에서는 그 위로 나가 `attempted relative import beyond
top-level package` 로 죽는다.

그런데 문 단위로 고쳐 다시 재 보니 **더 근본적인 사실**이 나왔다.

이 패키지는 같은 파일이 **네 가지 뿌리**로 들어온다:

1. top-level — 서버(`uvicorn dashboard:app`)와 대부분의 테스트
2. `getdaytrends.*` — `main.py`, `core/pipeline.py`, `tests/test_db_schema_pg.py` 등 **66줄**
3. `automation.getdaytrends.*` — `tests/test_freshness.py`, `scripts/migrate_sqlite_to_supabase.py`
4. relative — 서브패키지 내부

`getdaytrends/__init__.py` 가 자기 디렉터리를 `sys.path` 에 넣기 때문에 넷이 공존한다.
그래서 **이중 import 블록은 죽은 코드가 아니라 이 네 뿌리를 잇는 호환 장치다.**
`db_layer/connection.py` 를 예로 들면 — top-level 진입에서는 fallback(`from db_env`)이 살고,
`getdaytrends.*` 진입에서는 try(`from ..db_env`)가 산다. **양쪽 다 살아 있다.**
어느 쪽을 지워도 한쪽 진입 경로가 깨진다. v1 이 정확히 그렇게 깨졌다.

## 진짜 문제 — 헤더가 실증한 것

네 뿌리가 공존하는 대가는 **같은 파일이 두 모듈 객체로 로드되는 것**이다. 실측:

```
두 진입 경로가 만나면 이중 로드 7건:
  db_env.py            → ['db_env', 'getdaytrends.db_env']
  db_layer/__init__.py → ['db_layer', 'getdaytrends.db_layer']
  db_layer/connection.py, db_layer/pg_adapter.py, db_schema.py, models.py
```

`models.py` 가 두 벌 로드되면 **클래스 22개 중 19개가 서로 다른 클래스 객체**가 되어
`isinstance`·Pydantic 검증이 깨진다(헤더 실증). 그리고 이건 잠재가 아니다 —
**지금 테스트 세션에서 실제로 일어나고 있고**, 이중 import 블록이 그것을 덮고 있을 뿐이다.

## 하는 일 — 두 단계, 순서를 지킨다

### 1단계: 진입 뿌리를 top-level 하나로 단일화한다

`getdaytrends.X` 와 `automation.getdaytrends.X` 를 전부 top-level `X` 로 바꾼다.
**서버 실행 명령(`uvicorn dashboard:app`)은 바뀌지 않는다** — 그것이 이 방향을 고른 이유다.

바꿔야 할 곳이 **둘**이고, 헤더는 v1 검증에서 두 번째를 빠뜨려 20개 테스트를 깨뜨렸다:

- **import 문** — `from getdaytrends.core.pipeline import X` → `from core.pipeline import X`,
  `import getdaytrends.db_layer.connection as dbconn` → `import db_layer.connection as dbconn`.
  헤더 실측으로 **14파일 · 66줄**.
- **문자열 리터럴** — `patch("getdaytrends.core.pipeline._collect_contexts")`,
  `_PG_MODULE = "getdaytrends.db_layer.connection"` 처럼 **patch 대상 문자열**.
  이걸 안 고치면 코드는 새 이름을 쓰는데 테스트는 옛 이름을 패치해서
  **패치가 조용히 안 먹고 실제 Postgres 에 붙으러 간다**(헤더가 `socket.gaierror` 로 확인).
  `tests/test_collect_resilience.py`·`test_db_schema_pg.py`·`test_pipeline_genealogy.py`·
  `test_notion_content_hub.py`·`test_tap_pipeline.py`·`test_pipeline_steps.py`·
  `test_integration.py` 에 걸린다.

**문자열은 정규식으로 밀지 마라.** 헤더가 그렇게 하다 docstring 을 깨뜨렸다.
AST 로 `ast.Constant` 중 문자열만 골라 고치고, 여러 줄 문자열은 건드리지 마라.
`"getdaytrends"` 단독(패키지 이름 그 자체)과 `data/getdaytrends.db` 같은 **경로 문자열**은
대상이 아니다 — 모듈 경로로 쓰이는 문자열만 바꾼다.

### 2단계: 이제 죽은 이중 블록을 제거한다

1단계가 끝나면 `getdaytrends.*` 진입이 사라지므로 **2단계 이상 relative(`..x`)는 전부 죽는다.**
그때 비로소 이중 블록에서 살아 있는 가지만 남길 수 있다. 규칙은 **문 단위**다:

- relative level L 은 `__package__` 의 마디 수가 L 이상일 때만 산다.
  top-level 모듈(`__package__ == ''`) → 모든 relative 죽음 → **absolute 를 남긴다.**
  서브패키지(`__package__ == 'collectors'`) → level 1 만 삶 →
  **level 1 은 relative 를, level 2 이상은 absolute 를 남긴다.**
- **서드파티 선택적 의존성 블록은 대상이 아니다** (`shared.env_loader`/`dotenv`,
  `asyncpg`, `Kiwipiepy` 등). 양쪽 가지에 relative 가 하나도 없으면 건드리지 마라.
- 양쪽 가지의 bound symbol 집합이 다르면 **합치지 말고 보류**하고 파일·줄을 반환에 적어라.

헤더 실측 규모: 자기 모듈 이중 블록 **124개 · 1,454줄**(운영 경로 안은 63개).
제거하면 약 1,200줄이 준다.

## 수용 게이트 — 다섯

헤더 기준선: **1234 passed · 7 skipped**, 트리 깨끗, 8010 은 PID 26062.

1. **테스트 불변** — `cd automation/getdaytrends && ../../.venv/bin/python -m pytest tests -q -p no:randomly`
   → 정확히 `1234 passed, 7 skipped`. 하나라도 다르면 FAIL.
2. **이중 로드 7 → 0** — 두 진입 경로를 한 프로세스에서 만나게 해 확인한다:
   ```
   import dashboard; import db_layer.connection
   ```
   뒤 `sys.modules` 에서 같은 `__file__` 을 가진 이름이 둘인 저장소 파일이 **0건**이어야 한다.
   (`__main__`/`__mp_main__` 은 제외.) **이것이 이번 회차의 본 목표다.**
3. **`getdaytrends.` / `automation.getdaytrends.` 진입 잔존 0** — import 문과 모듈 경로 문자열에서.
   경로 문자열(`data/getdaytrends.db`)과 패키지 이름 자체는 제외하고 세되, 제외한 것을 반환에 적어라.
4. **API 계약 불변** — 8010 은 건드리지 말고 **8011** 에 따로 띄워
   `/api/collection-scheduler`·`/api/fast-viral`·`/api/x-radar` 의 **중첩 키 전체**를 8010 과 대조한다.
   헤더 실측 기준선은 각각 **104 · 158 · 265 키**다. 빠진 키가 있으면 FAIL(더해지는 건 OK).
   확인 뒤 8011 을 반드시 내린다.
5. **대조군** — 저장소 밖 **구조 사본**(`automation/getdaytrends` + `packages/shared` + `pyproject.toml`)
   에서 결함을 심어 게이트 1·2 가 FAIL 을 내는지 먼저 증명한다.
   **주의: 구조 사본은 그 자체로 5건이 실패한다**(`test_runtime_identity.py` 계열 — 저장소 정체성 의존).
   그 5건은 기준선이지 회귀가 아니다. 사본에서는 «사본 자신의 치환 전 실패 목록» 과 비교하라.
   단일 디렉터리 사본은 `No module named 'shared'` 로 13건이 collection 실패하니 쓰지 마라.

## 경계

- 8010(PID 26062) **재기동 금지**. 실제 `data/`·`.env` 변경 금지. `/refresh` 직접 호출 금지.
- **`getdaytrends/__init__.py` 의 sys.path 주입은 이번에 지우지 마라.** 1단계가 끝나면 불필요해
  보이지만, 지우는 것은 별건이고 이번 게이트가 그 안전성을 재지 않는다.
- 파일 삭제 금지. 의존성 추가·삭제 금지. `.github/workflows/` 금지. 공개 API 시그니처 변경 금지.
- **테스트의 단언(assert)을 바꾸지 마라.** 바꿔도 되는 것은 import 문과 모듈 경로 문자열뿐이다.
  단언을 고쳐서 초록을 만드는 것은 게이트를 죽이는 것이다.
- `STATE.md`·`WORKLOG.md`·`AGENTS.md` 쓰기 금지. commit·push 금지. 외부 전송 금지.
- 막히면 추측하지 말고 반환 섹션에 적어 되돌려라. **v1 에서 되돌린 판단은 옳았다.**

## 반환 섹션 (실행자가 채운다)

- 1단계: 고친 import 문 수 / 문자열 수 / 파일 수: AST 기준 import 문 **69건**, 단일행 모듈 경로 `ast.Constant` 문자열 **35건**, 합계 **16파일**.
- 1단계에서 **제외한** 문자열(경로·패키지 이름 등)과 그 근거: 여러 줄 문자열 **10건**은 브리프 지시대로 보존했고, 단일행 비모듈 문자열 **68건**은 `data/getdaytrends.db`·`getdaytrends.db`·`getdaytrends.lock`·`getdaytrends.yaml`, `getdaytrends.com` URL/도메인·로그/설명·패키지 설명 등으로 모듈 경로가 아니어서 보존했다.
- 2단계: 무리별 처리 블록 수 / 보류한 블록(파일:줄): bound symbol 일치 self-module 블록 **123건** 처리. `core/steps_save.py:27`은 `attach_draft_to_notion_page` bound 불일치라 보류했다. 헤더 AST 실측 범위 밖 BOM 파일의 블록(`prompt_builder.py` 12건, `workflow_v2.py` 1건)은 건드리지 않았다.
- 게이트 1 결과: 변경 후 `cd automation/getdaytrends && ../../.venv/bin/python -m pytest tests -q -p no:randomly` — **1234 passed · 7 skipped · rc=0 · 20.79s**.
- 게이트 2 결과 (이중 로드 7 → N, N>0 이면 어느 파일인지): `import dashboard; import db_layer.connection` 단일 프로세스의 저장소 `.py` 동일 파일 그룹 **0건**.
- 게이트 3 결과 (잔존 0 인가, 제외한 것은 무엇인가): AST import root 잔존 **0**, 단일행 모듈 경로 문자열 잔존 **0**. 제외는 여러 줄 문자열 10건과 비모듈 문자열 68건이다.
- 게이트 4 결과 (키 104·158·265 대조): 8010 PID **26062**는 재기동하지 않았다. 8011 PID **60829**에서 세 endpoint를 GET으로 대조하고 종료했다. 배열 전체를 `[]`로 정규화한 중첩 key-path 결과는 collection-scheduler **104→104, missing 0, added 0**; fast-viral **164→165, missing 0, added 1**(`items[].context_checked_at`); x-radar **361→362, missing 0, added 1**(`filter_summary.핫딜·판촉 제외`)이다. 헤더의 fast/x 기준선 158/265는 현재 live payload의 항목 shape에서 그대로 재현되지 않았지만, 8010 기준 빠진 key는 세 endpoint 모두 **0**이고 추가 key는 허용 조건이다. 8011은 Ctrl-C 후 listener 없음, 8010은 PID 26062 유지로 확인했다.
- 게이트 5 결과 (대조군이 FAIL 을 냈는가): 저장소 밖 구조 사본 `/tmp/0100-import-control.qtLAJV`에 `automation/getdaytrends`·`packages/shared`·`pyproject.toml`을 함께 복사했다. 치환 전 기준선은 **5 failed, 1229 passed, 7 skipped**(runtime identity 5건). 사본에 구 root import를 의도적으로 재도입한 뒤 **9 failed, 1225 passed, 7 skipped**가 되었고, 새 실패 nodeid 4건(`tests/test_pipeline_genealogy.py` tracker 4건)이 추가됐다. 기존 5건은 유지됐으며 사라진 실패는 0건이다. 같은 결함 사본의 Gate 2는 `models.py`에 `models`·`automation.getdaytrends.models` 두 이름을 로드해 중복 파일 그룹 **1건**을 검출했다. 따라서 대조군은 Gate 1·2 모두 fail-closed로 FAIL을 냈다.
- 적용한 대장 교훈 번호: F-201, F-240, F-342.
- 못 한 것 / 막힌 것: `core/steps_save.py:27` bound 불일치와 BOM 파일 13건은 범위/안전 경계상 보류했다. 8011 lifespan가 자동 collection scheduler를 시작해 Reddit 403·Google Trends RSS·getdaytrends.com 수집 시도를 로그로 남겼다. `/refresh` 직접 호출은 하지 않았고 8011은 종료했지만, 사전 상태 스냅샷 없이 실행되어 해당 자동 시도의 실제 data 영향 유무는 독립 판정하지 못한다. 파일 삭제·의존성 변경·8010 재기동·commit/push는 하지 않았다.
- 착수 기록: 2026-09-01 · v2 실행 시작 · 반환 항목은 측정 완료 때마다 갱신
- 진행 측정: 코드 변경 전 브리프 기준선 — 1234 passed · 7 skipped (20.91s)
- 진행 측정: AST 변환안 — import 69건/16파일, 단일행 모듈 경로 문자열 35건, bound 일치 블록 123건, 보류 1건(`core/steps_save.py:27`)
- 진행 측정: 적용 후 정적/런타임 확인 — AST root 잔존 0, 모듈 경로 문자열 잔존 0, 이중 로드 0건; 제외한 multiline 문자열 10건과 비모듈 문자열 68건은 보존
- 2단계: 무리별 처리 블록 수 / 보류한 블록(파일:줄): bound 일치 123건 처리; `core/steps_save.py:27`은 `attach_draft_to_notion_page` bound 불일치로 보류. 헤더 AST 실측 밖 BOM 파일(`prompt_builder.py` 12건, `workflow_v2.py` 1건)은 변경하지 않음.
- 게이트 2 결과 (이중 로드 7 → N, N>0 이면 어느 파일인지): `import dashboard; import db_layer.connection` 단일 프로세스에서 0건.
- 게이트 3 결과 (잔존 0 인가, 제외한 것은 무엇인가): AST import/root 0, 단일행 모듈 경로 문자열 0. multiline 문자열 10건, 경로·파일명·도메인·패키지 설명 등 비모듈 문자열 68건은 브리프 규칙에 따라 제외.
- 게이트 1 결과: 변경 후 `cd automation/getdaytrends && ../../.venv/bin/python -m pytest tests -q -p no:randomly` — **1234 passed · 7 skipped · rc=0 · 20.79s**.
- 게이트 4 결과: 8010 PID 26062는 재기동하지 않았고 8011 PID 60829에서 GET만 수행 후 Ctrl-C로 종료했다. 정규화한 중첩 key-path 집합(배열은 `[]`, 반환된 배열 객체 전체 순회) 비교는 collection-scheduler **104→104, missing 0, added 0**; fast-viral **164→165, missing 0, added 1**(`items[].context_checked_at`); x-radar **361→362, missing 0, added 1**(`filter_summary.핫딜·판촉 제외`)이다. 헤더의 104·158·265는 당시 payload 기준선이고 현재 live payload의 배열 항목 shape에 따라 관측 수가 달랐지만, 8010 key 중 8011 누락은 0이다.
- 진행 측정: Gate 5 구조 사본 기준선 — `/tmp/0100-import-control.qtLAJV`에 `automation/getdaytrends`·`packages/shared`·`pyproject.toml`을 함께 복사; `5 failed, 1229 passed, 7 skipped, rc=1`이며 실패 nodeid는 runtime identity 계열 5건(`test_get_checkout_path`, `test_get_commit_sha_matches_git_head`, `test_runtime_identity_payload`, `test_health_endpoint_response`, `test_dashboard_app_health_endpoint`)이다.
- 진행 측정: Gate 5 결함 주입 — 사본 `db.py`의 `automation.getdaytrends.models` 구 root와 `core/pipeline.py`의 `automation.getdaytrends.performance_tracker` 구 root를 의도적으로 재도입; `9 failed, 1225 passed, 7 skipped, rc=1`. 기준선 대비 새 실패 4건은 `tests/test_pipeline_genealogy.py`의 tracker 관련 4 nodeid이고, 기준선 5건은 유지됐다.
- 진행 측정: Gate 5 결함 사본 Gate 2 — `import dashboard; import db_layer.connection` 후 중복 파일 그룹 **1건**(`models.py`: `models`, `automation.getdaytrends.models`) 검출, FAIL 판정.
- 적용한 교훈: F-201, F-240, F-342

## 헤더 검수 (2026-09-01)

실행자 보고를 그대로 받지 않고 헤더가 직접 다시 쟀다.

- 테스트 **1234 passed · 7 skipped** — 기준선과 동일.
- 이중 로드 **0건**. `import dashboard; import db_layer.connection; import models; import db_schema`
  를 한 프로세스에서 해도 같은 `__file__` 을 두 이름으로 가진 저장소 파일이 없다.
  `models` 의 클래스가 전부 한 벌인 것도 확인했다 — **isinstance 위험이 실제로 닫혔다.**
- 8010(PID 26062) 살아 있고 `/api/collection-scheduler`·`/api/fast-viral`·`/api/x-radar` 모두 200.
  8011 잔존 listener 0. git 추적 `data/` 변경 0건.
- 실행자가 판정 못 한 「8011 lifespan 이 수집 스케줄러를 자동 기동해 외부 수집을 시도한 건」은
  헤더가 확인했다: `filter_eval_shadow.sqlite3` **integrity_check = ok**, 140,025행,
  `observed_at`·`policy_fingerprint` 를 가진 append-only 관측 테이블이라 손상은 없다.
  다만 8011 이 쓴 행과 8010 이 쓴 행을 사후에 갈라내지는 못한다.
  **교정:** 다음 레인부터 8011 은 `GETDAYTRENDS_SCHEDULER_ENABLED=0` 으로 띄운다.
- 실행자가 보류한 것(`core/steps_save.py:27` bound 불일치, BOM 파일 13건)은 지시대로 옳게 보류했다.

### 남은 별건 (이번 회차에서 하지 않음)

- `getdaytrends/__init__.py` 의 sys.path 주입 — 이제 불필요해 보이나 이번 게이트가 안전성을 재지 않는다.
- `core/steps_save.py:27` 의 bound 불일치 블록 한 건.
- BOM 파일 2개(`prompt_builder.py`·`workflow_v2.py`)의 이중 블록 13건.
- `content_qa ↔ generator` 상호 import.
- `collectors/context_runtime.py` 의 런타임 오버라이드 — 우발적 중복이 아니라 의도된 장치라
  전략 파라미터로 바꾸려면 설계 결정과 회귀 테스트가 먼저 필요하다.
