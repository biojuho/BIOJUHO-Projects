# 핸드오프 0036 — 공개 릴리스 데이터 경계 강화

- **상태:** DONE
- **기획자:** 사용자 (2026-07-19 채팅 승인)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-07-19

## 목표

공개 릴리스가 명시적으로 허용된 `data/*` 파일만 포함하도록 만들고, GitHub 동기화가 비공개 저장소 메타데이터를 원문으로 다시 기록하지 못하게 한다. 예상 밖 데이터 파일과 비식별화 회귀는 검증 단계에서 실패해야 한다.

## 배경

`data/repos.json`의 현재 비공개 8건은 이름과 URL만 부분 비식별화된 채 언어·활동 시각·커밋 정보가 남아 있었다. 또한 `scripts/package-release.mjs`가 `data/` 전체를 재귀 복사하고 `scripts/sync-github.sh`의 인증 경로가 비공개 저장소 원문 메타데이터를 다시 만들 수 있었다. 2026-07-17에 추가됐던 비식별화 회귀 테스트도 메타 기계 정리 과정에서 제거됐다.

## 범위

- **건드릴 것:** `scripts/sync-github.sh`, `scripts/package-release.mjs`, `scripts/verify-release.mjs`, `scripts/test-pure-helpers.mjs`, `data/repos.json`, 필요 시 공개 데이터 경계 문서, 이 핸드오프, `WORKLOG.md`.
- **건드리지 말 것:** 현재 사용자 데이터·동결 evidence 내용 자체, 앱 제품 기능, 원격 저장소·workflow·배포 상태, 무관한 3단계 제품 개선.

## 단계

1. GitHub GraphQL/REST 입력의 비공개 저장소를 출력 경계에서 결정적으로 비식별화한다.
2. 릴리스 패키저의 `data/` 전체 복사를 명시적 공개 파일 allowlist로 교체한다.
3. 릴리스 verifier가 allowlist 밖 `data/*`를 발견하면 실패하게 한다.
4. 비공개 메타데이터 비식별화와 릴리스 데이터 exact-set 계약을 회귀 테스트로 고정한다.
5. 전체 수용 게이트를 통과시키고 반환 섹션과 `WORKLOG.md`를 기록한다.

## 수용 게이트

- synthetic private GitHub 입력에서 실제 id/name/url/description/topics가 출력되지 않는다.
- `dist/release/data/`의 파일 집합이 공개 allowlist와 정확히 일치한다.
- 예상 밖 sentinel `data/*.json`은 패키지에 들어가지 않으며 verifier도 거부한다.
- `npm run test:unit`
- `npm test`
- `npm run build && node scripts/verify-release.mjs`
- `npm run verify:full`
- `git diff --check`

## 금지사항

- 원격 push, workflow dispatch, 배포, public claim을 하지 않는다.
- 비밀키·토큰·비공개 저장소 원문 메타데이터를 출력하지 않는다.
- 자동 병합이나 범위 밖 리팩터를 하지 않는다.

---

## 반환 섹션 (실행자가 채운다)

- **결과:** `sync-github.sh`가 인증 GraphQL 경로와 비인증 fallback 경로 모두에서 비공개 저장소를 결정적 placeholder로 치환하도록 고쳤다. 릴리스 패키저는 공개 JSON 11개만 복사하며, verifier는 그 exact set과 `repos.json`의 비공개 placeholder 스키마를 독립적으로 검증한다. 현재 `data/repos.json`의 비공개 8건도 같은 계약으로 정규화했고, 실제 동기화 스크립트·패키저·verifier를 실행하는 회귀 테스트를 추가했다.
- **실행한 게이트:** `npm run test:unit` PASS, `npm test` PASS, `npm run build && node scripts/verify-release.mjs` PASS(87 files, 공개 data 11개), `npm run test:product` PASS, `npm run verify:full` PASS, `git diff --check` PASS. 첫 `verify:full`의 마지막 패키지 interaction 단계에서 Chrome/CDP가 한 차례 시간 초과했으나 동일 interaction 격리 실행(68단계), `test:product`, 전체 `verify:full` 순으로 재검증해 모두 PASS했다.
- **사용자 가시 변화 한 줄:** 공개 릴리스에 허용되지 않은 데이터와 비공개 저장소 원문 메타데이터가 다시 섞이는 경로를 차단한다.
- **남은 것 / 막힌 곳:** 로컬 구현과 검증은 완료했다. 금지사항에 따라 원격 push·workflow dispatch·배포는 수행하지 않았으며, 공개 사이트 반영은 별도 사용자 승인과 배포 절차가 필요하다.
