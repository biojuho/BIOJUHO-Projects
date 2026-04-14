# 학습된 교훈 (LESSONS)

> 크로스 세션으로 축적되는 교훈. 5회 이상 반복되거나 같은 유형의 문제가 2회+ 발생 시 기록.
> 150줄 (next-actions.md 합산) 이내 유지. 오래된 항목은 정리 제안.

## 반복 패턴

- **Notifier API 계약 불일치**: `send_alert` vs `send_error`, sync vs async 차이가 런타임 장애로 이어짐 → 공통 모듈 사용 시 반드시 실제 클래스 시그니처 확인 (2026-04-14)
- **API 호출부 에러 핸들링 누락**: 새 API 함수 작성 시 try/catch를 기본 템플릿에 포함 (2026-04-14)
- **gitleaks 시크릿 노출**: 상세 로깅(harness_audit 등) 시 Redaction 로직을 최상단 모듈에서 수행 (2026-04-14)

## 사용자 선호

- 코드: Python 함수형 스타일, 비동기 우선 (async/await)
- 에러 메시지: 한국어 구어체
- 워크플로우: 4단계 QA/QC 필수 적용 (코드 변경 시)
- 커밋 메시지: `[Project] feat/fix/refactor: 한 줄 설명` 형식

## 아키텍처 교훈

- **Shift-Left QA**: 품질 검사를 파이프라인 끝이 아니라 생성 직후로 전진 배치하면 LLM intervention이 가능해짐 (2026-04-14)
- **듀얼 모드 DB**: PG/SQLite 자동 절체 아키텍처가 로컬 개발과 클라우드 운영을 동시 지원 (2026-04-14)
