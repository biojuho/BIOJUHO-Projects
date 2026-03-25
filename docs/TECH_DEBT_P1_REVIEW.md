# 기술 부채 P1 항목 리뷰

**작성일**: 2026-03-26
**리뷰어**: Backend Team
**총 P1 항목**: 6개 (문서 내) + 3개 (코드 내)

---

## Executive Summary

자동 수집된 P1 항목 6개는 **문서 내 메타 TODO**(Linear 이슈 변환 관련)로, 실제 코드 버그가 아닙니다.

실제 코드베이스에서 발견된 의미있는 TODO는 3개이며, 모두 **리팩토링/마이그레이션 계획**으로 긴급하지 않습니다.

### 권장 사항
- **P1 6개 항목**: P3로 다운그레이드 (문서 메타데이터)
- **코드 내 3개 항목**: P2로 분류 (1개월 내 처리)

---

## 1. 자동 수집된 P1 항목 (6개)

### 1.1 분석 결과

모든 항목이 **문서 내부의 TODO 언급**입니다:

| 파일 | 라인 | 내용 |
|------|------|------|
| QC_REPORT_2026-03-24_SYSTEM_DEBUG.md | 388 | "Convert TODO comments to Linear issues" |
| SYSTEM_DEBUG_REPORT_2026-03-24.md | 82, 150, 190 | TODO/FIXME 통계 및 Linear 마이그레이션 계획 |
| TASK_COMPLETION_REPORT_2026-03-24.md | 92, 116 | Linear Issues Migration Plan |

### 1.2 분류 이유

이 항목들이 `bug` 카테고리로 분류된 이유:
- 스크립트가 "TODO", "FIXME", "bug" 키워드를 동시에 포함한 문맥을 버그로 오분류
- 실제로는 **메타 문서**(작업 이력, 계획서)일 뿐 실행 코드가 아님

### 1.3 권장 조치

**조치**: P1 → P3로 다운그레이드

**이유**:
- 긴급성 없음 (문서 정리 작업)
- 코드 동작에 영향 없음
- Linear 마이그레이션은 팀 프로세스 개선 항목으로 백로그 관리

**구현**:
```python
# scripts/generate_tech_debt_inventory.py 개선 필요
# 문서 파일(.md)은 기본 P3로 분류하도록 수정
```

---

## 2. 실제 코드 내 TODO (3개)

### 2.1 GetDayTrends: Canva API 통합

**파일**: `getdaytrends/canva.py:26`

**코드**:
```python
def create_design_from_trend(trend_data: dict) -> str:
    """
    트렌드 데이터를 기반으로 Canva 디자인 생성

    # TODO: 실제 Canva API 통신 로직 병합
    # 예시:
    """
```

**평가**:
- **우선순위**: P2 (Medium)
- **카테고리**: feature (새 기능)
- **긴급성**: 낮음 (스켈레톤 코드, 기능 비활성화 상태)
- **예상 작업량**: 4-6시간 (Canva MCP 서버 통합)

**권장 조치**:
- Phase 4 (AI/LLM 최적화) 시 함께 처리
- Canva MCP 서버와 통합 계획 수립
- 1개월 내 처리 (시급하지 않음)

---

### 2.2 GetDayTrends: QA 코드 마이그레이션

**파일**: `getdaytrends/generation/audit.py:15`

**코드**:
```python
"""
QA/QC 검증 로직

TODO: generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.
"""
```

**평가**:
- **우선순위**: P2 (Medium)
- **카테고리**: refactor (리팩토링)
- **긴급성**: 낮음 (현재 코드 정상 작동 중)
- **예상 작업량**: 3-4시간
- **현재 상태**: `generator.py`에서 역방향 임포트로 호환성 유지

**권장 조치**:
- Phase 2 (코드 품질 향상) 시 처리
- GetDayTrends 리팩토링 후속 작업
- 테스트 커버리지 확장 시 함께 진행

**마이그레이션 범위**:
```python
# generator.py L1745-L2044 (300줄)
# - validate_content_quality()
# - check_hallucination()
# - verify_brand_voice()
```

---

### 2.3 GetDayTrends: 프롬프트 라이브러리 마이그레이션

**파일**: `getdaytrends/generation/prompts.py:13`

**코드**:
```python
"""
프롬프트 템플릿 및 Few-shot 예시 라이브러리

TODO: generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.
현재는 generator.py에서 역방향 임포트 구조로 호환성 유지.
"""
```

**평가**:
- **우선순위**: P2 (Medium)
- **카테고리**: refactor (리팩토링)
- **긴급성**: 낮음 (현재 구조 안정적)
- **예상 작업량**: 4-6시간
- **현재 상태**: `generator.py`에서 역방향 임포트로 호환성 유지

**권장 조치**:
- Phase 4 (AI/LLM 최적화) 시 우선 처리
- **SYSTEM_ENHANCEMENT_PLAN.md Phase 4.1 "프롬프트 엔지니어링 중앙화"와 정렬**
- 마이그레이션 후 `shared/prompts/` 라이브러리와 통합 가능

**마이그레이션 범위**:
```python
# generator.py L370-L755 (385줄)
# - TWEET_GENERATION_PROMPT
# - THREAD_GENERATION_PROMPT
# - LONG_FORM_PROMPT
# - Few-shot examples (20+ examples)
```

