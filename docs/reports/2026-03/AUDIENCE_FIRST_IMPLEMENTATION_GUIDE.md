# Audience-First Implementation Guide

> **작성일**: 2026-03-26
> **대상**: AI Project Workspace 전체 프로젝트
> **목적**: Audience-First Skill v2.0 도입 및 A/B 테스트 프레임워크 적용

---

## Executive Summary

**현황 문제점**:
- ✅ 기술적으로 완성도 높은 코드와 파이프라인 구축
- ❌ 타깃 청중 정의 없이 "만들고 나서 생각하기" 관행
- ❌ A/B 테스트가 "주관적 선호도" 수준에 머물러 있음
- ❌ 성과 측정이 기술 지표(빌드 성공/실패) 중심, 사용자 지표 부재

**해결 방안**:
- ✅ Audience-First Skill v2.0 도입 (청중 정의 → 설계 → 측정)
- ✅ 각 프로젝트별 Audience Profile 수립 완료
- ✅ KPI 기반 A/B 테스트 프레임워크 구축
- ✅ 단계별 실행 가이드 제공 (Phase 1-4, 4주 완료)

**예상 효과**:
- DailyNews: 인게이지먼트율 +50% (현 3% → 목표 5%)
- GetDayTrends: 바이럴 히트율 +30% (현 15% → 목표 20%)
- DeSci: 매칭 정확도 +20% (현 60% → 목표 80%)
- AgriGuard: B2C 채택률 +100% (현 50회/일 → 목표 1000회/일)

---

## Phase 1: Immediate Actions (Week 1)

### 1.1 Audience-First Skill v2.0 활성화

**Location**: [.claude/skills/audience-first/SKILL.md](../../../.claude/skills/audience-first/SKILL.md)

**Changes in v2.0**:
- ✅ Success Metrics & KPI framework (Phase 4 추가)
- ✅ B2B vs B2C 구분 가이드
- ✅ A/B 테스트 통합 프레임워크
- ✅ Localization/i18n 가이드 (한국어 특화)
- ✅ Persona Validation Checklist

**Action Items**:

```bash
# 1. 기존 스킬 백업
cd "D:/AI project/.claude/skills"
mkdir -p audience-first/backup
cp audience-first/SKILL.md audience-first/backup/SKILL_v1.md 2>/dev/null || echo "No existing file"

# 2. v2.0 스킬 확인
cat .claude/skills/audience-first/SKILL.md | head -50

# 3. Claude Code 재시작 (스킬 리로드)
# VSCode에서 Claude Code extension reload
```

**Validation**:
- [ ] 새 요청 시 Claude가 청중 프로필 먼저 확인하는지 체크
- [ ] B2C/B2B 구분을 자동으로 제안하는지 확인
- [ ] A/B 테스트 요청 시 KPI 정의를 먼저 묻는지 검증

---

### 1.2 프로젝트별 Audience Profile 임베딩

**Location**: [.claude/skills/audience-first/references/workspace-audience-profiles.md](../../../.claude/skills/audience-first/references/workspace-audience-profiles.md)

**각 프로젝트 README 업데이트**:

#### DailyNews

```bash
cd automation/DailyNews
```

**README.md에 추가** (Product Scope 다음):

```markdown
## Target Audience

**Type**: B2C (콘텐츠 구독형)

**Primary Persona**: "경제 인사이트 헌터"
- Demographics: 2040세대, 직장인/소상공인
- Pain Point: 경제 뉴스 홍수 속 핵심 파악 어려움, 시간 부족 (아침 5-10분만 투자 가능)
- Goal: 투자/재테크 의사결정에 도움 되는 실용적 인사이트
- Channel: X (Twitter) Longform, Notion Dashboard
- Success Metric: X 인게이지먼트율 >5%

**상세**: [workspace-audience-profiles.md](../../../.claude/skills/audience-first/references/workspace-audience-profiles.md#1-dailynews--antigravity-content-engine)
```

#### GetDayTrends

```bash
cd automation/getdaytrends
```

**README.md에 추가**:

```markdown
## Target Audience

**Type**: B2C (바이럴 콘텐츠 제작자용 도구)

**Primary Persona**: "트렌드 서퍼"
- Demographics: 20-35세, 콘텐츠 크리에이터/마케터
- Pain Point: 트렌드 수동 리서치 시간 낭비, 경쟁자보다 늦으면 기회 소진
- Goal: 매일 자동 Top 트렌드 확인 + 1시간 안에 콘텐츠 제작
- Interface: CLI + Telegram 알림 + Notion DB
- Success Metric: 사용자 바이럴 히트율 +50%

**상세**: [workspace-audience-profiles.md](../../../.claude/skills/audience-first/references/workspace-audience-profiles.md#2-getdaytrends)
```

