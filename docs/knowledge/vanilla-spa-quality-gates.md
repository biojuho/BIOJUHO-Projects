# 바닐라 JS SPA 품질 게이트 — 테스트·접근성·모바일·벤더 보안

- 작성일: 2026-06-11
- 분류: 프로젝트 운영 지식
- 요약: 프레임워크 없는 정적 SPA는 "순수 함수 테스트 + 실브라우저 스모크 + 수동 벤더 점검"의 3층 구조로 품질을 지킨다. 이 문서는 Node 내장 테스트 러너와 jsdom의 한계, WCAG 2.2 AA에서 실제로 중요한 항목(타깃 크기 24px 최소 vs 모바일 44~48px 권장), 가벼운 스크린샷 비교, vendored 라이브러리(직접 포함한 외부 코드)의 취약점 추적·SRI·롤백 절차를 정리한다.

## 왜 우리에게 필요한가

JooPark Workspace는 빌드 단계 없이 vendor/에 fuse.js·marked·DOMPurify를 직접 포함하므로 `npm audit`(npm이 의존성 취약점을 자동 검사하는 명령) 같은 자동 경보가 없다. 순수 헬퍼 테스트는 363개로 충분하지만, 화면(뷰)을 실제로 조작하는 통합 테스트가 없고 smoke-mobile.mjs·smoke-a11y.mjs는 `npm test` 체인에서 빠져 선택 실행 상태다. 즉 "로직은 검증되지만 화면·모바일·접근성은 사람이 봐야 아는" 구멍이 있다. 또 위키 뷰가 marked+DOMPurify로 마크다운을 HTML로 바꾸므로 XSS(악성 스크립트 주입) 방어 순서를 잘못 잡으면 단일 사용자라도 가져온 백업·문서를 통해 위험해질 수 있다.

## 핵심 지식

### 1. 프레임워크 없는 SPA의 3층 테스트 전략

