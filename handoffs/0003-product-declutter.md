# 핸드오프 0003 — 제품 정리: 시드 데이터 노출 제거와 생성 아티팩트 보존 정책

- **상태:** DONE
- **기획자:** Claude Code
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
사용자가 앱에서 보는 것이 "내 데이터"가 되고(OSS 후보 44개 같은 시드 데이터는 기본 숨김), 생성 아티팩트의 git 보존 정책이 명확해진다.

## 배경
점검(`docs/improvement-plan-2026-06.md` §3) 결과: 포트폴리오 뷰가 `data/adoption-candidates.json`의 OSS 후보 44개(AppFlowy, AFFiNE 등)를 사용자 데이터처럼 렌더링하고 있다. 단일 비개발자 사용자에게는 노이즈다. 또한 `autoresearch-results/`(1.9MB)와 `data/`의 생성 JSON들이 커밋 대상인지 캐시인지 불명확해 미커밋 폭증의 원인이 됐다.

## 범위
- **건드릴 것:** 포트폴리오 뷰 렌더링(`portfolio-view.js`, 관련 app.js 연결부), 설정 뷰의 토글 추가(`settings-view.js`), `.gitignore`, `docs/app-architecture.md`(아티팩트 정책 문단), WORKLOG.md.
- **건드리지 말 것:** `data/adoption-candidates.json` 자체(삭제 금지 — 숨김만), localStorage 스키마, 릴리스 게이트 스크립트의 동작.

## 단계
1. 포트폴리오 뷰에서 adoption-candidates 섹션을 **기본 숨김**으로 바꾼다. 설정(또는 포트폴리오 상단)에 "참고 자료 보기" 토글을 추가해 원하면 볼 수 있게 한다. 토글 상태는 기존 설정 저장 경로를 재사용한다.
2. 생성 아티팩트 정책을 정한다:
   - 각 `data/*.json`·`autoresearch-results/*`가 어느 스크립트에서 생성되는지 매핑한다(파일 상단 주석 또는 docs/app-architecture.md 표).
   - 매 실행마다 재생성되는 캐시성 파일은 `.gitignore`에 추가하고 git 추적에서 제거(`git rm --cached`)한다. 증거(evidence)로 보존할 파일은 그대로 둔다. 판단이 애매한 파일은 반환 섹션에 적는다.
3. `docs/app-architecture.md`에 "생성 아티팩트 보존 정책" 문단을 추가한다.
4. WORKLOG.md 기록 후 논리 단위로 커밋한다.

## 수용 게이트
- `npm test` 전체 통과 (구조·문서 게이트 포함)
- 포트폴리오 뷰 기본 화면에 adoption-candidates가 보이지 않고, 토글로 표시 가능 (스모크 또는 수동 확인 결과를 반환 섹션에 기록)
- `git status`가 캐시성 아티팩트 재생성으로 더럽혀지지 않음 (재생성 스크립트 1회 실행 후 확인)

## 금지사항
- 데이터 파일 삭제 금지(숨김·ignore만). 릴리스 게이트 수치를 맞추기 위한 게이트 스크립트 수정 금지.
- 범위 밖 뷰 리팩터 금지.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** 포트폴리오 adoption-candidates 44개는 기본 화면에서 숨기고, 포트폴리오 상단 및 설정 화면의 `참고 자료 보기` 토글로만 표시되도록 연결했다. 토글 상태는 기존 설정 저장 경로(`dashboard.settings.showReferenceProjects`)를 재사용하며, 후보 전용 필터가 숨김 상태에서 남지 않도록 기본 필터로 되돌린다. `data/github-project-discovery.json`과 `data/github-project-discovery.md`는 재생성 캐시로 `.gitignore`에 추가했고, `docs/app-architecture.md`에 생성 아티팩트 보존 정책 표를 추가했다.
- **실행한 게이트:** `npm test` 전체 통과. 포함 게이트: unit, lint, structure, docs, raw/XSS audit, vendor honesty, perf, dashboard verification, product smoke, mobile smoke, a11y smoke, cockpit smoke, packaged release smoke. Product smoke에서 `portfolioReferenceToggle: true`, 포트폴리오 기본 운영 프로젝트 6개/도입 후보 44개 토글 노출을 확인했다. `git diff --check` 통과. `git status --short --ignored -- data/github-project-discovery.json data/github-project-discovery.md autoresearch-results/release-readiness-gates.json`에서 세 파일 모두 ignored(`!!`)로 확인했다.
- **남은 것 / 막힌 곳:** 논리 단위 커밋은 수행하지 않았다. 현재 워크트리에 0001/0002/0004/0005 및 기존 자동화 변경이 함께 섞여 있고, 0001의 push/외부 전송 경로는 사용자 승인 대상이라 이 핸드오프에서는 로컬 변경과 검증까지만 완료했다.
