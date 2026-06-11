# 서버 없는 정적 사이트에서 실데이터 가져오기 — 캘린더·CSV·ICS

- 작성일: 2026-06-11
- 분류: 프로젝트 운영 지식
- 요약: 서버가 없는 GitHub Pages 정적 사이트는 OAuth 토큰이나 비밀 URL을 안전하게 다룰 방법이 없다. 따라서 Google Calendar·Todoist·Notion의 **내보내기 파일(.ics/.csv)을 사용자가 직접 업로드**하는 방식이 가장 현실적이며, 파싱은 의존성 없는 ical.js와 TextDecoder로 해결할 수 있다.

## 왜 우리에게 필요한가

JooPark Workspace는 모든 데이터를 localStorage(`joopark.workspace.v3`)에만 저장하는 순수 정적 SPA라, 지금은 일정·할일을 전부 손으로 입력해야 한다. 이미 쓰고 있는 Google Calendar나 다른 앱의 데이터를 한 번에 들여올 수 있으면 체감 가치가 크게 올라간다. 문제는 우리에게 서버가 없어서 비밀키 보관·토큰 교환·프록시 운영이 전부 불가능하다는 점이다. 이 문서는 "서버 없이 어디까지 가능한가"를 정리하고, 파일 업로드 기반 가져오기를 1순위 결론으로 제시한다.

## 핵심 지식

### 1. Google Calendar를 읽어오는 세 가지 길

