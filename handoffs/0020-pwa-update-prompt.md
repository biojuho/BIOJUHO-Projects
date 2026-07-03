# 핸드오프 0020 — PWA 새 버전 알림 UI (첫 배포 전 필수)

- **상태:** DONE
- **기획자:** Claude Code
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

> **선행 조건: 0019(런치 커밋 트레인)가 DONE이어야 착수할 수 있다.** 워크트리가 깨끗한 상태에서 시작해, 완료 즉시 커밋 1개로 끝낸다.

## 목표

서비스워커가 새 버전으로 교체될 때 사용자가 그 사실을 알 수 있다. 배포 후 사용자가 구버전 캐시에 조용히 갇히거나, 영문 모르게 화면이 갱신되는 일이 없어진다. (1차 플랜 백로그에서 "첫 배포 전 필수 점검"으로 지정된 항목 — 푸시 전에 넣어야 v1 배포에 포함된다.)

## 배경

- `pwa-runtime.js:112` 부근에 `controllerchange` 리스너가 이미 있으나 현재 무음 처리된다.
- `sw.js`는 `CACHE_VERSION` 기반 캐시 교체를 이미 수행한다 — SW 쪽 변경은 불필요하다.
- 근거 자료: `docs/knowledge/pwa-offline-operations.md` (업데이트 프롬프트 패턴).
- 토스트 UI는 앱에 이미 있는 토스트 패턴(undo 토스트 등)을 재사용한다 — 새 UI 체계를 만들지 않는다.

## 범위

- **건드릴 것:** `pwa-runtime.js`(업데이트 감지·알림 로직), 필요 시 `styles.css` 최소 추가, 관련 스모크(`scripts/smoke-cockpit.mjs` 또는 product smoke에 검증 1건 추가 가능), `WORKLOG.md`, 이 핸드오프 반환 섹션.
- **건드리지 말 것:** `sw.js` 캐시 전략·버전 체계, `index.html` 스크립트 순서, 다른 런타임 파일.

## 단계

1. `registration.addEventListener('updatefound')` + 새 워커 `statechange`로 "새 버전 설치됨(waiting/installed + 기존 controller 존재)" 상태를 감지한다.
2. 감지 시 기존 토스트 패턴으로 "새 버전이 준비되었습니다 — 새로고침" 액션을 노출하거나, `controllerchange` 후 "새 버전이 적용되었습니다" 고지를 띄운다 (둘 중 기존 코드 구조에 자연스러운 쪽, 과한 모달 금지).
3. 수동 시나리오 검증: 로컬 서버에서 SW 등록 → sw.js `CACHE_VERSION` 임시 변경 → 재방문 시 알림 노출 확인 → 버전 원복. 시나리오와 결과를 반환 섹션에 기록한다.
4. 완료 즉시 **커밋 1개**로 마무리하고 WORKLOG에 1줄 기록한다.

## 수용 게이트

- `npm run smoke:cockpit` pass, `npm test` 전체 pass.
- 수동 SW 업데이트 시나리오 기록(반환 섹션).
- 커밋 1개로 완결, `git status` 깨끗.

## 금지사항

- sw.js 캐시 전략·프리캐시 목록 변경 금지. index.html 스크립트 순서 변경 금지.
- push·디스패치 금지. 범위 밖 리팩터 금지(모라토리엄 적용 중).
- 비밀키 노출 금지.

---

## 반환 섹션 (실행자가 채운다)

- **결과:** `pwa-runtime.js`가 기존 active service worker가 있는 상태에서 새 installing/waiting worker를 감지하면 기존 토스트 패턴으로 새 버전 알림을 띄운다. 첫 설치 `controllerchange`는 조용히 지나가도록 판정을 좁혔고, 실제 업데이트에는 "새 버전이 준비되었습니다" 또는 controllerchange fallback의 "새 버전이 적용되었습니다" 토스트와 "새로고침" 액션이 노출된다. `sw.js` 캐시 전략과 `index.html` 스크립트 순서는 바꾸지 않았다.
- **실행한 게이트:** `node --check pwa-runtime.js`, `node --check scripts/test-pure-helpers.mjs`, `npm run test:unit`, `npm run smoke:cockpit`, `npm test` 모두 pass. 수동 SW 업데이트 시나리오는 로컬 테스트 서버에서 첫 `CACHE_VERSION`(`manual-a`)으로 SW 등록/제어 확인 → 서버가 `sw.js`의 `CACHE_VERSION`을 메모리상 `manual-b`로 제공 → `registration.update()` 후 "새 버전이 준비되었습니다새로고침" 토스트와 액션 노출 확인 → 액션 클릭 확인으로 통과했다. 중복 product smoke lock 프로세스는 테스트 충돌 방지를 위해 정리한 뒤 단일 `npm test`로 최종 pass를 확인했다.
- **사용자 가시 변화 한 줄:** 배포 후 새 서비스워커 버전이 준비되면 사용자는 토스트에서 새 버전과 새로고침 액션을 확인할 수 있다.
- **남은 것 / 막힌 곳:** 없음. push/dispatch는 하지 않았다.
