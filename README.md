# JooPark Workspace v3.0

일정·할 일·메모·습관·통계를 한 화면에서 관리하는 **개인 워크스페이스**에, 프로젝트(PM)·DB 카탈로그 관리까지 더한 정적 SPA입니다. 빌드/패키지 없이 정적 파일만으로 동작하며, 내가 만든 모든 데이터는 브라우저(localStorage)에 자동 저장됩니다.

## 실행

```bash
python3 -m http.server 5178
```

브라우저에서 `http://127.0.0.1:5178/` 를 엽니다. (저장 기능은 `http://`에서 동작합니다. `file://`로 직접 열면 저장이 제한될 수 있습니다.)

## 출시 전 검증

서버를 켠 상태에서 아래 명령을 실행하면 설치된 Chrome headless/CDP로 15개 화면 라우트, 콘솔 오류, 네트워크 4xx/5xx, GitHub/도입 후보 데이터 병합 카운트를 한 번에 확인합니다.

```bash
node scripts/smoke-chrome.mjs
```

성공 기준은 `status: "pass"`, `consoleIssues: []`, `networkIssues: []` 입니다.
실제 클릭/입력 워크플로우까지 확인하려면 아래 명령을 추가로 실행합니다. 독립 Chrome 프로필에서 일정·할 일·메모·습관·프로젝트·이슈·간트·팀·DB 인스턴스·테이블·쿼리·마이그레이션·설정·JSON 백업 내보내기/가져오기/전체 초기화·명령 팔레트 흐름을 생성/토글/저장/검증합니다.

```bash
node scripts/smoke-interactions.mjs
```

좁은 화면 레이아웃 회귀는 모바일 스모크로 확인합니다. 500px 폭 headless Chrome에서 15개 화면을 열고 horizontal overflow, 기본 텍스트, 콘솔/네트워크 문제를 검사합니다.

```bash
node scripts/smoke-mobile.mjs
```

## 출시 패키지 생성

정적 호스팅에 올릴 파일만 `dist/release/`로 복사하고, 파일별 SHA-256 manifest와 실행 안내를 생성합니다.

```bash
node scripts/package-release.mjs
cd dist/release
python3 -m http.server 5178
```

패키지 검증은 프로젝트 루트에서 `BASE_URL=http://127.0.0.1:5178 node scripts/smoke-chrome.mjs`로 실행합니다. 포트가 이미 사용 중이면 다른 포트로 서버를 띄우고 `BASE_URL`도 같은 포트로 바꿉니다.
체크섬 manifest까지 함께 검증하려면 먼저 `node scripts/verify-release.mjs`를 실행합니다.
전체 출시 게이트를 한 번에 돌리려면 프로젝트 루트에서 아래 명령을 실행합니다. 이 명령은 패키지 생성, manifest 검증, 임시 로컬 서버 기동, Chrome 라우트 스모크, 모바일 레이아웃 스모크, interaction 스모크, 서버 종료까지 자동으로 처리합니다.

```bash
node scripts/smoke-release.mjs
```

요구사항별 증거와 외부 publish blocker까지 한 번에 감사하려면 아래 명령을 실행합니다. `--run-gates`는 위 전체 출시 게이트까지 실제 실행해 감사 결과에 포함합니다.

```bash
node scripts/audit-release-readiness.mjs --run-gates
```

## 내 워크스페이스 (개인 관리)

| 메뉴 | 기능 |
| --- | --- |
| **일정** | 월간 캘린더 + 선택일 아젠다. 추가/수정/삭제, 분류(업무·회의·개인·마감·기타)별 색상, 종일/시간, 장소·메모. **반복 일정**(매일·매주·매월, 종료일·이 날짜 건너뛰기). |
| **할 일** | 빠른 추가(Enter), 우선순위·마감일, 완료 토글, 상태 필터(미완료/오늘/예정/완료/전체), 기한 지남·오늘 마감 강조. |
| **메모** | 색상 카드 그리드, 상단 고정(핀), 추가/수정/삭제. **Markdown 지원**(굵게·목록·링크·코드·인용 등, 출력은 XSS 소독). |
| **습관** | 습관 추가/편집/삭제, 이번 주 7일 체크 그리드, **현재/최장 연속(streak)**, 주간 목표·완료율. |
| **통계** | 최근 14일 할 일 추이, 완료율, 요일별 완료 분포, 일정 분류 분포, 습관 요약(순수 CSS/SVG 차트). |
| **대시보드 홈** | 인사말 + 오늘 일정·할 일, 다가오는 7일(반복 포함), 핵심 지표, 빠른 추가. |

- 모든 변경은 즉시 자동 저장됩니다.
- **알림 벨**은 기한 지난 할 일·오늘 일정/할 일·임박 마감·오늘 미완료 습관을 실데이터로 계산해 배지로 표시합니다.
- **라이트/다크 테마** — 우측 상단 ◑ 버튼, 설정 화면, 명령 팔레트에서 전환(저장됨).

## 팀·시스템 관리 (실제 CRUD)

| 섹션 | 기능 |
| --- | --- |
| **프로젝트(PM)** | 포트폴리오·Kanban·간트·팀을 **실제로 생성/편집/삭제**하고 저장합니다. Kanban은 드래그 또는 ◀▶로 컬럼 이동, 간트는 작업 CRUD, 팀은 멤버 CRUD(참조 자동 정리). |
| **데이터(DB 카탈로그)** | 인스턴스·데이터베이스·테이블·컬럼·저장 쿼리·마이그레이션을 직접 관리하는 문서화 도구. 모두 영속화됩니다. (백업 뷰는 샘플 시각화) |

