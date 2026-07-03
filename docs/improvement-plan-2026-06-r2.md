# JooPark Workspace 개선 플랜 2차 (2026-06-11)

- 작성: Claude 기획
- 관계: 1차 플랜(`improvement-plan-2026-06.md`)의 후속. 1차의 Phase 0·2·3·4는 핸드오프 0002~0006으로 완료됐고, 이 문서는 **남은 차단(런치)과 다음 라운드(백로그·구조)**를 다룬다. 1차 문서는 기록으로 보존한다.
- 점검 방식: 4영역(핸드오프 상태 / 플랜 이행 / 제품 격차 / 배포 상태) 병렬 감사 + 누락 교차검증 + 핵심 주장 직접 재검증.

## 한 줄 결론

**1차 플랜의 제품·품질·지식 작업은 끝났다. 남은 것은 단 하나의 차단 — 미커밋 139개를 논리 단위로 커밋하고 올바른 브랜치로 푸시하는 것 — 과, 그 차단을 우회하며 계속 도는 마이크로 리팩터 루프를 멈추는 것이다.**

## 감사로 검증된, 설계를 바꾸는 사실 4가지

1. **푸시 대상은 main이 아니다.** 로컬 main과 리모트 main(`biojuho/BIOJUHO-Projects`)은 공통 조상이 없다(orphan 히스토리). 추적 브랜치는 `biojuho-projects/codex/joopark-workspace-release` [ahead 2, fast-forward 가능]이고, Pages 워크플로의 push/dispatch ref도 이 브랜치다. **handoff 0001의 `git push biojuho-projects main` 명령은 오류**이며 무효로 선언한다. 올바른 명령:
   ```
   git push biojuho-projects main:codex/joopark-workspace-release
   ```
   (리모트 main 통합은 `data/main-bridge-plan.json`의 서브디렉터리 브리지 전략으로 별도 트랙 — 런치에 불필요.)
