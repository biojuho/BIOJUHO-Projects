# Workspace Audience Profiles

> **작성일**: 2026-03-26
> **대상**: AI Project Workspace (DailyNews, GetDayTrends, DeSci, AgriGuard)
> **용도**: 각 프로젝트별 타깃 청중 정의 및 설계 가이드

---

## 1. DailyNews / Antigravity Content Engine

### 🎯 Audience Profile

**Type**: B2C (콘텐츠 구독형)

**Primary Persona**: "경제 인사이트 헌터" (김지훈, 32세)

| Dimension | Details |
|-----------|---------|
| **Demographics** | 2040세대, 직장인/소상공인/1인 창업자 |
| **Location** | 한국 (서울/경기 60%, 지방 40%) |
| **Tech Proficiency** | 중상 (Notion, X 일상 사용, MZ 디지털 네이티브) |
| **Income** | 중산층 (연 3000-7000만원), 재테크 관심 높음 |

**Psychographics**:

```yaml
Pain Points:
  - 경제 뉴스 홍수 속에서 핵심만 빠르게 파악하고 싶음
  - 부동산/주식 시장 불확실성에 대한 불안
  - 뉴스 대부분이 실생활과 무관하게 느껴짐
  - 시간 부족 (아침 출근 전 5-10분만 투자 가능)

Goals:
  - 아침 출근길 5분 안에 핵심 경제 동향 파악
  - 투자/재테크 의사결정에 도움 되는 실용적 인사이트
  - 지인/동료에게 공유할 가치 있는 콘텐츠
  - "똑똑한 사람"으로 보이고 싶은 욕구

Emotional Triggers:
  - FOMO (남들은 다 아는데 나만 모르는 건 아닐까)
  - 경제적 안전 (내 자산을 지키고 싶음)
  - 정보 우위 (남보다 먼저 알고 싶음)
  - 사회적 인정 (정보 공유로 인정받고 싶음)

Values:
  - 시간 효율성 > 완벽한 정보
  - 실용성 > 학술성
  - 중립성 (정치 편향 극도로 싫어함)
  - 데이터 기반 (주관적 의견보다 팩트 선호)
```

**Consumption Context**:

| Aspect | Details |
|--------|---------|
| **Primary Channel** | X (Twitter) Longform Post |
| **Secondary** | Notion Dashboard, Telegram 알림 |
| **Time** | 평일 오전 7-9시 (출근길), 점심 12-1시, 퇴근 후 9-10시 |
| **Device** | 모바일 80%, 데스크톱 20% |
| **Attention Span** | 첫 2줄 (3초)에서 읽을지 결정 |
| **Reading Pattern** | 스캔 → 흥미 항목만 정독 |

**Success Criteria** (Must-Have):

```
✅ 헤드라인에 구체적 숫자/사실 포함 (예: "4223조 원", "1.6배")
✅ 개인에게 미치는 영향 명시 ("당신의 자산에 미칠 3가지 영향")
✅ 행동 가능한 인사이트 or 명확한 Next Step
✅ 중립적 어조 (정치 편향 없음)
✅ 400-800자 (모바일 최적 길이)
```

**Language & Culture**:

```yaml
Locale: ko-KR
Tone: 전문적이되 접근 가능 (완곡 표현, 존댓말 기본)
Structure: 결론 뒤로 미루기 (서론-본론-결론, 한국식 글쓰기)
Taboo:
  - 과도한 공포 유발 (불안 마케팅)
  - 정치 편향 명시
  - 투자 권유 (법적 리스크)
  - 근거 없는 예측
```

---

### 📊 Content Strategy

**Content Types & Formats**:

| Type | Purpose | Format | Frequency |
|------|---------|--------|-----------|
| **Daily Brief** | 당일 핵심 3-5개 이슈 요약 | Notion Page + X Thread | 매일 오전 7시 |
| **Deep Dive** | 주요 이슈 심층 분석 | Longform Post (800-1200자) | 주 2-3회 |
| **Weekly Wrap** | 주간 핵심 정리 + 다음주 전망 | Notion + Canva Infographic | 주말 |
| **X Quick Hit** | 단일 뉴스 속보 | Short Tweet (280자 이하) | 실시간 |