#### DeSci Platform

```bash
cd apps/desci-platform
```

**README.md에 추가**:

```markdown
## Target Audience

**Type**: B2B (Prosumer) — 연구자 + VC 매칭 플랫폼

**Dual Persona**:
1. **연구자**: 박사급, 연구비 확보 어려움, RFP 매칭 자동화 원함
2. **VC/투자자**: 유망 바이오 프로젝트 조기 발견, 기술 평가 자동화

**Success Metric**: 성공 매칭 건수 월 >5건 (연구비 확보 or 투자 성사)

**상세**: [workspace-audience-profiles.md](../../../.claude/skills/audience-first/references/workspace-audience-profiles.md#3-desci-platform-biolinker)
```

#### AgriGuard

```bash
cd apps/AgriGuard
```

**README.md에 추가**:

```markdown
## Target Audience

**Type**: B2B (Enterprise) — 농수산 공급망 추적

**Dual Persona**:
1. **공급망 관리자**: 물류팀장, 실시간 온도 모니터링 필요, QR 기반 이력 조회
2. **최종 소비자**: 식품 안전 관심 부모/주부, QR 스캔으로 원산지 즉시 확인

**Success Metric**: 클레임 감소율 -90%, QR 스캔 일평균 >1000회

**상세**: [workspace-audience-profiles.md](../../../.claude/skills/audience-first/references/workspace-audience-profiles.md#4-agriguard)
```

**Validation**:
- [ ] 각 프로젝트 README에 Audience 섹션 존재
- [ ] 새 기여자가 README만 보고 "누구를 위한 것인지" 이해 가능
- [ ] 기능 우선순위가 Persona Pain Point와 일치

---

### 1.3 A/B Test v2.0 스크립트 배포

**Location**: [automation/DailyNews/scripts/ab_test_economy_kr_v2.py](../../../automation/DailyNews/scripts/ab_test_economy_kr_v2.py)

**Features**:
- ✅ Audience Profile 정의 (AUDIENCE_PROFILE dict)
- ✅ Hypothesis & KPI 명시 (AB_TEST_HYPOTHESIS)
- ✅ 자동 평가 함수 (evaluate_content_quality)
- ✅ Primary KPI 계산 (구체성 30% + 실용성 30% + 감정 공감 20% + CTA 20%)
- ✅ 의사결정 룰 (+15점 이상 AND Secondary 2개 충족 → NEW 채택)
- ✅ JSON + Markdown 리포트 자동 생성

**Usage**:

```bash
cd automation/DailyNews

# 기존 v1 백업
cp /tmp/ab_test_economy_kr.py scripts/ab_test_economy_kr_v1.py

# v2 실행
python scripts/ab_test_economy_kr_v2.py

# 결과 확인
cat output/ab_test_economy_kr_v2.md
```

**Expected Output**:

```
================================
🎯 AUDIENCE PROFILE
================================
타입: B2C
타깃: 한국 개인 투자자 (2040세대)
...

================================
🧪 A/B TEST HYPOTHESIS
================================
가설: 새 3-Stage 파이프라인은 기존 대비 더 구체적이고 실용적인 인사이트를 제공하여 독자 인게이지먼트를 높일 것
...

================================
📊 EVALUATION RESULTS
================================
Version              Primary KPI     Length    Specificity    Actionability   CTA
-----------------------------------------------------------------------------------------------
Version A (OLD)      67.5            531       60.0           50.0            30
Version B (NEW)      82.3            612       90.0           75.0            100

================================
✅ DECISION
================================
Primary KPI 차이: +14.8점 (Target: +15점)
Secondary 통과: 3/3개 (Target: 2개 이상)

결정: ⚠️ NEW 버전 조건부 채택 (추가 샘플 필요)
신뢰도: 중간
```

**Validation**:
- [ ] 스크립트 실행 시 에러 없이 완료
- [ ] JSON 리포트 생성 확인
- [ ] Primary KPI가 0-100 범위 내 숫자로 나옴
- [ ] Decision이 명확히 제시됨

---

## Phase 2: Integration & Automation (Week 2)

### 2.1 GetDayTrends A/B Test 추가

**목표**: 바이럴 스코어링 알고리즘 검증

**스크립트 생성**: `automation/getdaytrends/scripts/ab_test_viral_scoring.py`