- **비밀 iCal 주소(Secret address)**: 캘린더 설정 → "캘린더 통합"에서 복사하는 개인용 구독 URL. 읽기 전용이며, Google은 ["이 주소를 다른 사람과 공유하지 말라"고 명시](https://support.google.com/calendar/answer/37648?hl=en)하고, 유출 시 Reset으로 무효화하라고 안내한다. *URL 자체가 비밀키*라서 코드나 외부 서비스에 넣는 순간 캘린더 전체가 노출된다.
- **공개 캘린더 iCal**: 캘린더를 공개로 전환해야만 쓸 수 있어 개인 일정에는 부적합.
- **Google Calendar API**: 공식 [JavaScript 퀵스타트](https://developers.google.com/workspace/calendar/api/quickstart/js)에 따르면 개인 데이터 접근에는 OAuth 2.0 클라이언트 ID와 사용자 동의(Google Identity Services 토큰 클라이언트)가 필수다. 정적 사이트에서도 기술적으로는 되지만, 토큰을 localStorage에 보관해야 하고 Cloud 콘솔 설정·동의 화면 심사가 필요해 단일 사용자 개인 도구에는 과하다.
- **현실적 대안 — 내보내기 파일**: Google은 [캘린더를 .ics 파일로 내보내기](https://support.google.com/calendar/answer/37111?hl=en)를 공식 지원한다(단일 캘린더는 .ics, 전체는 .zip). 비밀이 외부로 나가지 않는 유일한 경로다.

### 2. 브라우저에서 iCal URL을 직접 fetch하면 — CORS 벽

CORS(교차 출처 리소스 공유)란 다른 도메인의 데이터를 브라우저가 마음대로 읽지 못하게 막는 보안 규칙이다. calendar.google.com은 우리 사이트에 읽기를 허용해 주지 않으므로 비밀 iCal 주소를 fetch하면 차단된다. 흔한 우회책인 공개 CORS 프록시는 위험하다 — [HTTP Toolkit의 분석](https://httptoolkit.com/blog/cors-proxies/)에 따르면 "프록시는 통과하는 모든 요청·응답을 읽고 무엇이든 할 수 있으며", 보낸 개인 데이터는 운영자에게 전부 노출된다. 비밀 iCal URL을 프록시에 넘기는 것은 캘린더 열쇠를 모르는 사람에게 맡기는 것과 같다. **결론: URL 구독은 포기하고 파일 업로드로 간다.**

### 3. ICS(RFC 5545) 파싱 — 직접 짜지 말 것

.ics는 단순 텍스트처럼 보이지만 75바이트 줄바꿈 접기, 타임존, 그리고 반복 일정 규칙(RRULE — "매주 화요일" 같은 규칙을 한 줄로 적는 문법)에 예외 날짜(EXDATE)까지 얽혀 직접 파싱하면 반드시 틀린다. [ical.js](https://github.com/kewisch/ical.js/blob/main/README.md)는 RFC 5545 전용 파서로 **의존성 0개, MPL-2.0 라이선스**이고 브라우저용 빌드(`dist/ical.min.js`)를 제공하며 RRULE 전개(RecurExpansion)까지 지원한다. [최신 릴리스는 v2.2.1(2025-08-08)](https://github.com/kewisch/ical.js/releases)로 우리 벤더 정책(vendor/ + SRI)에 맞는 1순위 후보다. 파일 크기는 확인 필요.

### 4. CSV 가져오기 — 인코딩이 절반이다

- 업로드는 `<input type="file" accept=".csv">`로 받고, 파싱은 [Papa Parse](https://www.papaparse.com/)(의존성 0, RFC 4180 준수, header 옵션으로 첫 줄을 열 이름으로 매핑) 같은 검증된 파서를 쓴다. 단순 포맷이면 직접 파서도 가능하나 따옴표 안 쉼표 처리를 잊기 쉽다.
- **한국어 인코딩**: 옛 엑셀 CSV는 EUC-KR(한국어 전용 옛 인코딩)인 경우가 많다. [MDN TextDecoder](https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder/TextDecoder)에 따르면 기본값은 UTF-8이고 Encoding 명세의 모든 라벨을 지원하므로(`new TextDecoder("euc-kr")`), `fatal: true`로 UTF-8 해석을 먼저 시도하고 실패하면 euc-kr로 재시도하는 폴백이 가능하다. BOM(UTF-8 표식 3바이트)은 기본 설정에서 자동 제거된다.

### 5. 주요 서비스의 내보내기 포맷

- [Todoist](https://todoist.com/help/articles/360000748525): 프로젝트별 "CSV로 내보내기" 지원. UTF-8 필수, TYPE(task/section/note)·CONTENT·PRIORITY(1이 최고)·DATE·DURATION 열 구조. **완료된 작업은 내보내기에 포함되지 않음**에 유의.
- [Notion](https://www.notion.com/help/export-your-content): 페이지는 Markdown/HTML, 데이터베이스는 CSV(+하위 페이지 Markdown)로 내보낸다.

### 6. 동기화 UX — 출처 배지

업로드 방식은 실시간 동기화가 아니라 "스냅샷 가져오기"다. 사용자가 혼동하지 않도록 가져온 항목에는 출처(파일명·가져온 날짜)를 배지로 표시하고, 같은 파일을 다시 올렸을 때 중복 생성을 막는 키(ICS의 UID 필드)를 활용한다.

## 우리 프로젝트에 적용하기

1. **벤더 추가**: ical.js v2.2.1의 `dist/ical.min.js`를 `vendor/ical.js/`에 받고, SRI 해시를 `openssl dgst -sha384 -binary vendor/ical.js/ical.min.js | openssl base64 -A`로 생성해 `index.html`의 `<script>`에 `integrity` 속성으로 기록(기존 fuse.js/marked/dompurify와 동일 패턴).
2. **ICS 가져오기**: 캘린더 뷰 도구줄에 "ICS 가져오기" 버튼 + `<input type="file" accept=".ics">`. 파싱 → 이벤트마다 `{ title, start, end, rrule, uid, source }`로 변환해 기존 일정 스키마에 합류. UID 중복이면 갱신.
3. **CSV 가져오기**: 할일 뷰에 CSV 업로드 → `file.arrayBuffer()` → TextDecoder UTF-8(fatal) → 실패 시 euc-kr 폴백 → 첫 줄 헤더를 우리 필드(제목/마감일/우선순위)에 매핑하는 2단계 미리보기 UI. Todoist CSV는 TYPE=task 행만 취한다.
4. **출처 배지**: 항목에 `source: { kind: 'ics'|'csv', label, importedAt }` 저장, 카드에 "Source: 파일명 · 2026-06-11" 배지 렌더링.
5. **테스트**: 파싱·매핑 헬퍼를 순수 함수로 분리해 `scripts/test-pure-helpers.mjs`에 케이스 추가(접힌 줄, EXDATE, EUC-KR 샘플, 따옴표 쉼표). 스모크는 `scripts/smoke-interactions.mjs` 패턴으로 업로드 흐름 1건.

## 주의사항 / 흔한 실수

- 비밀 iCal URL을 코드·설정·외부 프록시 어디에도 넣지 말 것. 유출 시 캘린더 설정에서 즉시 Reset.
- 공개 CORS 프록시 경유 fetch는 "동작은 하지만" 데이터 전체를 제3자에게 넘기는 것 — 금지.
- RRULE 반복 일정을 단일 이벤트로만 들여오면 "매주 회의"가 한 번만 보인다. ical.js의 전개 기능을 쓰되 전개 범위(예: 향후 1년)를 제한해 localStorage 폭증을 막는다.
- CSV를 `FileReader.readAsText`로만 읽으면 EUC-KR 파일이 통째로 깨진다. 반드시 TextDecoder 폴백 경로를 둘 것.
- Todoist CSV에는 완료 작업이 없다 — "전체 백업 가져오기"로 오해하지 않도록 UI에 안내 문구.
- 같은 파일 재업로드 시 중복 생성 방지(ICS UID, CSV는 제목+날짜 해시) 없이는 데이터가 두 배가 된다.

## 출처

(모두 접근일 2026-06-11)

- https://support.google.com/calendar/answer/37648?hl=en — Google Calendar 비밀 iCal 주소
- https://support.google.com/calendar/answer/37111?hl=en — Google Calendar .ics 내보내기
- https://developers.google.com/workspace/calendar/api/quickstart/js — Calendar API JS 퀵스타트(OAuth 필수)
- https://github.com/kewisch/ical.js/blob/main/README.md — ical.js README
- https://github.com/kewisch/ical.js/releases — ical.js 릴리스(v2.2.1)
- https://httptoolkit.com/blog/cors-proxies/ — 공개 CORS 프록시의 위험
- https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder/TextDecoder — TextDecoder 생성자
- https://www.papaparse.com/ — Papa Parse
- https://todoist.com/help/articles/360000748525 — Todoist CSV 내보내기/가져오기
- https://www.notion.com/help/export-your-content — Notion 내보내기 포맷