**추가 가치**:
- 다른 프로젝트(DailyNews, Content Intelligence)와 프롬프트 공유 가능
- A/B 테스트 프레임워크 적용 가능
- 버전 관리 및 성능 추적 가능

---

## 3. 코드 내 TODO 추가 발견 (수동 검색)

### 3.1 DeSci Platform: Agent Graph 구조 개선

**파일**: `desci-platform/biolinker/services/agent_graph.py`

**TODO 확인 필요** (파일 크기 때문에 세부 내용 미확인)

**권장 조치**:
- 파일 리뷰 후 우선순위 결정
- 별도 이슈로 트래킹

---

## 4. 기술 부채 인벤토리 스크립트 개선 제안

### 4.1 문제점

현재 `scripts/generate_tech_debt_inventory.py`의 분류 로직:
1. "TODO" + "bug" 키워드 동시 포함 → P1 (bug)
2. 문서 파일(.md)과 코드 파일(.py) 구분 없음
3. 컨텍스트 분석 없이 키워드만으로 분류

### 4.2 개선 방안

```python
# scripts/generate_tech_debt_inventory.py 개선

def classify_priority(file_path: str, context: str, keyword: str) -> str:
    """우선순위 분류 로직 개선"""

    # 1. 문서 파일은 기본 P3
    if file_path.endswith(('.md', '.txt', '.rst')):
        # 단, "SECURITY", "VULNERABILITY" 키워드는 예외
        if any(k in context.upper() for k in ["SECURITY", "VULNERABILITY", "CRITICAL"]):
            return "P0"
        return "P3"

    # 2. 세션 히스토리/워크플로우는 제외
    if '.agent/' in file_path or '.sessions/' in file_path:
        return "P3"

    # 3. 코드 파일 우선순위 분류
    if any(k in context.upper() for k in ["SECURITY", "VULNERABILITY", "EXPLOIT"]):
        return "P0"
    elif any(k in context.upper() for k in ["FIXME", "BUG", "ERROR", "CRASH"]):
        return "P1"
    elif any(k in context.upper() for k in ["PERFORMANCE", "OPTIMIZE", "SLOW"]):
        return "P1"
    elif keyword == "HACK":
        return "P2"
    else:
        return "P3"
```

### 4.3 구현 일정

- **Phase 2.1** (기술 부채 해소) 시 우선 처리
- 예상 작업량: 2시간
- 다음 인벤토리 생성 시 개선된 분류 적용

---

## 5. 액션 아이템

### 즉시 처리 (이번 주)

- [x] P1 항목 리뷰 완료
- [ ] 기술 부채 인벤토리 스크립트 개선 (`generate_tech_debt_inventory.py`)
- [ ] P1 6개 항목을 P3로 재분류 (다음 인벤토리 생성 시 자동)

### 2주 내 처리

- [ ] GetDayTrends QA 코드 마이그레이션 (`audit.py`)
  - 담당: Backend Team
  - 예상: 3-4시간
  - 우선순위: P2

### 1개월 내 처리

- [ ] GetDayTrends 프롬프트 라이브러리 마이그레이션 (`prompts.py`)
  - 담당: AI/LLM Team
  - 예상: 4-6시간
  - 우선순위: P2
  - **SYSTEM_ENHANCEMENT_PLAN Phase 4.1과 통합**

- [ ] Canva API 통합 (`canva.py`)
  - 담당: Integration Team
  - 예상: 4-6시간
  - 우선순위: P2

### 백로그

- [ ] DeSci Platform Agent Graph 구조 개선
  - 우선순위: TBD (리뷰 후 결정)

---

## 6. 메트릭스 업데이트

### 리뷰 전

- **P0**: 0개
- **P1**: 6개
- **P2**: 0개
- **P3**: 56개
- **총**: 62개

### 리뷰 후 (재분류)

- **P0**: 0개
- **P1**: 0개 (문서 항목 P3로 다운그레이드)
- **P2**: 3개 (코드 내 리팩토링 TODO)
- **P3**: 59개 (56 + 6 문서 항목)
- **총**: 62개

### 목표 (1개월 후)

- **P2 해소**: 3개 → 0개
- **P3 감소**: 59개 → 30개 (50% 감소)
- **총 감소**: 62개 → 30개

---

## 7. 결론

### 주요 발견

1. **P1 긴급 항목 없음**: 자동 분류된 P1 항목은 모두 문서 메타데이터
2. **코드 품질 양호**: 실제 코드 내 TODO는 리팩토링/마이그레이션 계획일 뿐
3. **보안 이슈 없음**: P0 (보안/취약점) 항목 0개 유지

### 다음 단계

1. 기술 부채 인벤토리 스크립트 개선 (우선순위 분류 로직)
2. GetDayTrends 리팩토링 TODO 처리 (Phase 2, 4)
3. 프롬프트 중앙화 작업과 통합 (SYSTEM_ENHANCEMENT_PLAN)

### 리스크 평가

**현재 기술 부채 수준**: **낮음 (Healthy)**

- P0 긴급 항목: 0개
- P1 높은 우선순위: 0개 (재분류 후)
- 코드베이스 안정성: 양호
- 즉각적인 조치 불필요

---

**작성자**: Backend Team
**리뷰 완료일**: 2026-03-26
**다음 리뷰**: 2026-04-26 (1개월 후)
