# Next Actions

> 세션 종료 시 `/session-workflow`가 이 파일의 갱신을 제안합니다.
> 2026-04-14 21:00 기준 — 병렬 세션이 QC+SLA+대시보드 슬라이스를 커밋 완료 (2ff5ab3..bc6b73a), smoke 18/18 green.

## Safe Auto (확인 없이 진행 가능)

*(현재 진행 가능한 안전한 자동화 백로그가 없습니다. 완료됨)*

## Needs Approval (진행 전 확인 필요)

- [needs_approval] `.github/workflows/deploy-dashboard.yml` (untracked) — CI 신규 워크플로, 커밋 전 내용 리뷰 + 시크릿 확인
- [needs_approval] origin/main push — 로컬 12+ 커밋 미반영, force push 금지
- [needs_approval] DeSci Platform 프론트엔드 VC 컴포넌트 (2ff5ab3) 디자인 리뷰 + 배포
- [needs_approval] 대시보드 Vercel/Cloud Run 배포 (Dockerfile + SPA static 완료, workflow 대기)
