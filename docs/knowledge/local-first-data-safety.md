# localStorage만 쓰는 앱의 데이터 안전 — 한계, 영속성, 마이그레이션

- 작성일: 2026-06-11
- 분류: 프로젝트 운영 지식
- 요약: localStorage는 오리진당 약 5MiB 제한이 있고, 브라우저가 저장 공간 압박이나 Safari의 7일 규칙으로 데이터를 통째로 지울 수 있다. `navigator.storage.persist()` 요청, 스키마 버저닝, 정기 백업 내보내기로 단일 저장소 리스크를 줄이는 방법을 정리한다.

## 왜 우리에게 필요한가

JooPark Workspace는 할일·습관·통계·PM·DB·위키 데이터 전부를 localStorage 키 하나(`joopark.workspace.v3`)에 담는다. 백업 서버가 없으므로 브라우저가 이 키를 지우면 데이터가 전부 사라진다. 특히 Safari에서 7일간 사이트와 상호작용하지 않으면 localStorage가 자동 삭제될 수 있어, 단일 사용자 앱이라도 "잠시 안 쓰다 돌아오니 텅 빔" 시나리오가 현실적인 위협이다. GitHub Pages 첫 배포를 앞둔 지금, 영속 저장소 요청과 백업 UX를 미리 넣어 두는 것이 가장 저렴한 보험이다.

## 핵심 지식

### 1. 용량 한계: 약 5MiB, 넘으면 QuotaExceededError

[MDN 저장소 할당량 문서](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)에 따르면 localStorage와 sessionStorage는 합쳐서 오리진(사이트 주소 단위)당 최대 10MiB, 각각 약 5MiB로 제한되며, 초과 저장을 시도하면 `QuotaExceededError` 예외(저장 실패 오류)가 발생한다. 반면 IndexedDB(브라우저 내장 데이터베이스)는 Chrome 기준 디스크의 최대 60%까지 쓸 수 있어 용량 여유가 수백 배 크다. 현재 남은 공간은 `navigator.storage.estimate()`로 확인할 수 있다.

### 2. 브라우저가 데이터를 지우는 조건

- **Safari ITP 7일 규칙**: [WebKit 공식 블로그](https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/)는 "사이트와 상호작용 없이 Safari를 7일 사용하면" localStorage·IndexedDB·서비스워커 캐시 등 스크립트가 쓴 저장소를 전부 삭제한다고 명시한다. 단, **홈 화면에 추가한 웹앱은 예외**로, 자체 사용 카운터를 쓰므로 데이터가 지워지지 않는 것이 정상 동작이다.
- **저장 공간 압박 시 eviction(자동 삭제)**: 디스크가 부족하면 브라우저는 [가장 오래 안 쓴 오리진부터(LRU) 데이터를 통째로 삭제](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)한다. 일부만 지우는 게 아니라 오리진 전체가 한 번에 사라지며, 영속(persistent) 승인을 받은 오리진은 건너뛴다.
- **시크릿/사생활 보호 모드**: [MDN localStorage 문서](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)에 따르면 마지막 사생활 보호 탭이 닫힐 때 데이터가 삭제된다.

### 3. navigator.storage.persist() — 영속 저장소 요청