2. **워킹트리의 `.gitignore` 9-10행이 지뢰다.** `data/github-project-discovery.json/.md` 2줄이 추가돼 있는데, 이 파일은 `sw.js:74`(APP_SHELL_ASSETS — `cache.addAll`은 하나라도 404면 SW 설치 전체 실패)와 `scripts/verify-release.mjs:84` 필수 목록에 들어 있다. 이대로 커밋하면 첫 배포가 깨진다. → **2줄을 제거하고 파일 2개를 추적에 추가**한다.
3. **메타 아티팩트 추적 해제(`git rm --cached`)는 런치 뒤로 미룬다.** 후보 다수(data/*.json, autoresearch-results/ 일부)가 sw.js 프리캐시 9개·System Status 런타임 fetch 7개·package-release 패키징에 의존한다. 런치 전에 빼면 배포가 깨지고, 배포 baseline이 생긴 뒤에는 잘못된 해제가 verify-release 실패로 즉시 드러난다. 추적 해제는 정책 표(`docs/app-architecture.md`)·`.gitignore`·`sw.js`·`package-release.mjs`·`verify-release.mjs` 5자를 한 번에 정합 변경하는 별도 핸드오프(0023)로 한다.
4. **루프홀: 실행자 자가 발급.** 핸드오프 0013~0018의 기획자 필드가 "Codex 기획" — "OPEN 핸드오프 없으면 시작 금지" 가드레일을 실행자가 스스로 핸드오프를 발급해 우회했다(refactor loop 167회+, 제품 작업 0건). 이 문서 작성 시점에 0015~0017은 DONE, **0018은 CLAIMED 진행 중**이라 번호 0015~0018은 이미 소모됐다. AGENTS.md에 **발급 권한 조항**을 신설해 봉쇄한다.

## 트랙/페이즈 구조

```
Phase L 런치 완결 ──[U1 푸시 승인]──[U2 디스패치 승인]──→ 배포 v1   ← 최우선
   L0 루프 동결 + 가드레일 개정 (이 문서와 함께 완료)
   L1 커밋 트레인: 139개 → ≤5 (핸드오프 0019, 푸시 없음)
   L2 PWA 새 버전 알림 UI (핸드오프 0020 — 첫 배포 전 필수 지정 항목)
   L3 푸시 + 게이트 재검증 (핸드오프 0021) ← U1
   L4 디스패치 + 배포 URL 검증 (핸드오프 0022) ← U2
Phase M 메타 정리 — 배포 baseline 확보 후
   M1 아티팩트 보존 정책 개정 + 추적 해제 (0023)
   M2 지연 로드 활성화 — review 그룹 먼저 (0024), release/operations 후속 (0025)
   M3 원격 codex/* 브랜치 42개 정리 (0030) ← U3 (삭제 목록 승인)
Phase P 제품 백로그 — M1 이후 M2와 병행 가능
   P1 .ics/.csv 가져오기 (0026)
   P2 통합 플로우 자동화 테스트: create→edit→delete→undo·오프라인·복구 (0027)
   P3 v4 스키마 마이그레이션 템플릿 (0028)
Phase S 구조 — 제품 큐가 빌 때만, 기획자 발급 大단위만
   S1~ app.js render* 추출, 건당 ≥800줄 (0029+, renderStats 1순위)
```

**순서 근거:**
- **L이 무조건 먼저**: 미커밋 139개가 모든 트랙의 리스크 증폭기다. 어떤 작업이든 diff가 더 섞이고 게이트 증거 재검증 비용이 커진다. 커밋·푸시는 가장 싼 큰 성과다.
- **L2(PWA 알림)가 L3(푸시) 앞**: "첫 배포 전 필수"로 지정된 유일한 제품 항목. `pwa-runtime.js`에 controllerchange 리스너(112행)가 이미 있어 작업이 작고, 푸시 전에 넣어야 v1 배포에 포함된다.
- **M(추적 해제·지연 로드)이 런치 뒤**: 현재 게이트는 42개 동기 로드·현행 추적 기준으로 전부 통과 중이다. 알려진-정상 상태로 v1을 내보내고, 변경은 배포 URL 스모크라는 회귀 감지망이 생긴 뒤에 한다(product-direction에 review 지연 로드 게이트 실패 전력 기록 있음).
- **S가 마지막**: 마이크로 리팩터 167루프 재발 방지. 구조 작업은 "제품 큐 빈 상태 + 기획자 발급 + 측정 가능한 大단위(≥800줄)" 3중 조건으로만 연다.

## 승인 게이트 (외부 행위 = 사용자 명시 승인, 매번 별도로 묻는다)

| 게이트 | 내용 | 비고 |
|---|---|---|
| **U1** | `git push biojuho-projects main:codex/joopark-workspace-release` (런치 윈도우 동안 게이트 증거 재푸시 포함) | 부수효과 고지: 새 `joopark-ci.yml`이 이 브랜치 push에 트리거되어 원격 CI가 돈다(권한 contents:read, 10분 타임아웃 — 안전) |
| **U2** | `gh workflow run joopark-pages.yml --ref codex/joopark-workspace-release` 1회 (실제 게시) | run 실패 시 재디스패치는 원인 분석·기획자 보고 후 |
| **U3** | 원격 codex/* 브랜치 삭제 목록 | "gone 추적 + 병합 확인된 것"만 목록화해 승인 |

2026-06-11 사용자 결정: **커밋(로컬)까지만 선승인**. U1·U2·U3는 각 시점에 다시 묻는다.

## 핸드오프 분할표

번호는 0019부터 — 0015~0018은 실행자 자가 발급 리팩터 핸드오프가 이미 소모했다(기록으로 보존, 발급 권한 규칙은 이후부터 적용). 0006 번호 중복도 같은 원칙으로 보존. 0003/0005의 "DONE인데 커밋 미실행" 모순은 0019가 커밋을 실행함으로써 해소.

| # | 범위 | 수용 게이트 | 금지 |
|---|---|---|---|
| **0019 런치 커밋 트레인** | 전처리(.gitignore 2줄 제거+discovery 추적, npm test baseline) → 논리 커밋 ①~⑨ (상세는 핸드오프 본문). 0014~0018 자가 발급 리팩터 결과물 흡수. | npm test 전후 pass · `git status --porcelain ≤ 5줄` · `git diff --check` | push 금지 · 기능 수정 금지 · 추적 해제 금지 · 트레인 중 다른 핸드오프 착수 금지 |
| **0020 PWA 업데이트 알림** | pwa-runtime.js controllerchange 무음 갱신 → "새 버전 적용" 토스트 UI. 완료 즉시 커밋 1개. 0019 DONE 후 착수. | smoke:cockpit · npm test · SW 업데이트 수동 시나리오 기록 | sw.js 캐시 전략 변경 금지 · index.html 스크립트 순서 변경 금지 |
| **0021 푸시+게이트 재검증** [U1] | 명시 refspec 푸시 → `check-remote-workflow-files --write` → `plan-publish-dispatch --live --write` → `refresh:launch-readiness` → 증거 커밋+재푸시 | `remoteMatchesTemplate=true`(pages·drift-watch) · `allDispatchReady=true` · 원격 CI green | `--force` 금지 · 리모트 main/브랜치 삭제 금지 · dispatch 금지 |
| **0022 디스패치+배포 검증** [U2] | `gh workflow run` → run 완주 → attestation/publish evidence 캡처 → 배포 URL 라우트 스모크 → 증거 커밋+푸시 | run success · Pages URL 200 · 데스크톱/모바일 16라우트 패리티 · 배포 URL SW 설치 성공 | 재디스패치는 보고 후 |
| **0023 보존 정책 개정** | 정책 표 개정 + .gitignore + `git rm --cached`(1차 후보: `joopark-product-loop.md` 833K — 런타임 비참조 확인됨) + sw.js/package-release/verify-release 동시 정합 + archive/ 처분 | npm test · package-release 성공 · verify-release pass · check:docs | 런타임 fetch되는 data/*.json 추적 해제 금지 |
| **0024 지연 로드 1단계** | index.html에서 review-*.js 13개 동기 로드 제거, 라우트 진입 시 ops-runtime-loader GROUPS.review 트리거 연결. sw.js 프리캐시 유지. | smoke:cockpit · 라우트 패리티 · Ops runtime diagnostics on-demand 기록 · measure:perf 수치 | release/operations 그룹 동시 변경 금지(0025로) |
| **0026 .ics/.csv 가져오기** | 파서를 순수 헬퍼로 분리(+단위 테스트) + backup-import-ui 진입점 + 캘린더/할일 매핑. 기존 2MB 가드 재사용. | test:unit 신규 케이스 · npm test · 깨진 파일 거부 케이스 | 외부 네트워크 fetch 금지(파일 입력만) |
| **0027 통합 플로우 테스트** | smoke-delete-undo 확장: create→edit→delete→undo 저니 + 오프라인(SW) + 스토리지 복구. npm test 체인 편입. | 신규 스모크 단독 pass + 체인 내 pass | 앱 동작 변경 금지(테스트만) |
| **0028 v4 마이그레이션 템플릿** | v2→v3 패턴 일반화 스캐폴드 + 단위 테스트 + docs/knowledge 1편 | test:unit · 더미 v4 필드 왕복 테스트 | 실제 스키마 변경 금지 |
| **0029+ 구조 추출** | renderStats → stats-view.js 이관(1순위) → renderSettings → renderKanban → renderTodos/Notes | 건당 app.js ≥800줄 감소 · check:structure · 동작 보존 스모크 · npm test | 한 번에 1개 render*만 · 마이크로 단위 발급 금지 |
| **0030 원격 브랜치 정리** [U3] | codex/* 42개 중 병합 확인분 목록화 → 사용자 승인 → 삭제 | 삭제 목록=승인 목록 일치 | 승인 없는 삭제 금지 |

## 운영 규칙 개정 (AGENTS.md·handoffs/README.md에 반영됨)

1. **발급 권한**: 핸드오프는 기획자(Claude Code) 또는 사용자만 발급한다. `기획자:` 필드가 실행자인 핸드오프는 무효이며, 실행자는 OPEN이어도 잡지 않는다.
2. **refactor 모라토리엄**: Phase L~P 완료까지 refactor류 핸드오프 발급 0건.
3. **구조 작업 최소 단위**: 구조 핸드오프는 "app.js ≥800줄 감소"처럼 측정 가능한 大단위만. helper 추출류 마이크로 단위는 발급하지 않는다.
4. **OPEN 큐 상한**: 동시 OPEN 핸드오프 ≤ 2. 직렬 의존이 있으면 후행 핸드오프 첫머리에 선행 조건을 명시한다(선행 DONE 전 착수 금지).
5. **제품 가치 문장 의무**: 반환 섹션에 "사용자 가시 변화 한 줄" 필수. "없음"이면 기존 "이틀 연속 0건 자동 중단" 카운터가 증가한다.

## 트랙별 종료 기준

- **Phase L**: ① `git status --porcelain ≤ 5줄` ② remoteWorkflowFilesReady=true + allDispatchReady=true ③ Pages run success ④ 배포 URL 데스크톱/모바일 16라우트 패리티 + SW 설치 성공 + attestation 캡처 ⑤ npm test 그린.
- **Phase M**: ① 정책 표·.gitignore·sw.js·package-release·verify-release 5자 일치 ② 추적 해제 후 재배포 1회 성공 ③ 초기 동기 스크립트 42 → 29 이하 + measure:perf 수치 기록.
- **Phase P**: 신규 기능 각각 npm test 체인에 자동 테스트 편입 + WORKLOG에 사용자 가시 변화 기록.
- **Phase S**: app.js 10,610 → 1차 목표 ~8,000줄, check:structure 경고 0, 라우트 패리티 유지.

## 리스크와 완화

| 리스크 | 영향 | 완화 |
|---|---|---|
| `push main` 오용 | 리모트 모노레포 main 충돌·혼란 | 0021에 명시 refspec 명문화 + `--force` 금지 + 0001 명령 무효 선언 |
| discovery 2줄 커밋 | 첫 배포 verify-release 실패 / SW 설치 전면 실패 | 0019 전처리에서 2줄 제거·파일 추적 |
| 트레인 중 자가 발급 루프 재오염 | 논리 커밋 불가, 차단 재연 | 발급 권한 조항을 핸드오프 발급 전에 개정 + "트레인 중 착수 금지" 명시 + CLAIMED 중인 0018의 반환 대기/회수 절차 |
| 런치 전 추적 해제 | 배포 산출물 결손 | 추적 해제를 Phase M(0023)으로 후치 |
| joopark-ci.yml 푸시로 예고 없는 원격 CI | 사용자 인지 없는 자동화 | U1 승인 요청문에 부수효과 고지 |
| 지연 로드 회귀(게이트 실패 전력) | review 라우트 깨짐 | 그룹별 단계 적용 + 라우트 패리티 게이트 + 로더 진단 패널 관측 |
| npm test 체인 길이로 트레인 지연 | 트레인 중 새 변경 유입 | 전체 test는 시작·종료 2회만, 커밋 사이는 lint+check:structure |
| 원격 브랜치 삭제 실수 | 복구 곤란 | U3에서 병합 확인분만 목록 승인 |
