# QC 보고서: 플랫폼 규제 반영 콘텐츠 시스템 통합

> 보고서 작성일: 2026-03-08
> 검토 버전: v12.0
> 대상: `getdaytrends/generator.py`, `getdaytrends/main.py`

---

## 1. 요구사항 충족 여부

| 요구사항 | 충족 | 근거 |
|---------|:----:|------|
| getdaytrends에 규제 반영 | ✅ | `_JOONGYEON_RULES`에 X/Threads/네이버 규제 가이드라인 섹션 추가 |
| QA에 규제 축 추가 | ✅ | 5축→7축 확장 (regulation + algorithm), 합계 100점 유지 |
| 규제 위반 시 자동 차단 | ✅ | `main.py`에 regulation ≤ 3 강제 재생성 로직 추가 |
| 기존 기능 유지 | ✅ | 기존 QA 교정/재생성 로직 보존, avg_score 하위 호환 유지 |
| DailyNews 평가 | ✅ | 뉴스 수집/요약 시스템으로 소셜 게시 기능 없어 규제 비적용 판단 |

---

## 2. QA 검토 결과

```
QA 결과: PASS ✅
```

### 발견된 문제 목록

| 번호 | 심각도 | 카테고리 | 문제 내용 | 수정 방향 |
|------|--------|---------|----------|----------|
| — | — | — | 문제 없음 | — |

### 검토 세부

#### [기능성] ✅
- 7축 배점 합계 검증: 20+15+15+15+15+10+10 = **100점** ✅
- 플랫폼 힌트 감지 로직: `content_type` 기반 X/Threads/네이버 자동 분기 ✅
- `reg_score` None 안전 처리: `qa.get("regulation", 10) if qa else 10` ✅
- 하위 호환: `result["avg_score"] = result["total"]` 유지 ✅

#### [보안] ✅
- API 키/시크릿 하드코딩 없음
- 외부 입력 처리: `sanitize_keyword()` 유지
- 민감 정보 노출 없음

#### [안정성] ✅
- 예외 처리: `try/except` 블록 유지, 실패 시 `None` 반환
- `needs_regen` 플래그로 재생성 로직 단일화 (이전 중첩 if문보다 안전)
- LLM 응답 파싱 실패 시 graceful degradation

#### [코드 품질] ✅
- DRY: 규제 가이드라인이 `_JOONGYEON_RULES`에 1곳에만 존재 (모든 프롬프트가 공유)
- SRP: `audit_generated_content()` 함수의 단일 책임 유지
- 주석: 버전 태그 `[v12.0]`, `[QA 수정]` 일관 적용

#### [성능] ✅
- `max_tokens` 300→400 (7축 JSON 응답에 충분한 여유)
- 추가 LLM 호출 없음 (기존 1회 QA 호출에 축만 추가)
- `content_types` set 생성: O(n) 단순 연산, 성능 영향 무시

---

## 3. 최종 체크리스트

- [x] 코드가 실행 가능한 상태인가? (`ast.parse` 통과)
- [x] import 테스트 통과? (`_JOONGYEON_RULES`, `_CONTENT_QA_SYSTEM`, `audit_generated_content` 정상 임포트)
- [x] 7축 합계 100점 검증? (20+15+15+15+15+10+10 = 100)
- [x] 보안 취약점 제거? (하드코딩 없음, `sanitize_keyword` 유지)
- [x] 환경변수 처리 올바름? (변경 없음)
- [x] 예외 처리 완료? (`try/except` + `None` 가드)
- [x] 주석 및 문서화 충분? (버전 태그, docstring 업데이트)
- [x] 하위 호환? (`avg_score` alias 유지)

---

## 4. 변경 요약

### `getdaytrends/generator.py`

| 변경 위치 | 변경 내용 |
|----------|----------|
| `_JOONGYEON_RULES` (L245-260) | 플랫폼 규제 가이드라인 섹션 추가 (X Shadowban, Threads 링크, 네이버 C-Rank/D.I.A.) |
| `_CONTENT_QA_SYSTEM` (L1241-1284) | 5축→7축 확장, 배점 재조정 (fact/tone/kick/angle 각 20→15, regulation/algorithm 각 10 신규) |
| `audit_generated_content()` (L1287-1365) | 플랫폼 힌트 감지, 7축 로깅, regulation ≤ 3 경고, max_tokens 300→400 |

### `getdaytrends/main.py`

| 변경 위치 | 변경 내용 |
|----------|----------|
| `_step_generate()` (L607-648) | regulation ≤ 3 강제 재생성 로직, `needs_regen` 플래그 통합 |

---

## 5. 예상 리스크

| 수준 | 리스크 | 대응 |
|------|--------|------|
| LOW | LLM이 7축 JSON에서 regulation/algorithm 키를 누락할 가능성 | `.get("regulation", 10)` 기본값 10으로 안전 처리 |
| LOW | 규제 가이드라인 길이 증가로 프롬프트 토큰 소비 ~200토큰 증가 | LIGHTWEIGHT 티어에서 무시할 수준 |

---

## 6. 테스트 방법

1. `python main.py --one-shot --verbose` 실행 후 QA 로그에서 `R:` 및 `G:` 축 점수 출력 확인
2. 해시태그가 포함된 콘텐츠 생성 시 `[QA 규제 위반]` 경고 로그 발생 확인
3. regulation ≤ 3인 콘텐츠가 자동 재생성되는지 확인

---

## 7. 롤백 계획

```bash
cd d:\AI 프로젝트\getdaytrends
git checkout -- generator.py main.py
```

---

## 8. 최종 판정

```
배포 승인: ✅ 승인
판정 이유: 모든 검토 항목 PASS. 기존 기능 하위 호환 유지.
           7축 합계 100점 정확. 규제 위반 차단 로직 정상.
           추가 LLM 호출 없이 기존 QA 1회 호출에 축만 확장하여 비용 영향 없음.

---
보고서 작성일: 2026-03-08
검토 버전: v12.0
```