**Hypothesis**:
> "새 멀티소스 스코어링은 단일 소스 대비 바이럴 히트 예측 정확도를 +20% 향상시킬 것"

**KPI**:
- Primary: Precision@10 (Top 10 트렌드 중 실제 히트율)
- Secondary: Recall (전체 히트 중 시스템이 포착한 비율)

**Template**:

```python
AUDIENCE_PROFILE = {
    "type": "B2C",
    "target_persona": {
        "primary": "콘텐츠 크리에이터",
        "pain_points": ["트렌드 늦게 알면 기회 소진", "수동 리서치 시간 낭비"],
    }
}

AB_TEST_HYPOTHESIS = {
    "hypothesis": "멀티소스 스코어링이 단일 소스 대비 히트 예측 정확도 +20%",
    "version_a": "getdaytrends.com만 사용",
    "version_b": "getdaytrends + X API + Reddit + Google News",
    "kpis": {
        "primary": {
            "name": "precision_at_10",
            "target": "OLD 대비 +20%p",
        }
    }
}

def evaluate_viral_prediction(scored_trends, actual_hits):
    """실제 히트 데이터와 비교하여 정확도 평가"""
    # Implementation...
```

**Action**:
```bash
# Template 기반으로 스크립트 생성
cd automation/getdaytrends/scripts
# (Claude Code에게 요청: "DailyNews A/B test v2를 참고하여 GetDayTrends용 바이럴 스코어링 A/B 테스트 스크립트 생성해줘")
```

---

### 2.2 DeSci Platform 매칭 정확도 A/B Test

**목표**: RFP-연구자 매칭 알고리즘 개선

**Hypothesis**:
> "키워드 매칭 → 벡터 유사도 변경 시 매칭 관련성이 +30% 향상"

**KPI**:
- Primary: 연구자 만족도 (매칭된 RFP 관련성 평가 1-5점)
- Secondary: 제안서 제출율 (매칭 후 실제 지원한 비율)

**Location**: `apps/desci-platform/biolinker/tests/ab_test_matching.py`

---

### 2.3 AgriGuard QR 페이지 UI A/B Test

**목표**: 소비자 QR 스캔 페이지 최적화

**Hypothesis**:
> "간소화된 UI는 기존 대비 평균 체류 시간 +40% 증가"

**KPI**:
- Primary: 평균 체류 시간 (초)
- Secondary: "자세히 보기" 클릭률

**Location**: `apps/AgriGuard/frontend/tests/ab_test_qr_page.spec.js` (Playwright)

---

## Phase 3: KPI Dashboard (Week 3)

### 3.1 Grafana Audience-Centric 대시보드

**기존 문제**:
- Grafana 대시보드가 기술 지표 중심 (CPU, 메모리, HTTP 200 비율)
- 사용자 행동 지표 부재

**신규 패널 추가**:

#### DailyNews Dashboard

```yaml
Panels:
  - Title: "X Post Engagement Rate"
    Query: "avg(engagement_rate) by (category)"
    Visualization: Time Series
    Alert: if < 3% for 7 days

  - Title: "Notion Page Views"
    Query: "sum(notion_page_views) by (report_id)"
    Visualization: Bar Chart

  - Title: "Reader Retention"
    Query: "avg(read_time_seconds) by (hour)"
    Visualization: Heatmap
```

#### GetDayTrends Dashboard

```yaml
Panels:
  - Title: "Viral Hit Rate"
    Query: "sum(actual_viral) / sum(predicted_viral_80plus)"
    Visualization: Gauge (Target: >70%)

  - Title: "Trend Collection Success"
    Query: "sum(trends_collected) by (source)"
    Visualization: Stacked Bar
```

**Action**:
```bash
cd ops/monitoring
# grafana/dashboards/ 에 audience-metrics.json 추가
```

---

### 3.2 주간 Audience Review 프로세스

**Schedule**: 매주 금요일 오전 10시

**Agenda**:
1. KPI Review (30분)
   - 각 프로젝트 Primary KPI 달성도 확인
   - Trend 분석 (증가/감소 원인)

2. Persona Validation (15분)
   - 실제 사용자 피드백 vs 가정한 Persona 비교
   - Mismatch 발견 시 Persona 업데이트

3. A/B Test 결과 공유 (15분)
   - 이번 주 진행한 테스트 결과
   - 학습한 인사이트 공유

**Output**:
- Weekly Audience Report (Notion 페이지)
- Action Items (다음 주 개선 과제)

---

## Phase 4: Continuous Improvement (Week 4+)