**Editorial Policy**:

```
필터링 기준:
  ✅ 개인 자산/소비에 직접 영향
  ✅ 3일 내 실용적 의사결정 가능
  ✅ 신뢰할 수 있는 출처 (정부 통계, 메이저 언론)

  ❌ 정치 이슈 (경제 정책 제외)
  ❌ 해외 뉴스 (한국 영향 미미한 경우)
  ❌ 단순 기업 홍보성 기사
  ❌ 불확실한 루머/예측
```

**KPIs**:

```yaml
Primary:
  - X 인게이지먼트율: (좋아요+RT+답글)/조회수 목표 >5%
  - Notion 페이지뷰: 일평균 >100회

Secondary:
  - 독자 체류 시간: 평균 >2분
  - 주간 신규 팔로워: >50명
  - 콘텐츠 공유율: >10% (독자 중 공유한 비율)

Qualitative:
  - 댓글 톤 (긍정:부정 비율 >3:1)
  - "유익했다" 키워드 멘션 수
```

---

## 2. GetDayTrends

### 🎯 Audience Profile

**Type**: B2C (바이럴 콘텐츠 제작자용 도구)

**Primary Persona**: "트렌드 서퍼" (이서연, 27세)

| Dimension | Details |
|-----------|---------|
| **Demographics** | 20-35세, 콘텐츠 크리에이터/마케터/1인 미디어 |
| **Location** | 글로벌 (한국 40%, 미국 30%, 기타 30%) |
| **Tech Proficiency** | 고 (API, Automation 이해, 개발자는 아님) |
| **Income** | 변동형 (프리랜서, 광고 수익 의존) |

**Psychographics**:

```yaml
Pain Points:
  - 트렌드를 수동으로 찾고 분석하는 시간 낭비
  - 경쟁자보다 늦게 알면 이미 기회 소진
  - 트렌드 5개 중 1개만 히트하는 불확실성
  - 글로벌 트렌드를 놓칠까봐 불안

Goals:
  - 매일 아침 자동으로 Top 트렌드 + 바이럴 점수 확인
  - 1시간 안에 트렌드 기반 콘텐츠 제작
  - 트렌드 → 트윗/쓰레드 자동 생성으로 시간 절약
  - 히트 패턴 분석으로 성공률 높이기

Emotional Triggers:
  - FOMO (트렌드 놓치면 수익 기회 소실)
  - 효율성 (자동화로 시간 확보)
  - 경쟁 우위 (남보다 먼저, 더 빠르게)
  - 성취감 (바이럴 히트 쾌감)

Values:
  - 속도 > 완벽함 (80점짜리를 빠르게)
  - 데이터 기반 (감이 아닌 스코어링)
  - 자동화 (수동 작업 최소화)
  - 멀티소스 (한 곳에 의존 위험)
```

**Consumption Context**:

| Aspect | Details |
|--------|---------|
| **Primary Interface** | CLI + Telegram/Discord 알림 |
| **Secondary** | Notion DB (트렌드 아카이브) |
| **Usage Time** | 매일 오전 8-9시 (하루 시작 전 체크) |
| **Workflow** | 알림 받음 → Notion 확인 → 트윗 선택 → 수동 게시 or 자동화 |
| **Decision Time** | 트렌드당 10초 이하 (바이럴 점수 80+ 즉시 채택) |

**Success Criteria**:

```
✅ 바이럴 스코어링 정확도 >70% (실제 히트율과 상관관계)
✅ 트렌드 수집 자동화 (매 2시간, 무인 운영)
✅ 트윗 시안 5종 자동 생성 (스타일 다양성)
✅ 멀티소스 통합 (getdaytrends + X API + Reddit + Google News)
✅ 히스토리 DB로 중복 방지
```

