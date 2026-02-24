# desci-platform 개선 방향

업데이트: 2026-02-24

## 1. 안정화 우선
목표: 사용자 흐름을 끊는 장애를 먼저 제거한다.

- 완료: `frontend` lint 실패(`Layout.jsx`의 `motion` 사용) 해결.
- 완료: `biolinker` 업로드 API에서 임시 파일 정리(`finally`) 보강.
- 완료: `/health` 엔드포인트를 `degraded` 상태 반환 가능하도록 보강.
- 진행중: 프런트 빌드 크래시(`Node v24 + Vite 7`) 환경 이슈 분리.
  - 조치: `frontend/package.json`에 `engines` 추가 (`>=20.19 <24`).
  - 조치: `frontend/.nvmrc` 추가 (`22.12.0`).
  - 조치: `npm run build:lts` 스크립트 추가 (Node 22로 빌드 강제).

## 2. 품질 게이트 정착
목표: 로컬/CI에서 동일 기준으로 품질을 보장한다.

- 완료: Python 테스트 러너(`pytest`) 및 스모크 테스트(`biolinker/tests/test_smoke_pipeline.py`) 추가.
- 완료: 프런트 빌드 환경 Node LTS 기준 통일 및 CI 워크플로우 추가 (`.github/workflows/desci-platform-quality.yml`).
- 완료: 프런트 번들 예산 검사(`npm run check:bundle`) 및 CI 자동 게이트 추가.

## 3. 기능 고도화
목표: Mock 중심 동작을 실제 운영 플로우로 점진 전환한다.

- 다음 작업: Mock 반환 경로(VC/보상/분석)별 실제 연동 우선순위 정의.
- 진행중: 업로드-분석-매칭-제안서 생성 경로에 대한 E2E 스모크 시나리오 테스트 추가.

## 4. 추가 반영 (2026-02-24)
- 완료: `/me` 엔드포인트 추가로 대시보드 사용자 정보 연동 복구.
- 완료: `/upload` CID 파싱 호환(`cid`/`IpfsHash`) 보강.
- 완료: 문헌리뷰 API 경로 호환(`/api/agent/literature-review`, `/agent/literature-review`) 보강.
- 완료: LLM 미설정 시 제안서 생성 Mock fallback 보강.
