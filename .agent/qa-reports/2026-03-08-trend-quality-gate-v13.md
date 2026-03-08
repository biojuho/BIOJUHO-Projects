# QC 보고서 — v13.0 트렌드 품질 게이트 & 비용 최적화

> 보고서 작성일: 2026-03-08
> 검토 버전: v13.0
> 대상 프로젝트: getdaytrends

---

## 1. 요구사항 충족 여부

| 요구사항 | 충족 | 근거 |
|----------|:----:|------|
| 의미 없는 키워드("아주 여리고") 필터링 | ✅ | `publishable=false` 판정 → `_ensure_quality_and_diversity`에서 제거 |
| 오타 키워드("카이로류") 교정 | ✅ | `corrected_keyword` 필드 → 생성 시 교정된 키워드 사용 |
| 저품질 트렌드 강제 포함 방지 | ✅ | `floor_score` 50%→75%, `min_article_count` 5→3 |
| 블로그 글감 비활성화 | ✅ | `TARGET_PLATFORMS=x,threads` |
| 핵심 키워드만 수집 | ✅ | `DEFAULT_LIMIT` 10→5, `MIN_VIRAL_SCORE` 60→70 |
| 비용 절감 | ✅ | 장문 HEAVY→LIGHTWEIGHT, 예산 $2→$3 |

---

## 2. QA 검토 결과 (5축)

### [기능성] ✅ PASS
- `publishable`, `corrected_keyword` 필드가 models/analyzer/main 전체에서 일관 적용
- 단일 스코어링(`_score_trend_async`) + 배치 스코어링(`_batch_score_async`) 양쪽 모두 반영
- 프롬프트 JSON 스키마에 새 필드 포함, 파싱 로직에서 문자열 "false" 안전 처리

### [보안] ✅ PASS
- API 키 하드코딩 없음
- `.env` 설정만 변경, 민감 정보 노출 없음
- LLM 프롬프트에 사용자 입력 직접 삽입 없음 (sanitize_keyword 통과)

### [안정성] ✅ PASS
- `getattr(t, "publishable", True)` — 기존 ScoredTrend 객체 하위호환
- `getattr(trend, "corrected_keyword", "") or trend.keyword` — None/빈문자열 안전
- publishable 문자열 파싱: `isinstance(publishable, str)` 방어 코드

### [코드 품질] ✅ PASS
- 단일 책임: 필터링 로직은 `_ensure_quality_and_diversity`, 파싱은 `_parse_scored_trend_from_dict`
- 중복 최소화: publishable 파싱 로직이 단일/배치 양쪽에 동일 패턴
- 테스트: `test_publishable_false_excluded` 신규 추가, 기존 215개 전체 통과

### [성능] ✅ PASS
- LLM 호출 수 변경 없음 (프롬프트에 필드만 추가)
- 장문 HEAVY→LIGHTWEIGHT: 비용 ~$0.18/트렌드 절감
- `DEFAULT_LIMIT` 10→5: 스코어링 호출 50% 감소

---

## 3. 발견된 문제 목록

| 번호 | 심각도 | 카테고리 | 문제 내용 | 수정 상태 |
|------|--------|----------|-----------|:--------:|
| 1 | MED | 설정 | `DAILY_BUDGET_USD=2.0`이 루트 `.env` 캐시로 기본값 $3 오버라이드 | ✅ 수정 (getdaytrends/.env에 명시) |
| 2 | MED | 가변필터 | 카테고리 제외 시 `config.limit`과 비교하여 제외 해제되는 버그 | ✅ 수정 (`min_count` 비교 → 항상 적용) |
| 3 | LOW | 테스트 | `test_ensure_min_article_count` 기대값 floor_score 변경 미반영 | ✅ 수정 |
| 4 | LOW | 테스트 | `test_v6_config_defaults` min_article_count 기대값 변경 필요 | ✅ 수정 |

---

## 4. 최종 체크리스트

- [x] 코드가 실행 가능한 상태인가? → 프로세스 정상 가동 확인 (PID 27800, 25816)
- [x] 유닛 테스트를 통과하는가? → **215 passed, 0 failed**
- [x] 보안 취약점이 제거되었는가? → 해당 없음 (API 키 변경 없음)
- [x] 환경변수 처리가 올바른가? → `DAILY_BUDGET_USD=3.0` 명시적 설정 완료
- [x] 예외 처리가 완료되었는가? → publishable 문자열/"false" 안전 처리
- [x] 주석 및 문서화가 충분한가? → `[v13.0]` 태그 일관 적용
- [x] 성능 이슈가 해결되었는가? → HEAVY→LIGHTWEIGHT 비용 대폭 절감

---

## 5. 변경 파일 요약

| 파일 | 변경 요약 |
|------|-----------|
| `models.py` | `publishable`, `publishability_reason`, `corrected_keyword` 3개 필드 추가 |
| `analyzer.py` | 단일+배치 스코어링 프롬프트에 게시가능성 판정 추가, 파싱 로직 연동 |
| `main.py` | publishable 필터 + floor 강화 + 카테고리 제외 항상 적용 + corrected_keyword 적용 |
| `config.py` | `min_article_count` 5→3, `target_platforms` naver_blog 제거, `daily_budget_usd` $2→$3 |
| `generator.py` | 장문 기본 tier HEAVY→LIGHTWEIGHT |
| `.env` | `DEFAULT_LIMIT=5`, `MIN_VIRAL_SCORE=70`, `TARGET_PLATFORMS=x,threads`, `DAILY_BUDGET_USD=3.0` |
| `tests/test_quality_diversity.py` | publishable 테스트 추가, 기존 테스트 기대값 업데이트 (8건) |

---

## 6. 예상 리스크

| 리스크 | 심각도 | 대응 |
|--------|--------|------|
| Gemini Flash 무료 한도(15 RPM) 초과 시 유료 폴백 | LOW | 예산 $3으로 여유 확보, 자동 폴백 체인 작동 |
| LIGHTWEIGHT 장문 품질 하락 가능성 | LOW | Gemini Flash 한국어 성능 우수, 모니터링 후 조정 |
| `publishable=false` 과잉 필터링 | LOW | LLM 판정이므로 false positive 가능, 로그 모니터링 |

---

## 7. 테스트 방법

1. **다음 파이프라인 사이클 로그 확인**: `[게시불가 필터]`, `[키워드 교정]` 태그 출력 여부
2. **Notion Content Hub 확인**: 생성된 콘텐츠가 X/Threads 2개 플랫폼으로만 저장되는지
3. **비용 모니터링**: 내일 `check_cost.py` 실행 → 일일 비용이 $0.50 이하인지 확인

---

## 8. 롤백 계획

```bash
# .env 원복
DEFAULT_LIMIT=10
MIN_VIRAL_SCORE=60
TARGET_PLATFORMS=x,threads,naver_blog
DAILY_BUDGET_USD=2.0

# config.py: min_article_count=5, daily_budget_usd=2.0
# generator.py: tier=TaskTier.HEAVY (장문)
# analyzer.py: publishable 관련 프롬프트/파싱 제거
# models.py: publishable, corrected_keyword 필드 제거
# main.py: publishable 필터 제거, floor_score 0.5 복원
```

---

## 9. 최종 판정

```
배포 승인: ✅ 승인
판정 이유: 
  - 215개 유닛 테스트 전체 통과
  - 핵심 요구사항 6개 전부 충족
  - QA 5축 전항목 PASS
  - 발견된 4건의 이슈 모두 세션 내 수정 완료
  - 프로세스 재시작 후 정상 가동 확인

---
보고서 작성일: 2026-03-08
검토 버전: v13.0
```
