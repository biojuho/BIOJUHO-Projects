# desci-platform 개선 방향

업데이트: 2026-03-17

## 1. 안정화 우선 ✅ 완료
목표: 사용자 흐름을 끊는 장애를 먼저 제거한다.

- 완료: `frontend` lint 실패(`Layout.jsx`의 `motion` 사용) 해결.
- 완료: `biolinker` 업로드 API에서 임시 파일 정리(`finally`) 보강.
- 완료: `/health` 엔드포인트를 `degraded` 상태 반환 가능하도록 보강.
- 완료: 프런트 빌드 크래시(`Node v24 + Vite 7`) 환경 이슈 해결.

## 2. 품질 게이트 정착 ✅ 완료
목표: 로컬/CI에서 동일 기준으로 품질을 보장한다.

- 완료: Python 테스트 러너(`pytest`) 및 스모크 테스트 추가.
- 완료: 프런트 빌드 환경 Node LTS 기준 통일 및 CI 워크플로우 추가.
- 완료: 프런트 번들 예산 검사(`npm run check:bundle`) 및 CI 자동 게이트 추가.

## 3. Freemium 수익 모델 인프라 ✅ 완료 (2026-03-17)
목표: SaaS 구독 기반 수익 창출 구조를 구축한다.

- 완료: 사용자 티어 모델(`user_tier.py`) — Free/Pro($29)/Enterprise($199)
- 완료: 티어별 월간 사용량 한도(TIER_LIMITS) 및 Rate Limit 설정
- 완료: 사용량 추적 미들웨어(`usage_middleware.py`) — Firestore 연동
- 완료: Subscription 라우터(`subscription.py`) — pricing/usage/upgrade 엔드포인트
- 완료: RFP 라우터에 사용량 가드 적용(`/analyze`, `/match/rfp`, `/proposal/generate`)
- 진행중: Stripe Checkout 실제 연동 (webhook stub 준비됨)

## 4. 클라우드 배포 준비 ✅ 완료 (2026-03-17)
목표: 로컬 의존 탈피, 프로덕션 배포 가능 상태로 전환한다.

- 완료: BioLinker Dockerfile 프로덕션 강화 (health check, non-root user)
- 완료: Backend Dockerfile 신규 추가
- 완료: Railway 배포 설정(`railway.json`)
- 완료: Frontend Vercel 배포 설정(`vercel.json`, SPA + API proxy)
- 완료: 프로덕션 환경변수 템플릿(`.env.production.example`)

## 5. 다음 단계 (TODO)
- [ ] Stripe Checkout Session 생성 + Webhook 실제 연동
- [ ] Landing Page (Pricing 포함) 프론트엔드 컴포넌트 구축
- [ ] SEO 메타데이터 및 `index.html` 최적화
- [ ] Vercel + Railway 실제 배포 및 도메인 연결
- [ ] 한국 바이오 VC 50개사 DB 크롤링 활성화
- [ ] Polygon Amoy Testnet에 DeSciToken 배포
