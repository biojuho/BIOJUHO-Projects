# PWA 서비스워커 운영 — 업데이트 수명주기와 오프라인 UX

- 작성일: 2026-06-11
- 분류: 프로젝트 운영 지식
- 요약: 서비스워커(웹앱을 오프라인에서도 돌게 해 주는 백그라운드 스크립트)는 "설치 → 대기 → 활성화" 수명주기를 가지며, 이를 모르면 배포 후에도 사용자에게 구버전이 계속 보이는 사고가 난다. 이 문서는 업데이트 수명주기, 캐시 전략, iOS 제약, 오프라인 UX를 정리하고 첫 GitHub Pages 배포 전 체크리스트를 제시한다.

## 왜 우리에게 필요한가

JooPark Workspace는 `sw.js` + `pwa-runtime.js`로 PWA가 이미 켜져 있고, 곧 GitHub Pages 첫 배포를 앞두고 있다. 지금 구조는 오프라인 감지는 하지만 "새 버전이 나왔어요" 프롬프트가 없어서, 배포 후 캐시된 구버전이 화면에 남는 사고가 가장 흔한 위험이다. 모든 데이터가 localStorage 하나에 있으므로 iOS Safari의 저장소 정리 정책도 직접적인 데이터 유실 위험이다. 단일 사용자 앱이라 복잡한 인프라 없이, 수명주기 원리만 정확히 알면 예방 가능하다.

## 핵심 지식

### 1. 업데이트 수명주기 — 새 서비스워커는 왜 '대기(waiting)'하는가

