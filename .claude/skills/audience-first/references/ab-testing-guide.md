# A/B Testing Guide — Audience-First Framework

> **목적**: 청중 중심으로 A/B 테스트를 설계하고 실행하는 실전 가이드
> **대상**: DailyNews, GetDayTrends, DeSci, AgriGuard 등 모든 프로젝트
> **Version**: 1.0.0

---

## 1. Audience-First A/B Testing이란?

**전통적 A/B 테스트** (기술 중심):
```
"버전 A와 B 중 어느 게 더 빠른가?"
"어느 쪽이 에러가 적은가?"
→ 기술 지표 중심, 사용자 행동 무시
```

**Audience-First A/B 테스트** (청중 중심):
```
"타깃 청중이 어느 버전에서 더 목표를 달성하는가?"
"Persona의 Pain Point를 더 잘 해결하는 쪽은?"
→ 사용자 행동/성과 중심, 기술은 수단
```

---

## 2. 5-Step Framework

### Step 0: Audience Profile 먼저 (Before Everything)

**테스트 시작 전 필수 확인**:

```yaml
□ 이 기능/콘텐츠의 타깃 청중은 누구인가?
□ 그들의 핵심 Goal은?
□ Pain Point는?
□ 성공했다는 기준은? (청중 관점에서)
```

**예시 (DailyNews Economy_KR)**:

```yaml
Audience: 한국 개인 투자자 (2040세대)
Goal: 아침 5분 안에 핵심 경제 동향 파악
Pain Point: 뉴스 홍수, 시간 부족, 실생활 무관
Success Criterion: "이 정보로 오늘 투자 판단에 도움 됨"
```

❌ **Without Audience**: "OLD vs NEW 파이프라인 중 어느 게 나아?"
✅ **With Audience**: "2040 투자자가 5분 안에 실용적 인사이트 얻기에 어느 쪽이 효과적인가?"

---

### Step 1: Hypothesis 수립

**Format**:
> "[타깃 청중]에게 [Version B]는 [Version A] 대비 [Metric]을 [X%] 개선할 것이다. 왜냐하면 [Reason]."

**Good Examples**:

```
✅ "2040 투자자에게 새 3-Stage 파이프라인은 기존 대비 인게이지먼트를 +15% 개선할 것이다.
   왜냐하면 구체적 숫자와 실생활 영향을 명시하여 행동 유도가 강하기 때문."

✅ "콘텐츠 크리에이터에게 멀티소스 스코어링은 단일 소스 대비 바이럴 예측 정확도를 +20% 향상시킬 것이다.
   왜냐하면 X API와 Reddit 데이터가 초기 트렌드 신호를 더 빨리 포착하기 때문."
```

**Bad Examples**:

```
❌ "새 버전이 더 좋을 것이다." (주관적, 측정 불가)
❌ "A가 B보다 빠르다." (청중 무관한 기술 지표)
❌ "사용자가 더 좋아할 것이다." (모호함, "사용자"가 누구? "좋아함"을 어떻게 측정?)
```

---

### Step 2: KPI 정의 (Audience-Centric)

**원칙**:
- Primary KPI 1개 (의사결정의 핵심)
- Secondary KPI 2-4개 (보조 검증)
- 모두 **정량 측정 가능**해야 함

**KPI Selection Matrix**:

| Audience Type | Primary KPI 후보 | Secondary KPI 후보 |
|---------------|------------------|-------------------|
| **B2C 콘텐츠** | 인게이지먼트율, 읽기 시간, 공유율 | 클릭률, 재방문율, 완독률 |
| **B2C 도구** | DAU/MAU, Retention Rate | 기능 사용 빈도, 추천 의향 |
| **B2B SaaS** | 전환율, Activation Rate | Onboarding 완료율, 지불 의향 |
| **Prosumer** | 작업 완료 시간, 정확도 | 오류율, 학습 곡선 |

**Bad KPI Examples**:

```
❌ "더 예쁨" (주관적)
❌ "사용자 만족도" (측정 방법 불명확)
❌ "빌드 시간" (청중 무관, 기술 지표)
```

**Good KPI Examples (DailyNews)**:

```yaml
Primary:
  name: "predicted_engagement_score"
  calculation: "구체성(30%) + 실용성(30%) + 감정 공감(20%) + CTA(20%)"
  target: "+15점 이상 (OLD 대비)"
  rationale: "인게이지먼트는 청중이 '유용함'을 느낀 결과"

Secondary:
  - name: "content_length"
    target: "400-800자 (모바일 최적)"
    rationale: "출근길 5분 독서 가능한 길이"

  - name: "specificity_score"
    target: "최소 2개 구체적 데이터 포인트"
    rationale: "투자 판단은 구체적 숫자 필요"

  - name: "actionability"
    target: "명시적 CTA or 실생활 적용 가이드"
    rationale: "읽고 나서 '뭘 해야 하지?'라는 불안 해소"
```

---

### Step 3: Sample Size & Test Design

**최소 샘플 크기 계산**:

```
Simple Rule:
  콘텐츠 A/B 테스트: 각 버전 최소 20-30개
  기능 A/B 테스트: 각 그룹 최소 100-200명
  결제/전환 테스트: 각 그룹 최소 1000-5000명
```

**Statistical Significance**:

```python
# 예시 (DailyNews 인게이지먼트율)
from scipy import stats

engagement_a = [3.2, 2.8, 3.5, ...]  # 20개 샘플
engagement_b = [4.1, 3.9, 4.5, ...]  # 20개 샘플

t_stat, p_value = stats.ttest_ind(engagement_a, engagement_b)

if p_value < 0.05:
    print("통계적으로 유의미한 차이 (95% 신뢰도)")
else:
    print("차이 없음 (샘플 더 필요 or 실제 효과 없음)")
```

**Test Design Checklist**:

```
□ Randomization (순서 효과 제거)
□ 동일 조건 (시간대, 채널, 타깃 청중 동일)
□ Blinding (평가자가 A/B 모르게, 가능하면)
□ 중단 조건 (심각한 부정적 반응 시)
```

---

### Step 4: Evaluation (Automated + Manual)

**Automated Evaluation (Example: DailyNews)**:

```python
def evaluate_content_quality(content: str, version_name: str) -> dict:
    """
    Audience-First 기준 자동 평가
    """
    # 1. Specificity (구체적 숫자/사실)
    numbers = re.findall(r"\d+[조억만천백]?\s?[원%배달러]", content)
    specificity_score = min(100, len(numbers) * 30)

    # 2. Actionability (행동 유도)
    action_keywords = ["해야", "필요", "주목", "확인", "대비", ...]
    action_count = sum(1 for kw in action_keywords if kw in content)
    actionability_score = min(100, action_count * 25)

    # 3. Emotional Resonance (감정 공감)
    emotion_keywords = ["위험", "불안", "기회", "희망", ...]
    emotion_count = sum(1 for kw in emotion_keywords if kw in content)
    emotion_score = min(100, emotion_count * 20)

    # 4. CTA Clarity (명확한 Next Step)
    cta_phrases = ["지금", "오늘", "이번 주", "당장", ...]
    has_clear_cta = any(phrase in content for phrase in cta_phrases)
    cta_score = 100 if has_clear_cta else 30

    # Weighted Primary KPI
    primary_kpi = (
        specificity_score * 0.3 +
        actionability_score * 0.3 +
        emotion_score * 0.2 +
        cta_score * 0.2
    )

    return {
        "version": version_name,
        "primary_kpi": round(primary_kpi, 1),
        "breakdown": { ... },
    }
```

**Manual Evaluation (Qualitative)**:

```yaml
□ 실제 타깃 청중 3-5명에게 보여주기
□ "이 중 어느 쪽이 더 유용한가요?" 질문
□ "왜 그렇게 느꼈나요?" 이유 수집
□ 정량 데이터와 비교 (불일치 시 가설 재검토)
```

---

### Step 5: Decision & Learning

**Decision Rule Template**:

```
IF Primary KPI 차이 >= Target Threshold
   AND Secondary KPI 중 최소 [N]개 충족
THEN
   Version B 채택
ELSE IF Primary KPI 차이 >= 50% of Threshold
THEN
   조건부 채택 (추가 샘플로 재검증)
ELSE
   Version A 유지 OR 재설계
```

**Example (DailyNews)**:

```yaml
Target: Primary KPI +15점
Secondary: 3개 중 2개 충족

Result:
  Primary KPI 차이: +14.8점 (거의 달성)
  Secondary 통과: 3/3개

Decision: ⚠️ NEW 버전 조건부 채택
  - 샘플 20개 → 50개로 확대
  - 1주일 후 재평가
```

**Learning Documentation**:

```markdown
## Test ID: economy-kr-pipeline-v2

**Date**: 2026-03-26
**Hypothesis**: 3-Stage 파이프라인이 인게이지먼트 +15% 개선
**Result**: +14.8점 (거의 달성)

**Key Learnings**:
- ✅ 구체적 숫자 포함 시 스코어 +30점 상승 (검증됨)
- ✅ CTA 명시 시 +20점 (검증됨)
- ⚠️ 감정 공감 키워드는 과도하면 역효과 (3개 이상 시 오히려 -5점)

**Next Actions**:
- [ ] 샘플 크기 확대 (20 → 50)
- [ ] 감정 키워드 최적 개수 실험 (1-5개 범위)
- [ ] 실제 X 배포 후 실제 인게이지먼트 측정
```

---

## 3. Project-Specific Templates

### 3.1 DailyNews (콘텐츠 A/B Test)

**Script**: `automation/DailyNews/scripts/ab_test_economy_kr_v2.py`

**Usage**:
```bash
python automation/DailyNews/scripts/ab_test_economy_kr_v2.py
```

**Customization**:

```python
# 1. Audience Profile 수정
AUDIENCE_PROFILE = {
    "type": "B2C",  # or "B2B", "Prosumer"
    "target_persona": {
        "primary": "당신의 타깃 청중",
        # ...
    }
}

# 2. Hypothesis 수정
AB_TEST_HYPOTHESIS = {
    "hypothesis": "당신의 가설",
    "version_a": { "name": "OLD", ... },
    "version_b": { "name": "NEW", ... },
    "kpis": { ... }
}

# 3. Evaluation 함수 커스터마이즈
def evaluate_content_quality(content, version):
    # 당신의 평가 로직
    pass
```

---

### 3.2 GetDayTrends (알고리즘 A/B Test)

**Hypothesis Template**:
```yaml
Audience: 콘텐츠 크리에이터 (바이럴 성공률 중요)
Test: 멀티소스 스코어링 vs 단일 소스
Primary KPI: Precision@10 (Top 10 예측 정확도)
Target: +20%p
```

**Evaluation**:
```python
def evaluate_viral_prediction(scored_trends, actual_viral_trends):
    """
    바이럴 예측 정확도 평가
    """
    # Top 10 추출
    predicted_top10 = scored_trends[:10]

    # 실제 히트와 비교
    hits = len([t for t in predicted_top10 if t in actual_viral_trends])
    precision = hits / 10

    return {
        "precision_at_10": precision,
        "predicted": [t.topic for t in predicted_top10],
        "actual_hits": [t for t in predicted_top10 if t in actual_viral_trends],
    }
```

---

### 3.3 DeSci (매칭 알고리즘 A/B Test)

**Hypothesis Template**:
```yaml
Audience: 박사급 연구자 (연구비 확보 절박)
Test: 키워드 매칭 vs 벡터 유사도
Primary KPI: 연구자 만족도 (5점 척도)
Target: 3.5 → 4.5점
```

**Evaluation**:
```python
def evaluate_matching_quality(matches, researcher_feedback):
    """
    매칭 품질 평가 (연구자 피드백 기반)
    """
    satisfaction_scores = []
    for match in matches:
        score = researcher_feedback[match.id]["relevance_score"]  # 1-5
        satisfaction_scores.append(score)

    avg_satisfaction = sum(satisfaction_scores) / len(satisfaction_scores)

    return {
        "avg_satisfaction": avg_satisfaction,
        "high_quality_rate": len([s for s in satisfaction_scores if s >= 4]) / len(satisfaction_scores),
    }
```

---

### 3.4 AgriGuard (UI A/B Test)

**Hypothesis Template**:
```yaml
Audience: 식품 안전 관심 부모/주부 (QR 스캔 후 빠른 확인)
Test: 복잡한 UI vs 간소화 UI
Primary KPI: 평균 체류 시간 (초)
Target: 45초 → 90초
```

**Evaluation** (Playwright):
```javascript
test('QR Page A/B Test - Simplified UI', async ({ page }) => {
  await page.goto('/qr/product123?variant=simplified');

  const startTime = Date.now();

  // 사용자 행동 시뮬레이션
  await page.click('button#view-details');
  await page.waitForSelector('.cold-chain-status');

  const endTime = Date.now();
  const dwellTime = (endTime - startTime) / 1000;

  expect(dwellTime).toBeGreaterThan(90);  // 목표: >90초
});
```

---

## 4. Common Pitfalls & Solutions

### Pitfall 1: "샘플 크기 부족인데 결론 내림"