## 명령 팔레트 · 단축키

- `⌘K` / `Ctrl K` — **명령 팔레트**: 일정·할 일·메모·습관·프로젝트·이슈 **퍼지(오타 허용)·관련도순 통합 검색** + 화면 이동·새 항목·내보내기·테마 전환 명령. ↑↓ 이동, Enter 실행.
- `/` — 현재 화면 내 검색창 포커스
- `n` — 현재 화면 맥락의 새 항목 추가
- `?` — 단축키 도움말
- `g` 다음 `h/c/t/m/i/s/p/k` — 화면 이동(홈/일정/할 일/메모/습관/통계/포트폴리오/Kanban)
- `Esc` — 팔레트/모달/패널 닫기 · 할 일 입력 후 `Enter` — 즉시 추가

## 데이터 저장 / 백업

| 항목 | 위치 |
| --- | --- |
| 일정·할 일·메모·습관·프로필·PM·DB·테마 | 브라우저 localStorage 키 `joopark.workspace.v3` (자동 저장, v2 자동 마이그레이션) |
| 백업 파일 | 설정에서 내보낸 `joopark-workspace-YYYY-MM-DD.json` (전체 데이터) |
| 프로젝트 카드 시드 | `data/repos.json` (GitHub 스냅샷) + `data/adoption-candidates.json` (도입 후보, 기존 저장소에도 1회 병합) |

처음 실행하면 사용법을 보여주는 샘플 데이터가 자동으로 채워집니다(자유롭게 삭제 가능). **설정 → 데이터 백업**에서 JSON 내보내기 / 가져오기 / 전체 초기화가 가능합니다.

## 구성

- `index.html` — 사이드바/메인/시트/모달/명령 팔레트 레이아웃, 뷰 컨테이너
- `styles.css` — 디자인 토큰, 라이트/다크 테마, 카드/캘린더/차트/습관 그리드/팔레트 UI
- `app.js` — 뷰 렌더, 전 영역 CRUD + localStorage v3 영속화, 반복 일정 전개, 알림 계산, 명령 팔레트, 인덱스, GitHub/도입 후보 스냅샷 머지
- `favicon.svg` — 정적 배포 시 브라우저 favicon 404를 막는 로컬 SVG 아이콘
- `scripts/smoke-chrome.mjs` — Chrome DevTools Protocol 기반 출시 스모크 검증
- `scripts/smoke-interactions.mjs` — 독립 Chrome 프로필에서 주요 CRUD·토글·JSON 백업 내보내기/가져오기/전체 초기화·명령 팔레트 사용자 흐름을 클릭/입력으로 검증
- `scripts/package-release.mjs` — 정적 출시 패키지와 SHA-256 manifest 생성
- `scripts/verify-release.mjs` — 출시 패키지 manifest의 파일 목록·바이트·SHA-256 재검증
- `scripts/smoke-mobile.mjs` — 500px 폭 Chrome에서 15개 화면의 모바일 레이아웃 overflow·텍스트·콘솔·네트워크 회귀 검증
- `scripts/smoke-release.mjs` — 출시 패키지를 임시 HTTP 서버로 실제 서빙해 Chrome 라우트 스모크까지 실행하는 전체 출시 게이트
- `scripts/audit-release-readiness.mjs` — 출시 요구사항을 정적 파일·문서·manifest·브라우저 게이트·Git publish 조건 증거에 매핑하는 감사 리포트
- `data/repos.json` — GitHub 저장소 스냅샷 (포트폴리오 시드) · `data/adoption-candidates.json` — OSS 도입 후보 스냅샷 · `scripts/sync-github.sh` — GitHub 스냅샷 재생성
- `vendor/` — 로컬 동봉한 오픈소스 라이브러리 (아래 "도입한 오픈소스" 참고) · `vendor/LICENSES.md`

## 도입한 오픈소스

빌드 도구 없이 동작하도록, 검증된 경량·무의존 OSS를 단일 파일(UMD)로 `vendor/`에 **로컬 동봉**했습니다. CDN 런타임에 의존하지 않아 오프라인(`file://`)에서도 그대로 동작합니다.

| 라이브러리 | 버전 | 라이선스 | 용도 |
| --- | --- | --- | --- |
| [Fuse.js](https://github.com/krisk/Fuse) | 6.6.2 | Apache-2.0 | 명령 팔레트 퍼지(오타 허용)·관련도 랭킹 검색 |
| [marked](https://github.com/markedjs/marked) | 18.0.4 | MIT | 메모 본문 Markdown 렌더 |
| [DOMPurify](https://github.com/cure53/DOMPurify) | 3.4.7 | Apache-2.0 / MPL-2.0 | marked 출력 HTML XSS 소독 |

라이브러리가 로드되지 않은 환경에서도 앱은 정상 동작합니다(검색은 부분일치, 메모는 평문으로 자동 폴백). 여전히 **외부 빌드/패키지 매니저 없이 정적 파일만으로** 동작합니다.

## GitHub 동기화 (선택)

```bash
gh auth status          # 로그인 확인
./scripts/sync-github.sh
```

부팅 시 `data/repos.json`과 `data/adoption-candidates.json`을 읽어 포트폴리오를 시드합니다. 편집·저장한 프로젝트 데이터는 덮어쓰지 않으며, 도입 후보는 누락된 항목만 1회 병합합니다. 파일이 없거나 `file://`로 열면 내장 mock으로 동작합니다.
