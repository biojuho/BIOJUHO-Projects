# DailyNews Insight Generator — 설치 및 사용 가이드

## 개요

DailyNews Insight Generator는 3대 품질 원칙(점→선 연결, 파급 효과 예측, 실행 가능한 결론)을 충족하는 고품질 뉴스 인사이트를 자동 생성하는 Skill입니다.

## 설치 위치

현재 Skill은 다음 위치에 설치되어 있습니다:

```
d:/AI 프로젝트/.agent/skills/daily-insight-generator/
├── SKILL.md              # Skill 문서
├── generator.py          # 인사이트 생성 로직
├── validator.py          # 품질 검증 로직
└── templates/
    └── x_long_form.md    # X 롱폼 템플릿
```

## 파이프라인 통합

### 1. analyze.py 수정 사항

[`src/antigravity_mcp/pipelines/analyze.py:237-257`](../../src/antigravity_mcp/pipelines/analyze.py#L237-L257)에 인사이트 생성 로직이 추가되었습니다:

```python
# --- DailyNews Insight Generator (optional) ---
insight_report_x_form = ""
if insight_adapter and hasattr(insight_adapter, "generate_insight_report"):
    try:
        articles_data = [
            {"title": item.title, "summary": item.summary[:200], "link": item.link}
            for item in category_items
        ]
        insight_summaries, insight_items, x_long_form = await insight_adapter.generate_insight_report(
            category=category,
            articles=articles_data,
            window_name=window_name,
        )
        # Merge DailyNews insights into report
        for insight_item in insight_items[:3]:
            insights.append(insight_item)
        # Store X long-form separately for later publishing
        insight_report_x_form = x_long_form
        logger.info("DailyNews Insight Generator enriched %s: %d insights", category, len(insight_items))
    except Exception as exc:
        warnings.append(f"DailyNews Insight Generator failed for {category}: {type(exc).__name__}: {exc}")
```

### 2. 사용 방법

#### A. 파이프라인에서 자동 호출 (권장)

```python
from antigravity_mcp.integrations.insight_adapter import InsightAdapter
from antigravity_mcp.pipelines.analyze import generate_briefs

# InsightAdapter 초기화
insight_adapter = InsightAdapter(llm_adapter=llm_adapter, state_store=state_store)

# generate_briefs 호출 시 insight_adapter 전달
run_id, reports, warnings, status = await generate_briefs(
    items=content_items,
    window_name="morning",
    window_start=window_start,
    window_end=window_end,
    state_store=state_store,
    insight_adapter=insight_adapter,  # ← 여기에 추가
)
```

#### B. 독립 실행 (CLI)

```bash
# 워크스페이스 루트에서 실행
cd "d:/AI 프로젝트"

python .agent/skills/daily-insight-generator/generator.py \
  --category "Tech" \
  --articles '[{"title":"엔비디아 H100 품귀","summary":"AI 칩 부족","link":"https://example.com"}]' \
  --window "morning" \
  --max-insights 4 \
  --output json
```

## 3대 품질 원칙

### 원칙 1: 점(Fact) → 선(Trend) 연결

- 최소 2개 이상의 독립된 데이터 포인트 연결
- 시간축 트렌드 언급 (과거 → 현재 → 미래)
- 산업/분야 간 연결 고리 제시

**예시:**
> "엔비디아 H100 품귀(3월), AMD MI300X 출시(2월), 구글 TPU v5(1월)는 독립 이벤트가 아니라 AI 인프라 수직통합 경쟁의 일부입니다."

### 원칙 2: 파급 효과(Ripple Effect) 예측

- 1차 효과 명시
- 2차 효과 예측
- (선택) 3차 효과 언급

**예시:**
> "1차: GPU 공급 부족 → 2차: AI 스타트업 학습 비용 3배 상승 → 3차: 오픈소스 vs 폐쇄형 모델 격차 확대"

### 원칙 3: 실행 가능한 결론(Actionable Item) 도출

- 구체적 행동 동사 사용 (시작하라, 점검하라)
- 타겟 독자 명시 (투자자, 개발자, 창업자)
- 실행 가능한 구체적 행동 제시

**예시:**
> "AI 스타트업이라면 지금 당장 클라우드 크레딧 확보 전략을 수립하고, Smaller 모델 연구에 투자하세요."

## 검증 체계

### 자동 검증 (validator.py)

모든 인사이트는 다음과 같이 자동 검증됩니다:

```python
from validator import InsightValidator

validator = InsightValidator(min_score=0.6)
result = validator.validate(insight)

print(f"원칙 1 점수: {result['principle_1_score']:.2f}")
print(f"원칙 2 점수: {result['principle_2_score']:.2f}")
print(f"원칙 3 점수: {result['principle_3_score']:.2f}")
print(f"검증 통과: {result['validation_passed']}")
```

### 검증 기준

- **원칙 1**: 데이터 포인트(35%) + 시간축(35%) + 연결 표현(30%)
- **원칙 2**: 파급 연결어(40%) + 단계별 언급(40%) + 인과관계(20%)
- **원칙 3**: 행동 동사(40%) + 타겟 독자(30%) + 구체성(30%)

최소 점수: 각 원칙별 0.6점 이상

## 출력 형식

### JSON 출력

```json
{
  "insights": [
    {
      "title": "AI 반도체 경쟁 심화: 엔비디아의 독주와 후발주자들의 전략",
      "content": "...",
      "principle_1_connection": "H100 + MI300X + TPU v5 → AI 인프라 경쟁",
      "principle_2_ripple": "1차: 공급 부족 → 2차: 비용 상승 → 3차: 격차 확대",
      "principle_3_action": "클라우드 크레딧 확보, Smaller 모델 연구",
      "target_audience": "AI 스타트업, 투자자",
      "validation_passed": true,
      "principle_1_score": 0.9,
      "principle_2_score": 0.85,
      "principle_3_score": 0.95
    }
  ],
  "x_long_form": "# 📰 Tech 주요 인사이트 (2026-03-21)\n\n...",
  "validation_summary": {
    "total_insights": 4,
    "passed": 4,
    "failed": 0
  }
}
```

### X 롱폼 포스트

```markdown
# 📰 Tech 주요 인사이트 (2026-03-21)

오늘의 뉴스에서 도출한 핵심 인사이트입니다.

## 1. AI 반도체 경쟁 심화: 엔비디아의 독주와 후발주자들의 전략

...

**점→선 연결**: H100 + MI300X + TPU v5 → AI 인프라 경쟁
**파급 효과**: 1차: 공급 부족 → 2차: 비용 상승 → 3차: 격차 확대
**실행 항목**: 클라우드 크레딧 확보, Smaller 모델 연구

---

💡 생성: DailyNews Insight Generator
```

## 설정 파일

### prompts/insight_quality_check.md

전체 품질 체크리스트와 검증 프로세스가 문서화되어 있습니다:

- [prompts/insight_quality_check.md](../../prompts/insight_quality_check.md)

### templates/x_long_form.md

X 롱폼 포스트 작성 템플릿과 가이드라인:

- [.agent/skills/daily-insight-generator/templates/x_long_form.md](d:/AI 프로젝트/.agent/skills/daily-insight-generator/templates/x_long_form.md)

## 테스트

### 1. Validator 단독 테스트

```bash
cd "d:/AI 프로젝트"
python .agent/skills/daily-insight-generator/validator.py
```

**예상 출력:**
```
=== 테스트 1: 좋은 인사이트 ===
통과 여부: True
원칙1: 1.00
원칙2: 0.80
원칙3: 0.85
```

### 2. Generator 테스트 (더미 데이터)

```bash
cd "d:/AI 프로젝트"
python .agent/skills/daily-insight-generator/generator.py \
  --category "Tech" \
  --articles '[{"title":"테스트","summary":"테스트","link":"https://example.com"}]' \
  --output json
```

### 3. 전체 파이프라인 테스트

```bash
cd "d:/AI 프로젝트/DailyNews"
python -m antigravity_mcp jobs generate-brief --window morning --max-items 5
```

## 문제 해결

### Skill not available 오류

```
Insight generator skill is not available. Install the skill first.
```

**원인**: Skill 경로를 찾을 수 없음

**해결책**:
1. Skill이 `d:/AI 프로젝트/.agent/skills/daily-insight-generator/`에 있는지 확인
2. `generator.py` 파일이 존재하는지 확인
3. Python 경로에 워크스페이스 루트가 포함되어 있는지 확인

### 검증 실패 반복

```
validation_passed: False (P1: 0.4, P2: 0.3, P3: 0.5)
```

**원인**: LLM이 3대 원칙을 제대로 반영하지 못함

**해결책**:
1. `generator.py`의 프롬프트 온도 조정 (`temperature=0.7` → `0.5`)
2. LLM 모델 변경 (Gemini → GPT-4)
3. `validator.py`의 `min_score` 임시 완화 (`0.6` → `0.5`)

### 인사이트가 너무 길 때

**해결책**:
- `generator.py`에서 `--max-words` 파라미터 추가
- 프롬프트에 "150-300단어로 작성" 명시적 지시 추가

## 향후 개선 사항

### Phase 2 (예정)

- [ ] 과거 30일 트렌드 자동 조회 강화
- [ ] 카테고리별 맞춤 프롬프트
- [ ] X API 자동 발행 통합
- [ ] A/B 테스팅 (인사이트 퍼포먼스 추적)

### Phase 3 (고려 중)

- [ ] 다국어 지원 (영어 인사이트 생성)
- [ ] 이미지 첨부 (차트, 그래프)
- [ ] 음성 읽기 최적화 (팟캐스트용)

## 관련 문서

- [SKILL.md](d:/AI 프로젝트/.agent/skills/daily-insight-generator/SKILL.md): Skill 전체 문서
- [insight_quality_check.md](../../prompts/insight_quality_check.md): 품질 체크리스트
- [x_long_form.md](d:/AI 프로젝트/.agent/skills/daily-insight-generator/templates/x_long_form.md): X 템플릿
- [analyze.py](../../src/antigravity_mcp/pipelines/analyze.py): 파이프라인 통합 코드

## 라이선스

이 Skill은 DailyNews 프로젝트의 일부로 MIT 라이선스 하에 배포됩니다.

---

생성 일시: 2026-03-21
버전: v1.0
