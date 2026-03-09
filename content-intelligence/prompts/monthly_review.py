"""보너스 — 월간 회고 & 시스템 업데이트 프롬프트."""

MONTHLY_REVIEW_SYSTEM = """\
너는 콘텐츠 전략 컨설턴트야.
데이터에 기반한 정량적 분석과 실행 가능한 개선안을 제시해.
칭찬에 시간 쓰지 말고, 실패 원인과 개선 방향에 집중해."""


def build_monthly_review_prompt(
    content_performance: str,
    used_keywords: str,
    issues: str,
    qa_stats: str,
) -> str:
    """월간 회고 프롬프트를 생성한다."""
    return f"""\
[입력]
- 이번 달 발행 콘텐츠 목록과 성과 지표:
{content_performance}

- 이번 달 사용된 트렌드 키워드:
{used_keywords}

- 발생 이슈 (도달률 하락, 제재 등):
{issues}

- QA 검증 결과 통계:
{qa_stats}

[작업]
1. 성과 분석
   - 효과적이었던 트렌드 반영 사례 Top 3 (구체적 콘텐츠 + 이유)
   - 실패한 사례 Bottom 3 (구체적 콘텐츠 + 원인 + 개선 방향)
   - 플랫폼별 평균 QA 점수 비교표

2. 규제 리스크 리뷰
   - 놓친 정책 변화나 예상 못한 페널티
   - 알고리즘 변경으로 인한 도달률 영향 분석
   - 다음 달 대비 필요한 규제 업데이트

3. 다음 달 전략 제안
   - 키워드 방향: 상승세 키워드 3개, 하락세 키워드 3개
   - 포맷 실험 제안: 시도할 새로운 콘텐츠 형식 2개
   - 플랫폼별 톤/전략 미세 조정

4. 시스템 개선점
   - 프롬프트 수정/추가 제안
   - 수집 소스 변경 제안
   - QA 기준 조정 제안

■ 출력 형식 — 반드시 아래 JSON 구조로 응답해줘:
```json
{{
  "top_performers": [
    {{"content": "설명", "reason": "이유", "platform": "x"}}
  ],
  "bottom_performers": [
    {{"content": "설명", "reason": "이유", "improvement": "개선방향"}}
  ],
  "regulation_issues": ["이슈 1", "이슈 2"],
  "next_month_strategy": ["전략 1", "전략 2", "전략 3"],
  "system_improvements": ["개선 1", "개선 2"]
}}
```

반드시 JSON만 응답하고, 다른 텍스트는 포함하지 마."""