**Language & Culture**:

```yaml
Locale: Multi (ko-KR primary, en-US secondary)
Tone: 캐주얼, 빠른 의사결정용 (간결함 최우선)
Structure: 핵심 먼저 (역피라미드)
Output Style:
  - CLI: 최소 verbosity (진행바, 요약만)
  - Notion: 구조화된 테이블 (필터링/정렬 가능)
  - Alert: 긴급도 표시 (바이럴 80+ 🔥 아이콘)
```

---

### 📊 Product Strategy

**Core Value Proposition**:
> "트렌드 리서치 3시간 → 10초로 단축. 바이럴 성공률 3배 증가."

**Feature Prioritization**:

| Priority | Feature | Reason |
|----------|---------|--------|
| P0 | 바이럴 스코어링 | 의사결정의 핵심 (어떤 트렌드에 집중?) |
| P0 | 멀티소스 수집 | 단일 소스 실패 시 백업 |
| P1 | 트윗 시안 자동 생성 | 시간 절약 (수동 작성 불필요) |
| P1 | Telegram/Discord 알림 | 모바일 즉시 확인 |
| P2 | 히스토리 DB | 중복 방지, 패턴 학습 |
| P3 | A/B 테스트 통합 | 어떤 스타일이 효과적인지 학습 |

**KPIs**:

```yaml
Product Metrics:
  - 일 트렌드 수집 성공률: >95%
  - 바이럴 스코어 80+ 비율: 10-20%
  - 트윗 생성 소요 시간: <30초/건

User Engagement:
  - 일 활성 사용자: >100명
  - Notion DB 저장률: >80% (생성된 트윗 중 저장)
  - 알림 클릭률: >40%

Business Impact (사용자 기준):
  - 사용자 평균 바이럴 히트율: +50% (사용 전 대비)
  - 콘텐츠 제작 시간: -60%
```

---

## 3. DeSci Platform (BioLinker)

### 🎯 Audience Profile

**Type**: B2B (Prosumer) — 연구자 + VC 매칭 플랫폼

**Dual Persona**:

#### 3A. "연구자 페르소나" (박민지, 35세 박사후연구원)

| Dimension | Details |
|-----------|---------|
| **Demographics** | 30-50세, 박사급 연구자, 대학/연구소/바이오스타트업 |
| **Location** | 글로벌 (한국 30%, 미국 40%, 유럽 20%, 기타 10%) |
| **Tech Proficiency** | 중 (논문 작성 능력 高, 웹 플랫폼 이해 中) |
| **Pain Point** | 연구비 확보 어려움, RFP 찾기 시간 부족, VC 네트워크 없음 |

```yaml
Goals:
  - 내 연구와 매칭되는 RFP/펀딩 자동 발견
  - 제안서(Proposal) 초안 AI 생성으로 시간 절약
  - VC/투자자에게 연구 가치 효과적으로 전달
  - IPFS에 연구 데이터 영구 보존

Emotional Triggers:
  - 연구 지속성에 대한 불안 (펀딩 없으면 중단)
  - 행정 업무 부담 (연구 시간 잠식)
  - 인정 욕구 (내 연구의 사회적 가치 증명)

Decision Criteria:
  - 매칭 정확도 (내 분야와 관련성 >80%)
  - 시간 절약 (제안서 작성 3일 → 1일)
  - 신뢰성 (AI 생성 내용의 정확도)
```

#### 3B. "VC/투자자 페르소나" (김태준, 42세 파트너)

| Dimension | Details |
|-----------|---------|
| **Demographics** | 35-55세, VC 파트너/애널리스트, 바이오펀드 운용사 |
| **Location** | 한국/미국 중심 |
| **Tech Proficiency** | 중상 (금융 모델링 능력 高, DeSci 개념 학습 중) |
| **Pain Point** | 좋은 연구 발굴 어려움, 기술 평가 시간 부족, Deal Flow 부족 |