[`navigator.storage.persist()`](https://developer.mozilla.org/en-US/docs/Web/API/StorageManager/persist)를 호출하면 "사용자가 직접 지우기 전에는 브라우저가 자동 삭제하지 않는" 영속 모드를 요청할 수 있다(불리언으로 응답, HTTPS 필수). [web.dev 영속 저장소 가이드](https://web.dev/articles/persistent-storage)에 따르면 Chrome은 사이트 참여도·북마크·PWA 설치·알림 권한 같은 휴리스틱으로 묻지 않고 자동 승인/거부하고, Firefox는 사용자에게 팝업으로 묻는다. Safari도 15.2+에서 API를 지원한다. 페이지 로드 시가 아니라 **사용자가 중요한 데이터를 저장하는 동작 안에서** 요청하는 것이 모범 사례다.

### 4. IndexedDB로 옮겨야 하는 시점

[web.dev 웹 저장소 가이드](https://web.dev/articles/storage-for-the-web)는 localStorage가 동기(synchronous) API라 메인 스레드를 차단하고, 문자열만 저장 가능하며, 워커에서 접근 불가하므로 일반 데이터에는 IndexedDB를 권장한다. [RxDB의 localStorage 분석](https://rxdb.info/articles/localstorage.html)은 구체적 이주 기준으로 (a) 조건 검색이 잦을 때, (b) 큰 JSON 문서를 저장할 때, (c) 읽기/쓰기가 빈번할 때를 들고, 작은 설정값·소규모 키-값에는 localStorage가 여전히 적합하다고 본다. 즉 **용량이 1~2MiB를 넘보거나 저장 시 화면이 버벅이기 시작하면** 이주 신호다.

### 5. 스키마 버저닝 모범 사례

IndexedDB는 [버전 번호가 올라갈 때만 발동하는 onupgradeneeded 이벤트로 마이그레이션을 구조화](https://thevalleyofcode.com/lesson/indexeddb/migrations/)하지만, localStorage는 전부 수동이다. 통용되는 패턴: (a) 최상위뿐 아니라 **레코드(항목)마다 `version` 필드**를 두고, (b) 읽을 때 구버전이면 즉석 변환하는 **lazy migration**(한꺼번에가 아니라 읽는 시점에 천천히 변환)으로 일괄 변환 실패 리스크를 줄이며, (c) 업그레이드 직전 원본 전체를 별도 키(예: `joopark.workspace.v3.backup-<날짜>`)로 **스냅샷 저장해 롤백 체크포인트**를 만든다. [Dexie의 버저닝 문서](https://dexie.org/docs/Tutorial/Migrating-existing-DB-to-Dexie)처럼 v1→v3 직행 사용자도 처리되도록 마이그레이션을 버전 사슬로 누적 선언하는 것이 안전하다.

### 6. 내보내기/백업 UX

JSON 파일 내보내기가 기본이다. [showSaveFilePicker](https://developer.mozilla.org/en-US/docs/Web/API/Window/showSaveFilePicker)(저장 위치를 직접 고르는 네이티브 대화상자)는 파일 핸들을 돌려줘 같은 파일에 반복 저장이 가능하지만 Baseline이 아니어서(주로 Chromium 계열) Safari·Firefox용으로 `<a download>` + Blob 폴백이 필요하며, HTTPS와 사용자 제스처(클릭) 안에서만 호출할 수 있다. 마지막 백업 시점을 기록해 두고 일정 기간(예: 14일) 지나면 화면에 백업 리마인더를 띄우는 패턴이 단일 기기 앱의 표준적 보호책이다.

## 우리 프로젝트에 적용하기

1. **persist() 요청 추가** — `pwa-runtime.js`(또는 `workspace-storage.js` 초기화부)에 `navigator.storage.persisted()` 확인 후 미승인 시 설정 화면에 "데이터 보호 켜기" 버튼을 추가. 클릭(사용자 제스처) 안에서 `navigator.storage.persist()` 호출, 결과를 토스트로 표시. GitHub Pages는 HTTPS라 조건 충족.
2. **Safari 7일 리스크 명시 + PWA 안내** — Safari 사용 시 첫 화면 또는 설정에 "7일 미접속 시 데이터가 삭제될 수 있음 → 홈 화면에 추가하면 예외" 안내 배너. 이미 PWA(sw.js)가 있으므로 홈 화면 설치 유도가 가장 효과적인 방어다.
3. **백업 내보내기 강화** — `backup-import-ui.js`에 마지막 내보내기 시각을 localStorage 별도 키로 저장하고, 14일 경과 시 상단 리마인더 표시. `backup-import-guards.js`의 가져오기 검증에 스키마 버전 확인을 유지.
4. **레코드 버전 필드 도입** — `workspace-storage.js`는 v2→v3 blob 전체 마이그레이션만 있으므로, 다음 스키마 변경 때 각 레코드에 `v` 필드를 넣고 읽기 시 변환(lazy migration)으로 전환. 마이그레이션 직전 `joopark.workspace.v3.snapshot` 키에 원본 스냅샷 저장.
5. **용량 감시** — `scripts/test-pure-helpers.mjs`류에 직렬화 크기 점검을 추가하고, 앱에서 `navigator.storage.estimate()`와 `JSON.stringify(state).length`로 1MiB 초과 시 경고. 2MiB를 넘으면 `dashboard-storage.js`의 6개 컬렉션 단위로 IndexedDB 이주를 검토.

## 주의사항 / 흔한 실수

- eviction은 키 일부가 아니라 **오리진 전체가 한 번에** 지워진다 — "일부는 남겠지"라는 가정은 틀렸다.
- `persist()`가 `false`를 반환해도 앱은 계속 동작한다. 거부됐다고 반복 호출하지 말고, 백업 내보내기를 대안으로 안내할 것.
- 모노레포 주의: GitHub Pages에서 같은 오리진(biojuho.github.io)을 쓰는 다른 프로젝트와 **localStorage 5MiB 한도와 eviction 운명을 공유**한다. 키 네임스페이스만으로는 격리되지 않는다.
- 페이지 로드 직후 `persist()`를 자동 호출하면 Firefox에서 맥락 없는 권한 팝업이 떠 사용자를 혼란시킨다. 반드시 사용자 동작 안에서.
- 저장 실패(`QuotaExceededError`)를 try/catch 없이 두면 조용히 데이터가 유실된다. 모든 `setItem` 경로에서 잡아 사용자에게 알릴 것.
- 시크릿 모드에서는 탭을 닫으면 데이터가 사라진다. "왜 데이터가 없죠" 문의의 흔한 원인.
- showSaveFilePicker만 믿으면 Safari/Firefox에서 백업이 막힌다. `<a download>` 폴백을 항상 유지.

## 출처

(모두 2026-06-11 접근)

- [Storage quotas and eviction criteria — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)
- [Full Third-Party Cookie Blocking and More — WebKit Blog](https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/)
- [StorageManager.persist() — MDN](https://developer.mozilla.org/en-US/docs/Web/API/StorageManager/persist)
- [Persistent storage — web.dev](https://web.dev/articles/persistent-storage)
- [Window.localStorage — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)
- [Storage for the web — web.dev](https://web.dev/articles/storage-for-the-web)
- [localStorage in JavaScript: limitations and alternatives — RxDB](https://rxdb.info/articles/localstorage.html)
- [Window.showSaveFilePicker() — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/showSaveFilePicker)
- [Migrating existing DB to Dexie — Dexie.js Docs](https://dexie.org/docs/Tutorial/Migrating-existing-DB-to-Dexie) (검색 결과 참고, 본문 직접 확인은 미수행 — 버전 사슬 패턴은 확인 필요)
- [IndexedDB: Migrations — The Valley of Code](https://thevalleyofcode.com/lesson/indexeddb/migrations/) (검색 결과 참고)