### 4.1 User Interview 프로그램

**목표**: Persona 검증 및 업데이트

**Process**:
1. 각 프로젝트당 월 2-3명 인터뷰
2. Persona 가설 vs 실제 비교
3. Pain Point/Goal 업데이트

**Questions Template**:

```
1. 이 서비스를 처음 쓰게 된 계기는?
2. 가장 큰 불편함/문제점은?
3. 대안 서비스와 비교했을 때 차별점은?
4. 이상적인 모습은?
5. 사용 빈도와 시간대는?
```

---

### 4.2 A/B Test 자동화

**DailyNews 예시**:

```yaml
# .github/workflows/ab-test-economy-kr.yml
name: Weekly Economy_KR A/B Test

on:
  schedule:
    - cron: '0 1 * * 1'  # 매주 월요일 오전 1시

jobs:
  ab-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run A/B Test
        run: |
          cd automation/DailyNews
          python scripts/ab_test_economy_kr_v2.py
      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: ab-test-report
          path: automation/DailyNews/output/ab_test_economy_kr_v2.json
      - name: Notify Telegram
        run: |
          # Telegram 알림 전송
```

---

## Success Metrics (4주 후)

| Project | Metric | Baseline | Target | Actual |
|---------|--------|----------|--------|--------|
| **DailyNews** | X 인게이지먼트율 | 3% | 5% | TBD |
| **GetDayTrends** | 바이럴 히트율 | 15% | 20% | TBD |
| **DeSci** | 매칭 정확도 | 60% | 80% | TBD |
| **AgriGuard** | QR 스캔/일 | 50회 | 1000회 | TBD |

**Overall**:
- [ ] 모든 프로젝트 README에 Audience 섹션 존재
- [ ] 최소 2개 프로젝트에서 A/B Test 실행
- [ ] Grafana에 Audience-Centric 패널 추가
- [ ] 주간 Audience Review 최소 2회 진행

---

## Quick Start Checklist

### 지금 바로 할 수 있는 것 (15분):

- [ ] Audience-First Skill v2.0 확인 ([.claude/skills/audience-first/SKILL.md](../../../.claude/skills/audience-first/SKILL.md))
- [ ] DailyNews A/B Test v2 실행 (`python automation/DailyNews/scripts/ab_test_economy_kr_v2.py`)
- [ ] Workspace Audience Profiles 읽기 ([references/workspace-audience-profiles.md](../../../.claude/skills/audience-first/references/workspace-audience-profiles.md))

### 이번 주 내 (2-3시간):

- [ ] 각 프로젝트 README에 Target Audience 섹션 추가
- [ ] GetDayTrends A/B Test 스크립트 생성
- [ ] Grafana 대시보드에 1개 Audience 패널 추가

### 이번 달 내 (4주):

- [ ] 전 프로젝트 A/B Test 최소 1회 실행
- [ ] 주간 Audience Review 프로세스 정착
- [ ] User Interview 프로그램 시작 (최소 2명)

---

## Troubleshooting

### Q1: A/B Test 결과가 통계적으로 유의미하지 않으면?

**A**: 샘플 크기 부족일 가능성. 최소 20-30개 샘플로 재실행. 그래도 유의미하지 않으면 "차이 없음"도 중요한 인사이트.

### Q2: Persona가 실제 사용자와 다르면?

**A**: Persona 업데이트! 가설이 틀렸음을 인정하고 실제 데이터 기반으로 수정. 이게 바로 Audience-First의 핵심.

### Q3: B2B와 B2C 구분이 애매한 경우?

**A**: "의사결정자 = 사용자"인가? Yes → B2C, No → B2B. 예: DeSci는 연구자가 직접 결정하므로 Prosumer (B2C에 가까움).

### Q4: 모든 프로젝트에 즉시 적용 부담스러우면?

**A**: **DailyNews부터 시작 추천**. 가장 B2C적이고 성과 측정 쉬움. 성공 후 다른 프로젝트 확산.

---

## Resources

- [Audience-First Skill v2.0](../../../.claude/skills/audience-first/SKILL.md)
- [Workspace Audience Profiles](../../../.claude/skills/audience-first/references/workspace-audience-profiles.md)
- [DailyNews A/B Test v2 Script](../../automation/DailyNews/scripts/ab_test_economy_kr_v2.py)
- [Skills & MCP Proposal](./SKILLS_MCP_PROPOSAL.md) — 전체 워크스페이스 개선 계획

---

**Version**: 1.0.0
**Last Updated**: 2026-03-26
**Owner**: AI Project Workspace Team
