# 프로젝트 운영 지식 목차 (docs/knowledge)

- 작성일: 2026-06-11
- 작성 방식: Claude 기획 — 주제별 웹 조사 → 핵심 주장 교차검증(출처 직접 확인) → 교정 반영 후 문서화
- 용도: JooPark Workspace를 운영(배포·데이터 안전·품질·연동·에이전트 협업)하는 데 필요한 지식의 정본. 앱 위키 "프로젝트 운영" 카테고리로도 노출한다.

| # | 문서 | 한 줄 요약 | 출처 수 |
|---|---|---|---|
| 1 | [GitHub Pages를 Actions로 배포하기](github-pages-actions-deploy.md) | 배포 3단계(configure→upload→deploy)와 필수 permissions, "워크플로 파일을 푸시 안 해서 디스패치 불가"라는 우리 차단의 원인과 해제 절차 | 10 |
| 2 | [localStorage만 쓰는 앱의 데이터 안전](local-first-data-safety.md) | 오리진당 약 5MiB 한계, Safari 7일 규칙·eviction 리스크, persist() 영속 요청, 스키마 버저닝과 백업 UX | 10 |
| 3 | [PWA 서비스워커 운영](pwa-offline-operations.md) | SW 업데이트 수명주기(waiting 함정), 캐시 전략 선택, iOS 제약, 첫 배포 전 "구버전 고착" 예방 체크리스트 | 13 |
| 4 | [바닐라 JS SPA 품질 게이트](vanilla-spa-quality-gates.md) | 순수 함수 테스트 + 실브라우저 스모크 + 벤더 점검의 3층 구조, WCAG 2.2 타깃 크기(24px 최소/44px 권장), 시각 회귀 도입법 | 14 |
| 5 | [서버 없는 정적 사이트에서 실데이터 가져오기](static-site-data-sync.md) | OAuth·비밀 URL은 정적 사이트에서 불가 → .ics/.csv 파일 업로드가 현실해, ical.js 파싱·한국어 인코딩·출처 배지 | 10 |
| 6 | [LLM 에이전트 자율 루프 가드레일](llm-agent-loop-guardrails.md) | 우리 실제 사고(메타 루프 310회) 분석과 처방 — 정지 조건, 반복 예산, 에스컬레이션 트리거, 커밋 케이던스 | 7 |

## 문서가 뒷받침하는 실행 플랜

- 전체 플랜: `docs/improvement-plan-2026-06.md`
- #1 → handoffs/0001 (런치 차단 해제), #6 → handoffs/0002 (루프 가드레일, 반영 완료), #4 → handoffs/0005 (품질 게이트 승격, 반영 완료)
- #2·#3·#5 → 백로그(데이터 안전 강화, SW 업데이트 프롬프트, .ics/.csv 가져오기) 기획 시 1차 자료