- **1층 — 순수 로직**: Node 내장 테스트 러너는 [Node v20.0.0부터 안정(stable)이며 `node --test`로 실행하고, mock·커버리지·watch 모드를 기본 제공](https://nodejs.org/api/test.html)한다. 별도 설치가 필요 없어 무빌드 프로젝트와 잘 맞는다.
- **2층 — DOM 구조**: jsdom(브라우저 없이 DOM을 흉내내는 라이브러리)은 [레이아웃 계산을 지원하지 않아 `getBoundingClientRect` 등이 0을 반환하고, 페이지 내비게이션도 미구현](https://github.com/jsdom/jsdom)이다. 따라서 "요소가 존재하는가" 수준까지만 쓰고, 크기·위치·스크롤 검증에는 쓰면 안 된다.
- **3층 — 실브라우저 스모크**: Puppeteer/Playwright(실제 크롬을 코드로 조종하는 도구)는 느리고 깨지기 쉬우므로, 모든 화면을 다 누르는 대신 **핵심 사용자 여정(생성→수정→삭제→undo) 몇 개**만 멀티스텝으로 검증하는 것이 적정 범위다.

### 2. WCAG 2.2 AA — 개인용 SPA에서 실질적으로 중요한 항목

WCAG(웹 접근성 국제 표준) 2.2에서 [새로 추가된 AA 항목은 2.4.11 Focus Not Obscured(포커스가 가려지지 않기), 2.5.7 Dragging Movements(드래그 없이도 조작 가능), 2.5.8 Target Size(Minimum)이고, 3.2.6 Consistent Help와 3.3.7 Redundant Entry는 A 등급이며 4.1.1 Parsing은 폐지](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)됐다.

- **타깃 크기 구분이 핵심**: [2.5.8(AA)은 버튼 등 클릭 대상이 최소 24×24 CSS 픽셀이면 되고, 간격(spacing)·인라인 링크 등 5가지 예외](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)가 있다. 반면 [2.5.5 Target Size(Enhanced)는 44×44 CSS 픽셀로 AAA 등급](https://www.w3.org/WAI/WCAG21/Understanding/target-size.html)이다. 즉 **24px은 합격선, 44px은 권장선**. [web.dev는 모바일 터치 타깃을 약 48px + 주변 8px 간격으로 권장](https://web.dev/articles/accessible-tap-targets)한다(손가락 끝 약 9mm에 해당).
- **대비**: [일반 본문 텍스트는 배경과 4.5:1 이상, 큰 글씨(18pt 또는 14pt 굵게, CJK는 동등 크기)는 3:1 이상 — AA 등급](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html). 라이트/다크 두 테마 모두 따로 확인해야 한다.
- **포커스·키보드**: 다이얼로그를 열면 포커스를 안으로 옮기고 닫으면 원래 버튼으로 되돌리기, 모든 기능을 Tab/Enter/Esc만으로 수행 가능하게 하기, 고정 상단바가 포커스된 요소를 가리지 않게 하기(2.4.11)가 개인용 SPA에서 체감 효과가 가장 크다.

### 3. 시각 회귀 테스트를 가볍게 도입하기

시각 회귀 테스트 = "화면 스크린샷을 기준 이미지와 픽셀 단위로 비교해 의도치 않은 디자인 변화를 잡는 것".

- [pixelmatch는 약 150줄·의존성 0개의 이미지 비교 라이브러리로, threshold(기본 0.1)로 민감도를 조절하고 안티앨리어싱 픽셀을 자동 구분하며 Node에서 pngjs와 함께 사용](https://github.com/mapbox/pixelmatch)한다. 무빌드 프로젝트에 vendor로 넣기에도 적합한 크기다.
- 참고로 [Playwright의 `toHaveScreenshot()`도 내부적으로 pixelmatch를 쓰며, 첫 실행 때 기준 스크린샷을 만들고 `--update-snapshots`로 갱신하며 `maxDiffPixels`로 허용 오차를 둔다. 단 OS·헤드리스 여부 등 환경에 따라 렌더링이 달라지므로 기준 이미지는 테스트를 돌리는 환경과 같은 곳에서 생성](https://playwright.dev/docs/test-snapshots)해야 한다.
- 우리는 이미 Puppeteer류 스크립트(scripts/capture-preview.mjs)가 있으므로 **스크린샷 캡처 + pixelmatch 비교**가 가장 가벼운 조합이다.

### 4. vendored 라이브러리의 보안 관리

- **취약점 추적**: node_modules가 없으면 `npm audit`이 못 돈다. 대신 (a) [GitHub Advisory Database(github.com/advisories) — npm 생태계 포함, GitHub이 검수한(reviewed) 권고만 Dependabot 알림 대상이며 unreviewed는 알림이 안 옴](https://docs.github.com/en/code-security/security-advisories/global-security-advisories/about-the-github-advisory-database), (b) [OSV.dev — npm 취약점 21만+ 건 보유, 웹 검색 또는 패키지명+버전으로 API 질의 가능](https://osv.dev/)을 직접 조회한다.
- **SRI**: [무결성(integrity) 속성에 sha384 해시를 적어두면 파일이 한 글자라도 바뀌었을 때 브라우저가 로드를 거부한다. 교차 출처 로드에는 `crossorigin` 속성이 필요하고, 해시는 `cat 파일.js | openssl dgst -sha384 -binary | openssl base64 -A`로 생성](https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity)한다. 같은 출처(자기 사이트) 파일에는 필수는 아니지만, 우리처럼 변조 감지 목적으로 쓰는 것은 유효하다.
- **업데이트·롤백**: 월 1회 점검 → 취약점 발견 시 vendor/ 파일 교체 → SRI 해시 재계산 → 스모크 통과 확인 → 커밋. 문제가 생기면 `git revert`(해당 커밋만 되돌리는 git 명령) 한 번으로 파일과 해시가 함께 돌아가는 것이 vendoring의 장점이다.

### 5. marked + DOMPurify 조합의 주의점

- [marked 공식 문서는 "Marked does not sanitize the output HTML"(marked는 출력 HTML을 소독하지 않는다)고 명시하고 DOMPurify를 권장](https://marked.js.org/)한다. 즉 `DOMPurify.sanitize(marked.parse(텍스트))` 순서 — **sanitize가 항상 마지막**이어야 한다.
- [DOMPurify README의 핵심 경고: "소독한 HTML을 이후에 수정하면 소독 효과가 쉽게 무효화될 수 있다". 또한 mXSS(브라우저가 HTML을 재해석하며 생기는 변종 XSS)·DOM clobbering 같은 공격을 막아주는 만큼 버전을 최신으로 유지하는 것이 중요](https://github.com/cure53/DOMPurify)하다. `USE_PROFILES`와 `ALLOWED_TAGS`를 섞어 쓰지 말 것.

## 우리 프로젝트에 적용하기

1. **스모크 게이트 승격**: package.json의 `test` 스크립트 체인에 `node scripts/smoke-a11y.mjs && node scripts/smoke-mobile.mjs`를 추가해 선택 실행이 아닌 필수 통과 조건으로 만든다.
2. **멀티스텝 통합 스모크 추가**: `scripts/smoke-delete-undo.mjs`를 본떠 `scripts/smoke-crud-journey.mjs`를 새로 만든다 — 할일 생성→제목 수정→삭제→undo→localStorage(`joopark.workspace.v3`) 상태 확인까지 한 흐름. 같은 패턴을 습관·DB 뷰에도 1개씩.
3. **타깃 크기 자동 점검**: smoke-a11y.mjs에 "모든 button/a의 `getBoundingClientRect()`가 24×24px 이상(모바일 뷰포트에서 주요 액션은 44px 이상)" 검사를 추가한다. jsdom에선 불가능하므로 반드시 실브라우저 스모크에서 한다.
4. **가벼운 시각 회귀**: `scripts/capture-preview.mjs`가 찍는 스크린샷을 기준 이미지로 커밋하고, pixelmatch(의존성 0개) 단일 파일을 vendor/에 추가해 `scripts/smoke-visual.mjs`에서 비교한다. 허용 오차는 maxDiffPixels 개념으로 시작값을 잡고 조정.
5. **월 1회 벤더 점검 절차 문서화**: 매월 1일, ① github.com/advisories에서 `fuse.js`·`marked`·`dompurify` 검색, ② OSV.dev에서 현재 vendor 버전(fuse.js 6.6.2 등)으로 질의, ③ 업데이트 필요 시 파일 교체 후 `openssl dgst -sha384`로 index.html의 SRI 해시 갱신, ④ `npm test` 통과 후 커밋. 이 절차를 docs/improvement-roadmap.md 또는 운영 문서에 체크리스트로 넣는다.

## 주의사항 / 흔한 실수

- jsdom으로 크기·위치·스크롤을 검증하려는 시도 — 레이아웃 미지원이라 항상 0이 나와 테스트가 거짓 통과/거짓 실패한다. 타깃 크기·포커스 가림 검사는 실브라우저에서만.
- 시각 회귀 기준 이미지를 로컬(macOS)에서 만들고 CI(리눅스)에서 비교하면 폰트 렌더링 차이로 항상 실패한다. 기준 생성과 비교는 같은 환경에서.
- `DOMPurify.sanitize()` 결과를 innerHTML에 넣은 뒤 다시 DOM을 조작·재조합하면 소독이 무효화될 수 있다. 소독은 항상 출력 직전 마지막 단계.
- vendor 파일을 교체하고 SRI 해시 갱신을 잊으면 브라우저가 로드를 거부해 사이트 기능이 통째로 죽는다. 교체와 해시 갱신은 한 커밋으로 묶을 것.
- GitHub Advisory의 unreviewed 권고는 Dependabot 알림이 오지 않고, vendored 코드는 애초에 Dependabot 대상이 아니므로 "알림이 없음 = 안전함"이 아니다. 직접 조회가 유일한 방법.
- 24×24px(WCAG 2.5.8 AA)은 법적 최소선일 뿐이다. 모바일에서 자주 누르는 버튼을 24px로 만들면 합격은 해도 쓰기 불편하다 — 주요 타깃은 44~48px.

## 출처

(모두 접근일 2026-06-11)

- https://nodejs.org/api/test.html — Node.js 내장 테스트 러너 공식 문서
- https://github.com/jsdom/jsdom — jsdom README (레이아웃·내비게이션 한계)
- https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/ — WCAG 2.2 신규 성공 기준 목록
- https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html — 2.5.8 Target Size (Minimum), 24px AA
- https://www.w3.org/WAI/WCAG21/Understanding/target-size.html — 2.5.5 Target Size (Enhanced), 44px AAA
- https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html — 1.4.3 대비 4.5:1 / 3:1
- https://web.dev/articles/accessible-tap-targets — 모바일 터치 타깃 48px + 8px 간격 권장
- https://github.com/mapbox/pixelmatch — pixelmatch (150줄, 의존성 0, threshold 0.1)
- https://playwright.dev/docs/test-snapshots — Playwright 시각 비교, 환경 일관성 경고
- https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity — SRI 동작·해시 생성
- https://docs.github.com/en/code-security/security-advisories/global-security-advisories/about-the-github-advisory-database — GitHub Advisory Database (reviewed/unreviewed)
- https://osv.dev/ — OSV 취약점 데이터베이스 (npm 포함, API 질의)
- https://marked.js.org/ — marked 공식 문서 ("does not sanitize the output HTML")
- https://github.com/cure53/DOMPurify — DOMPurify README (소독 후 수정 금지, mXSS)