브라우저는 사이트 방문 시 `sw.js` 파일을 받아 기존 것과 **바이트 단위로 비교**해 다르면 새 버전으로 간주하고 백그라운드에서 설치한다([web.dev: Service worker lifecycle](https://web.dev/articles/service-worker-lifecycle), [web.dev: Update](https://web.dev/learn/pwa/update)). 설치된 새 워커는 바로 활성화되지 않고 **대기 상태**에 머문다 — "사이트의 한 버전만 실행되도록" 보장하기 위해, 구버전 워커가 제어하는 탭이 모두 닫힐 때까지 기다리는 것이다([MDN: Using Service Workers](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers)).

- `skipWaiting()`: 대기를 건너뛰고 즉시 활성화. 단, "구버전으로 로드된 페이지를 새 워커가 제어"하게 되어 페이지 코드와 캐시 버전이 어긋날 수 있다([web.dev: lifecycle](https://web.dev/articles/service-worker-lifecycle)).
- `clients.claim()`: 활성화된 워커가 아직 제어받지 않는 열린 페이지들을 즉시 제어. 첫 설치 때 유용하지만 같은 종류의 버전 불일치 위험이 있다([web.dev: lifecycle](https://web.dev/articles/service-worker-lifecycle)).

**권장 패턴 — "새 버전 있음 → 새로고침" 프롬프트**: 페이지가 대기 중인 워커를 감지하면 사용자에게 토스트를 띄우고, 수락 시 워커에 `{type:'SKIP_WAITING'}` 메시지를 보내 워커가 `self.skipWaiting()`을 실행, 페이지는 `controllerchange` 이벤트를 받아 `location.reload()`한다([Chrome Developers: Handling service worker updates](https://developer.chrome.com/docs/workbox/handling-service-worker-updates)).

### 2. 캐시 전략 — 어떤 자원에 어떤 전략?

[web.dev: Serving](https://web.dev/learn/pwa/serving) 기준:

| 전략 | 동작 | 적합한 자원 |
|---|---|---|
| Cache-first | 캐시 먼저, 없으면 네트워크 | 잘 안 바뀌는 앱 셸(HTML/CSS/JS), 폰트 |
| Network-first | 네트워크 먼저, 실패하면 캐시 | 자주 바뀌는 데이터, 최신성이 중요한 응답 |
| Stale-while-revalidate | 캐시를 즉시 주고 뒤에서 갱신 | 약간 낡아도 되는 목록·피드류 |

### 3. 캐시 버전 관리와 오래된 캐시 정리

캐시 이름에 버전을 넣고(`v1`, `v2`…), 새 워커의 `activate` 이벤트에서 `caches.keys()`로 전체 목록을 받아 유지 목록에 없는 캐시를 `caches.delete()`로 지우는 것이 표준 패턴이다. `event.waitUntil()`에 넣으면 정리가 끝난 뒤에야 fetch 이벤트가 온다([MDN: Using Service Workers](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers)). 새 워커를 설치해도 이전 캐시가 **자동 삭제되지 않으므로** 코드로 직접 지워야 한다([web.dev: Update](https://web.dev/learn/pwa/update)).

### 4. iOS Safari PWA 제약 (2026 기준)

- **홈 화면 추가**: 자동 설치 프롬프트(`beforeinstallprompt`)가 없어 사용자가 공유 → "홈 화면에 추가"를 직접 해야 한다([MagicBell: PWA iOS Limitations 2026](https://www.magicbell.com/blog/pwa-ios-limitations-safari-support-complete-guide)). EU에서도 홈 화면 웹앱은 iOS 17.4부터 계속 지원된다(애플이 제거 계획을 철회)([Apple: DMA and apps in the EU](https://developer.apple.com/support/dma-and-apps-in-the-eu/)).
- **저장소**: Safari에서 7일간 해당 사이트와 상호작용 없이 Safari를 사용하면 localStorage·IndexedDB·서비스워커 등록이 삭제될 수 있다. 단 **홈 화면에 추가한 웹앱은 자체 사용일 카운터를 가져 사실상 면제**다([WebKit: Full Third-Party Cookie Blocking](https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/)). Safari 17부터 용량 한도는 브라우저(홈 화면 웹앱 포함) 기준 오리진당 디스크의 최대 60%로 늘었고, `navigator.storage.persist()`로 영구 모드를 요청하면 홈 화면 설치 여부 등의 휴리스틱으로 승인된다([WebKit: Updates to Storage Policy](https://webkit.org/blog/14403/updates-to-storage-policy/)).
- **푸시**: iOS 16.4+에서 홈 화면 설치된 PWA만 웹 푸시 가능, Safari 탭에서는 불가([MagicBell](https://www.magicbell.com/blog/pwa-ios-limitations-safari-support-complete-guide)). Background Sync API는 iOS 미지원(2026-06 기준, 동 출처).

### 5. 오프라인 상태 표시 UX

오프라인을 색상 하나로만 표시하지 말고 아이콘+라벨을 함께 쓰고, "오프라인" 같은 기술 용어 대신 행동 중심 문구("저장은 됩니다, 연결되면 동기화돼요")를 쓰라는 것이 [web.dev 오프라인 UX 가이드라인](https://web.dev/articles/offline-ux-design-guidelines)의 핵심이다. 지금 상태에서 무엇을 할 수 있는지와 데이터가 언제 것인지(마지막 갱신 시각)를 함께 보여 준다. 참고로 `navigator.onLine`은 false면 확실히 오프라인이지만 **true라고 인터넷이 되는 보장은 없다**([MDN: Navigator.onLine](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/onLine)).

### 6. GitHub Pages 정적 호스팅에서의 주의점

- **스코프**: 서비스워커는 기본적으로 자기 파일이 놓인 디렉터리 이하만 제어한다([MDN](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers)). 모노레포 하위 경로(`/BIOJUHO-Projects/...`)로 배포하면 상대 경로 등록(`./sw.js`, scope `./`)이 안전하다 — 우리 `pwa-runtime.js`가 이미 이렇게 한다.
- **HTTP 캐시**: GitHub Pages는 모든 파일에 `Cache-Control: max-age=600`(10분)을 주고 커스텀 헤더를 못 바꾼다([GitHub Community 토론](https://github.com/orgs/community/discussions/11884)). 다만 `sw.js` 자체의 업데이트 확인은 `updateViaCache` 기본값(`"imports"`) 덕분에 HTTP 캐시를 거치지 않으므로([MDN: updateViaCache](https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerRegistration/updateViaCache)) 배포 후 늦어도 다음 방문(또는 24시간 주기 확인) 때 새 워커가 감지된다([web.dev: lifecycle](https://web.dev/articles/service-worker-lifecycle)). 일반 정적 자원은 10분간 낡은 버전이 보일 수 있다.

## 우리 프로젝트에 적용하기

현재 `sw.js`는 네트워크-우선 전략 + 버전 캐시 이름(`CACHE_VERSION`, 1행) + `activate`에서 옛 캐시 삭제(`clearOldCaches`)까지 이미 갖췄고, `install`에서 무조건 `skipWaiting()`, `activate`에서 `clients.claim()`을 호출한다. 빠진 것은 **업데이트 알림**이다.

1. **배포마다 캐시 버전 올리기**: 릴리스 시 `/Users/ju-hopark/Desktop/JooPark Project/sw.js` 1행 `CACHE_VERSION` 문자열을 반드시 변경. 릴리스 게이트 스크립트(`scripts/audit-release-readiness.mjs`)에 "직전 커밋 대비 CACHE_VERSION 변경 여부" 검사를 추가한다.
2. **업데이트 토스트 추가**: `pwa-runtime.js`의 `register()`에서 `registration.addEventListener("updatefound", ...)`로 새 워커의 `statechange`를 듣고, `state === "installed" && navigator.serviceWorker.controller`일 때 "새 버전이 준비됐어요 — 새로고침" 토스트를 띄운다. 현재처럼 무조건 `skipWaiting`을 유지한다면 최소한 `controllerchange` 시 자동 `location.reload()`가 아닌 **안내 후 수동 새로고침**으로 처리한다(편집 중 데이터 보호). 정석은 `skipWaiting`을 메시지 수신(`SKIP_WAITING`) 시에만 실행하도록 옮기는 것.
3. **첫 배포 후 검증 절차**: 배포 → 일반 창에서 열기 → 두 번째 배포 푸시 → 페이지 새로고침 후 DevTools > Application > Service Workers에서 새 워커가 활성화되고 캐시 이름이 새 `CACHE_VERSION`으로 바뀌는지 확인. 시크릿 창 결과와 비교해 구버전 잔존 여부 점검.
4. **버전 가시화**: 푸터나 설정 뷰(`settings-view.js`)에 현재 `CACHE_VERSION`을 표시해 "지금 무슨 버전인가"를 누구나 확인 가능하게 한다.
5. **iOS 데이터 보호**: 사용자 안내문에 "iPhone에서는 홈 화면에 추가해서 쓰기"를 명시하고(7일 삭제 면제), `pwa-runtime.js`에 `navigator.storage.persist()` 요청을 추가한다. 기존 백업 내보내기(`backup-import-ui.js`) 주기 실행을 권장 문구로 노출.
6. **비상 스위치 숙지**: 캐시 사고 시 `sw.js`를 "모든 캐시 삭제 + 자기 등록 해제(`registration.unregister()`)"만 하는 버전으로 교체 배포하면 복구된다.

## 주의사항 / 흔한 실수

- `CACHE_VERSION`을 안 올리고 배포하면 새 워커는 설치돼도(바이트 비교로 sw.js가 같으면 아예 미설치) 옛 캐시를 계속 쓴다 — 자산 목록 변경 시 버전 변경은 필수.
- `skipWaiting()` + 자동 reload 조합은 사용자가 입력 중일 때 화면을 날릴 수 있다. reload는 반드시 사용자 동의 후.
- `cache.addAll()`은 목록 중 **하나라도 404면 설치 전체가 실패**한다 — `sw.js`의 80여 개 자산 목록과 실제 파일이 어긋나지 않는지 릴리스 게이트로 검사할 것.
- `navigator.onLine === true`를 "인터넷 됨"으로 믿지 말 것. 실제 fetch 실패 처리로 보완.
- GitHub Pages의 10분 HTTP 캐시 때문에 배포 직후 확인은 시크릿 창 또는 10분 후에. "안 바뀌었다"고 곧바로 재배포를 반복하지 말 것.
- localStorage는 서비스워커 캐시와 별개다 — 캐시를 다 지워도 할일 데이터는 남지만, iOS Safari 탭에서만 쓰면 7일 규칙으로 둘 다 삭제될 수 있다.

## 출처

모두 2026-06-11 접근.

- https://web.dev/articles/service-worker-lifecycle — 수명주기, waiting, skipWaiting/claim 위험, 바이트 비교
- https://web.dev/learn/pwa/serving — cache-first / network-first / stale-while-revalidate
- https://web.dev/learn/pwa/update — 업데이트 감지, 옛 캐시 수동 삭제 필요
- https://developer.chrome.com/docs/workbox/handling-service-worker-updates — 새로고침 프롬프트 패턴(SKIP_WAITING 메시지)
- https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers — activate 캐시 정리 패턴, 스코프 규칙
- https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerRegistration/updateViaCache — sw.js 업데이트 확인 시 HTTP 캐시 기본 우회
- https://developer.mozilla.org/en-US/docs/Web/API/Navigator/onLine — onLine의 한계
- https://web.dev/articles/offline-ux-design-guidelines — 오프라인 UX 가이드라인
- https://webkit.org/blog/14403/updates-to-storage-policy/ — Safari 17 저장소 한도, persist()
- https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/ — 7일 저장소 삭제 규칙과 홈 화면 웹앱 면제
- https://developer.apple.com/support/dma-and-apps-in-the-eu/ — EU 홈 화면 웹앱 유지 결정
- https://www.magicbell.com/blog/pwa-ios-limitations-safari-support-complete-guide — iOS 푸시(16.4+)·설치 프롬프트 부재·Background Sync 미지원 (주의: 이 글의 EU 제거·50MB 한도 서술은 위 공식 출처와 어긋나 채택하지 않음)
- https://github.com/orgs/community/discussions/11884 — GitHub Pages Cache-Control: max-age=600
