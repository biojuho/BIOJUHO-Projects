# ADR-0003: 모니터링 & 지식 관리 체계 도입

- **상태**: 승인됨
- **날짜**: 2026-03-08
- **의사결정자**: biojuho

## 컨텍스트

프로젝트가 7개로 증가하면서 장애 대응, 성과 측정, 지식 공유에 체계가 필요합니다.
현재는 수동으로 상태를 확인하고, 장애 기록이 체계화되어 있지 않습니다.

## 결정

1. **헬스체크 스크립트** (`scripts/healthcheck.py`)
   - 6개 프로젝트 파일 존재/Git 상태/env 점검
   - Discord/Slack Webhook 알림 옵션

2. **DORA Metrics** (`scripts/dora_metrics.py`)
   - Git 로그 기반 3가지 지표(배포 빈도, 리드 타임, 변경 실패율) 자동 측정
   - Elite/High/Medium/Low 4단계 등급 판정

3. **Postmortem 템플릿** (`docs/postmortem-template.md`)
   - Blameless 원칙, 5-Whys 근본 원인 분석
   - Action Items 추적 테이블

4. **운영 Runbook** (`docs/runbook.md`)
   - 일상 점검 / 장애 대응 / 배포 절차 / 백업 가이드

## 대안

1. **상용 모니터링 (Datadog, PagerDuty)**: 현 규모에 과도한 비용
2. **Notion만으로 관리**: API 한계로 자동화 어려움
3. **GitHub Issues만 사용**: 장애 기록으로는 구조화 부족

## 결과

- 프로젝트 상태를 한 명령어로 전체 파악 가능
- 성과를 정량적으로 추적하여 개선점 발견
- 장애 발생 시 표준 절차에 따라 대응 & 기록