```yaml
Goals:
  - 투자 가치 높은 연구 프로젝트 조기 발견
  - 기술 평가 자동화 (AI 요약 + 매칭 스코어)
  - 포트폴리오 다각화 (바이오 섹터 확장)
  - DAO 거버넌스로 투명한 의사결정

Emotional Triggers:
  - FOMO (경쟁 펀드가 먼저 투자할까봐)
  - 리스크 회피 (검증되지 않은 연구 두려움)
  - 포트폴리오 성과 압박

Decision Criteria:
  - ROI 명확성 (투자금 대비 기대 수익)
  - 위험도 평가 (연구 성공 확률)
  - 매칭 알고리즘 신뢰도
  - 거버넌스 투명성 (DAO 투표 기록)
```

---

### 📊 Platform Strategy

**Value Proposition**:

```
연구자 → "연구비 찾기 100시간 → 10분으로 단축"
VC → "유망 바이오 프로젝트 조기 발견으로 경쟁 우위"
```

**Feature Prioritization**:

| Priority | Feature | User | Reason |
|----------|---------|------|--------|
| P0 | RFP 크롤링 + 벡터 검색 | 연구자 | 코어 가치 (매칭 없으면 의미 없음) |
| P0 | AI Proposal Generator | 연구자 | 시간 절약 (채택 이유 1순위) |
| P0 | 매칭 스코어링 | 양쪽 | 의사결정 기준 |
| P1 | VC Dashboard | VC | 투자 기회 시각화 |
| P1 | IPFS 데이터 저장 | 연구자 | 영구 보존 (DeSci 핵심 가치) |
| P2 | DAO 거버넌스 | 양쪽 | 투명성 (플랫폼 신뢰도) |

**KPIs**:

```yaml
Matching Accuracy:
  - 연구자 만족도: 매칭 RFP 관련성 >80%
  - VC Deal Flow: 월 신규 프로젝트 >20건

Engagement:
  - 연구자 제안서 제출율: >60% (매칭 후)
  - VC 프로젝트 평가율: >40% (추천 프로젝트 중)

Business:
  - 성공 매칭 건수: 월 >5건 (연구비 확보 or 투자 성사)
  - 플랫폼 수수료 수익: 매칭 건당 5-10%
```

---

## 4. AgriGuard

### 🎯 Audience Profile

**Type**: B2B (Enterprise) — 농수산 공급망 추적 플랫폼

**Dual Persona**:

#### 4A. "공급망 관리자" (이현수, 38세 물류팀장)

| Dimension | Details |
|-----------|---------|
| **Demographics** | 30-50세, 농수산 유통업체/대형마트 물류팀 |
| **Location** | 한국 중심 |
| **Tech Proficiency** | 중하 (ERP 사용 가능, 블록체인 개념 모름) |
| **Pain Point** | 수기 기록 오류, 콜드체인 중단 발견 지연, 클레임 대응 증거 부족 |

```yaml
Goals:
  - 실시간 온도 모니터링 (냉동차 고장 즉시 감지)
  - QR 스캔으로 전체 이력 즉시 조회
  - 클레임 발생 시 블록체인 증거 제시
  - 종이 서류 없애고 태블릿으로 통합

Emotional Triggers:
  - 리스크 회피 (식품 사고 → 브랜드 타격)
  - 효율성 (수기 입력 스트레스)
  - 컴플라이언스 (정부 규제 준수 압박)

Decision Criteria:
  - 구현 난이도 (기존 시스템과 충돌 최소)
  - 비용 (ROI 2년 내 회수)
  - 사용 편의성 (비기술자 교육 1시간 이하)
```

#### 4B. "최종 소비자" (김수진, 29세 주부)

| Dimension | Details |
|-----------|---------|
| **Demographics** | 20-40세, 식품 안전 관심 높은 부모/주부 |
| **Location** | 도심 거주, 온라인 장보기 선호 |
| **Tech Proficiency** | 중 (QR 스캔 익숙, 앱 설치 거부감 낮음) |
| **Pain Point** | 식품 원산지 신뢰 안 됨, 유통기한만 보고 구매, 리콜 뉴스 불안 |