**문제**:
```
Version A: 3개 샘플, 평균 85점
Version B: 3개 샘플, 평균 92점
→ "B가 7점 높으니 B 채택!" ❌
```

**해결**:
```python
# 통계적 유의성 확인
from scipy import stats

if len(samples_a) < 20 or len(samples_b) < 20:
    print("⚠️ 샘플 부족. 최소 20개 이상 권장")

t_stat, p_value = stats.ttest_ind(samples_a, samples_b)

if p_value < 0.05:
    print("✅ 통계적으로 유의미")
else:
    print("❌ 우연일 수 있음. 샘플 더 필요")
```

---

### Pitfall 2: "청중 무시하고 기술 지표만 봄"

**문제**:
```
"버전 B가 로딩 속도 0.5초 빠름 → B 채택"
→ 하지만 사용자는 그 차이를 못 느낌 ❌
```

**해결**:
```
항상 질문: "이 지표가 청중의 Goal 달성에 얼마나 기여하는가?"

예시:
  로딩 0.5초 차이 → 청중이 "빠르다"고 느끼는 임계값은 2초
  → 둘 다 2초 이하면 청중에게 차이 없음
  → 다른 지표(UX, 가독성)로 판단
```

---

### Pitfall 3: "주관적 평가로 결정"

**문제**:
```
"내 생각엔 A가 더 깔끔해 보여"
→ 당신은 타깃 청중이 아님 ❌
```

**해결**:
```
1. 정량 지표 우선 (인게이지먼트, 클릭률 등)
2. 정량이 애매하면 → 실제 청중 3-5명 테스트
3. "나는 ~라고 생각함"은 가설일 뿐, 검증 필요
```

---

### Pitfall 4: "A/B 테스트를 일회성으로만 함"

**문제**:
```
테스트 → 결과 확인 → 끝
→ Learning이 축적되지 않음 ❌
```

**해결**:
```markdown
# tests/ab-test-log.md

## Test History

| Date | Test ID | Hypothesis | Result | Learnings |
|------|---------|------------|--------|-----------|
| 2026-03-26 | economy-kr-v2 | 3-Stage +15% | +14.8% ⚠️ | 구체적 숫자 효과 검증 |
| 2026-04-02 | tech-brief-tone | 존댓말 vs 반말 | 존댓말 +22% ✅ | 한국 청중은 존댓말 선호 |

→ 패턴 발견: 숫자 2개 이상 + 존댓말 = 최고 성과
```

---

## 5. Checklist: "Is This Audience-First?"

테스트 설계 전 이 체크리스트로 검증:

```
□ Audience Profile이 명확히 정의되어 있는가?
  □ Persona (이름, 나이, 직업)
  □ Pain Point
  □ Goal
  □ Success Criterion

□ Hypothesis가 청중 중심인가?
  □ "[청중]에게 ~" 형식으로 시작
  □ 청중의 Goal/Pain Point 언급
  □ 측정 가능한 지표 포함

□ KPI가 청중 행동/성과인가?
  □ Primary KPI = 청중이 목표 달성했는지 측정
  □ Secondary KPI = 보조 검증
  □ 모두 정량 측정 가능

□ Sample Size가 충분한가?
  □ 콘텐츠: 최소 20-30개
  □ 기능: 최소 100-200명
  □ 통계적 유의성 확인 계획 있음

□ 평가 방법이 객관적인가?
  □ 자동 평가 함수 or 실제 청중 테스트
  □ "내 생각엔"이 아닌 데이터 기반

□ Decision Rule이 명확한가?
  □ IF-THEN 형식
  □ Threshold 명시
  □ 애매한 경우 처리 방법 정의

□ Learning을 기록하는가?
  □ Test Log 작성
  □ Key Learnings 문서화
  □ 다음 테스트에 반영
```

**70% 이상 체크 → Audience-First 테스트**
**50% 미만 → 재설계 필요**

---

## 6. Resources

- [Audience-First Skill v2.0](../SKILL.md)
- [Workspace Audience Profiles](./workspace-audience-profiles.md)
- [DailyNews A/B Test Script](../../../automation/DailyNews/scripts/ab_test_economy_kr_v2.py)
- [Implementation Guide](../../../docs/reports/2026-03/AUDIENCE_FIRST_IMPLEMENTATION_GUIDE.md)

---

**Version**: 1.0.0
**Last Updated**: 2026-03-26
**License**: Internal use only (AI Project Workspace)
