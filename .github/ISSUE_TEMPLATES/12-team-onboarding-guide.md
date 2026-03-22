# Create Team Onboarding Guide

**Labels**: `documentation`, `team`
**Priority**: 📝 **Documentation** - 1개월 내

---

## Description

새 팀원이 1시간 내에 로컬 개발 환경을 셋업할 수 있도록 가이드를 작성합니다.

---

## Content Outline

### 1. 필수 도구 설치 (10분)
- Python 3.13.3 (pyenv)
- Node.js 22.12.0+ (nvm)
- Docker Desktop
- Git
- VS Code (권장 확장 프로그램)

### 2. 환경 변수 설정 (5분)
- `.env` 파일 생성
- API 키 입력 가이드
- Firebase 서비스 계정 설정

### 3. Docker Compose 실행 (5분)
- `docker compose up`
- 서비스 health check 확인
- 로컬 브라우저 테스트

### 4. Pre-commit Hooks 설치 (5분)
- `pre-commit install`
- 첫 커밋 테스트

### 5. 첫 PR 제출 가이드 (30분)
- 브랜치 전략 (main, feature/*, bugfix/*)
- 커밋 메시지 규칙
- PR 템플릿
- Code Review 프로세스

### 6. 트러블슈팅 FAQ (참고용)
- "Docker가 시작되지 않아요"
- "API 키 오류가 나요"
- "Pre-commit이 차단했어요"

---

## Tasks

- [ ] `docs/ONBOARDING.md` 파일 생성
- [ ] 스크린샷 추가 (각 단계마다)
- [ ] 비디오 튜토리얼 녹화 (선택)
- [ ] 팀원 3명에게 테스트 요청
- [ ] 피드백 반영

---

## Acceptance Criteria

- ✅ 신규 팀원이 1시간 내에 로컬 환경 셋업 완료
- ✅ 첫 PR 제출까지 가이드됨
- ✅ 트러블슈팅 FAQ가 포함됨

---

**Estimated Time**: 2-3일