```yaml
Goals:
  - QR 찍으면 "진짜 국내산"인지 즉시 확인
  - 콜드체인 유지 여부 확인 (냉동 안 깨졌나?)
  - 아이 먹이는 식품은 이력 확인 후 구매
  - 간편한 UI (앱 설치 없이 웹뷰로)

Emotional Triggers:
  - 자녀 안전 (식중독 두려움)
  - 신뢰 (브랜드 말만 믿기 싫음)
  - 편리함 (복잡한 앱 설치 거부)

Decision Criteria:
  - 사용 편의성 (QR 1회 스캔으로 끝)
  - 정보 신뢰도 (블록체인 → 위변조 불가 인식)
  - 디자인 (깔끔한 UI, 전문 용어 배제)
```

---

### 📊 Platform Strategy

**Value Proposition**:

```
B2B → "식품 클레임 90% 감소, 물류 효율 +30%"
B2C → "QR 하나로 먹거리 안심"
```

**Feature Prioritization**:

| Priority | Feature | User | Reason |
|----------|---------|------|--------|
| P0 | QR 기반 이력 조회 | B2C | 소비자 채택의 핵심 |
| P0 | IoT 온도 모니터링 | B2B | 콜드체인 사고 예방 (ROI 최대) |
| P0 | 블록체인 기록 | 양쪽 | 신뢰성 (위변조 불가) |
| P1 | 관리자 대시보드 | B2B | 운영 효율화 |
| P1 | 알림 시스템 (온도 이탈) | B2B | 사고 조기 대응 |
| P2 | NFT 인증서 | B2C | 프리미엄 상품 차별화 |

**KPIs**:

```yaml
Operational:
  - QR 스캔 성공률: >99%
  - 온도 데이터 수집 주기: 5분 간격
  - 블록체인 기록 지연: <30초

Business Impact:
  - 클레임 감소율: -90% (블록체인 증거)
  - 물류 효율 증가: +30% (실시간 추적)
  - 프리미엄 상품 가격: +10-20% (신뢰도 상승)

Adoption:
  - B2B 고객사: 분기당 +5개
  - B2C QR 스캔: 일평균 >1000회
```

---

## Summary: Audience Segmentation Matrix

| Project | Type | Primary User | Decision Driver | Key Metric |
|---------|------|--------------|-----------------|------------|
| **DailyNews** | B2C | 2040 경제 관심층 | 시간 절약 + 실용성 | 인게이지먼트율 |
| **GetDayTrends** | B2C | 콘텐츠 크리에이터 | 자동화 + 바이럴 성공률 | 트렌드 히트율 |
| **DeSci** | B2B (Prosumer) | 연구자 + VC | 매칭 정확도 + 시간 절약 | 성공 매칭 건수 |
| **AgriGuard** | B2B (Enterprise) | 물류팀장 + 소비자 | 리스크 감소 + 신뢰 | 클레임 감소율 |

---

## Next Steps

1. **각 프로젝트에 Audience Profile 임베딩**:
   - README.md에 "Target Audience" 섹션 추가
   - 기능 우선순위를 Persona 기준으로 재정렬

2. **A/B 테스트 프레임워크 적용**:
   - DailyNews: 콘텐츠 스타일 테스트
   - GetDayTrends: 바이럴 스코어링 알고리즘 검증
   - DeSci: 매칭 알고리즘 정확도 개선
   - AgriGuard: QR 페이지 UI 최적화

3. **KPI 대시보드 구축**:
   - Grafana에 Audience-Centric 지표 추가
   - 주간 리뷰 시 Persona 기준 점검

4. **Persona 검증**:
   - 실제 사용자 인터뷰 (각 프로젝트당 5-10명)
   - 가설 vs 실제 비교 분석

---

**License**: Internal use only (AI Project Workspace)
**Version**: 1.0.0
**Last Updated**: 2026-03-26
