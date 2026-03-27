# 전체 프로젝트 리팩토링 우선순위 분석 보고서

**일시**: 2026-03-23
**분석 대상**: AI 프로젝트 Monorepo 전체 (5개 주요 프로젝트)

---

## 📊 프로젝트별 복잡도 분석

| 프로젝트 | main.py 크기 | 구조 평가 | 리팩토링 필요성 | 상태 |
|---------|-------------|----------|---------------|------|
| **getdaytrends** | 1,435줄 → **358줄** | ⭐⭐⭐⭐⭐ 완료 | ~~긴급~~ | ✅ **완료** (75% 축소) |
| **instagram-automation** | 599줄 | ⭐⭐⭐⭐ 양호 | 중간 | 🟡 권장 |
| **content-intelligence** | 304줄 | ⭐⭐⭐⭐⭐ 우수 | 낮음 | ✅ 불필요 |
| **desci-platform/biolinker** | 198줄 | ⭐⭐⭐⭐⭐ 우수 | 낮음 | ✅ 불필요 |
| **DailyNews (antigravity_mcp)** | 255줄 (server.py) | ⭐⭐⭐⭐ 양호 | 낮음 | ✅ 불필요 |

---

## 🎯 리팩토링 완료: getdaytrends

### Before
```
main.py (1,435줄)
├── CLI 파싱
├── 파이프라인 오케스트레이션 (900줄+)
│   ├── 예산 체크 & 적응형 limit
│   ├── 트렌드 수집
│   ├── 품질 필터링 & 다양성 알고리즘
│   ├── 바이럴 스코어링
│   ├── 트윗 생성
│   └── 저장 (SQLite/Notion/Sheets)
└── 스케줄링 & 종료 처리
```

### After (✅ 완료)
```
main.py (358줄, 75% ⬇️)
├── CLI 파싱
├── 설정 검증
├── 앱 초기화
└── 스케줄러 실행

core/pipeline.py (1,016줄)
├── _check_budget_and_adjust_limit()
├── _step_collect()
├── _ensure_quality_and_diversity()
├── _step_score_and_alert()
├── _step_generate()
├── _step_save()
└── async_run_pipeline()
```

**성과**:
- ✅ main.py 75% 축소 (1,435 → 358줄)
- ✅ 파이프라인 로직 독립 모듈로 분리 (SRP 준수)
- ✅ CLAUDE.md Architecture 섹션 업데이트
- ✅ REFACTORING.md 문서 생성

---

## 🟡 리팩토링 권장: instagram-automation

### 현재 구조 (양호)
```
instagram-automation/
  main.py                  # FastAPI 앱 (599줄) - 엔드포인트 중심
  services/                # 잘 분리된 서비스 레이어 ⭐⭐⭐⭐
    ├── meta_api.py        # Instagram Graph API (13KB)
    ├── database.py        # DB 트랜잭션 (11KB)
    ├── content_generator.py  # 콘텐츠 생성 (10KB)
    ├── scheduler.py       # 스케줄링 (9KB)
    ├── content_calendar.py  # 캘린더 관리 (9KB)
    ├── hashtag_strategy.py  # 해시태그 전략 (10KB)
    ├── ab_testing.py      # A/B 테스트 (10KB)
    ├── monitoring.py      # 시스템 모니터링 (8KB)
    └── ... (15개 서비스 모듈)
```

**평가**:
- ✅ **서비스 레이어 잘 분리됨** (services/ 디렉토리)
- ✅ 각 모듈 단일 책임 (meta_api, database, scheduler 등)
- ✅ main.py는 FastAPI 라우터 정의만 담당 (적절)

**개선 제안** (선택사항):
1. **라우터 분리** (낮은 우선순위)
   ```
   routers/
     ├── posts.py         # /api/posts/* 엔드포인트
     ├── insights.py      # /api/insights/* 엔드포인트
     ├── calendar.py      # /api/calendar/* 엔드포인트
     └── hashtags.py      # /api/hashtags/* 엔드포인트
   ```
   → main.py 599줄 → ~250줄 예상 (FastAPI 권장 패턴)

2. **외부 트리거 핸들러 독립화**
   - `services/external_trigger.py` → `adapters/external_trigger.py`
   - n8n/webhook 통합 로직 명확화

**우선순위**: 🟡 **중간** (필수 아님, 팀 성장 시 고려)

---

## ✅ 리팩토링 불필요: content-intelligence

### 현재 구조 (우수 ⭐⭐⭐⭐⭐)
```
content-intelligence/
  main.py                  # CLI + 파이프라인 조율 (304줄) ✅
  config.py                # 설정 관리
  collectors/              # 트렌드 수집기들 (모듈화 완료)
    ├── x_collector.py
    ├── threads_collector.py
    └── naver_collector.py
  regulators/              # 플랫폼 규제 점검
    └── checklist.py
  generators/              # 콘텐츠 생성기
    └── content_engine.py
  storage/                 # 저장 계층
    ├── local_db.py
    └── models.py
  review/                  # 월간 회고
    └── monthly_review.py
```

**평가**:
- ✅ **완벽한 책임 분리**: 수집/규제/생성/저장 각 디렉토리 독립
- ✅ main.py 304줄로 적절 (CLI + 파이프라인 조율만)
- ✅ 각 단계가 명확한 함수로 분리됨

**getdaytrends 리팩토링 시 참고한 모범 사례**

**우선순위**: ✅ **없음** (이미 최적화됨)

---

## ✅ 리팩토링 불필요: desci-platform/biolinker

### 현재 구조 (우수 ⭐⭐⭐⭐⭐)
```
biolinker/
  main.py                  # FastAPI 앱 설정 (198줄) ✅
  routers/                 # 라우터 분리 완료 ⭐
    ├── rfp.py             # RFP 관련 엔드포인트
    ├── crawl.py           # 크롤링 엔드포인트
    ├── web3.py            # Web3/NFT 엔드포인트
    ├── agent.py           # AI 에이전트 엔드포인트
    ├── governance.py      # 거버넌스 엔드포인트
    └── subscription.py    # 구독 엔드포인트
  services/                # 서비스 레이어
    ├── analyzer.py        # LLM 분석
    ├── vector_store.py    # ChromaDB
    ├── smart_matcher.py   # 매칭 엔진
    ├── web3_service.py    # DeSciToken + NFT
    ├── auth.py            # Firebase 인증
    └── scheduler.py       # APScheduler
  models.py                # Pydantic 스키마
  firestore_db.py          # Firestore 싱글톤
```

**평가**:
- ✅ **FastAPI 베스트 프랙티스 준수**
- ✅ 라우터 완전 분리 (routers/ 디렉토리)
- ✅ main.py 198줄로 최소화 (앱 설정 + 라우터 등록만)
- ✅ 서비스 레이어 명확 분리

**우선순위**: ✅ **없음** (이미 최적화됨)

---

## ✅ 리팩토링 불필요: DailyNews (antigravity_mcp)

### 현재 구조 (양호 ⭐⭐⭐⭐)
```
DailyNews/src/antigravity_mcp/
  server.py                # MCP 서버 (255줄) ✅
  config.py                # 설정 (306줄)
  cli.py                   # CLI (128줄)
  integrations/            # 외부 통합 (어댑터 패턴)
    ├── notion_adapter.py
    ├── canva_adapter.py
    ├── sentiment_adapter.py
    ├── market_adapter.py
    └── skill_adapter.py
  pipelines/               # 파이프라인 로직
  tooling/                 # MCP 도구 구현
    └── notion_tools.py
  domain/                  # 도메인 모델
    └── markdown_blocks.py
  state/                   # 상태 관리
    ├── events.py
    └── locks.py
```

**평가**:
- ✅ **MCP 서버 구조 잘 분리됨**
- ✅ Adapter 패턴 적용 (integrations/)
- ✅ 도메인/상태/도구 계층 분리
- ✅ server.py 255줄로 적절 (MCP 서버 진입점)

**우선순위**: ✅ **없음** (이미 최적화됨)

---

## 📈 리팩토링 우선순위 요약

### 🏆 우선순위 1 (완료): **getdaytrends**
- **상태**: ✅ 리팩토링 완료 (2026-03-23)
- **성과**: main.py 75% 축소 (1,435 → 358줄)
- **문서**: [getdaytrends/REFACTORING.md](getdaytrends/REFACTORING.md)

### 🟡 우선순위 2 (권장): **instagram-automation**
- **필요성**: 중간 (팀 성장 시 고려)
- **제안**: 라우터 분리 (main.py 599 → ~250줄 예상)
- **예상 작업 시간**: 2-3시간

### ✅ 우선순위 3 (불필요): **나머지 프로젝트**
- **content-intelligence**: 이미 최적화됨 (모범 사례)
- **desci-platform/biolinker**: FastAPI 베스트 프랙티스 준수
- **DailyNews**: MCP 서버 구조 적절

---

## 💡 전체 프로젝트 코드 품질 평가

### 우수 사례 (⭐⭐⭐⭐⭐)
1. **content-intelligence** - 완벽한 책임 분리
2. **desci-platform/biolinker** - FastAPI 라우터 분리
3. **DailyNews** - Adapter 패턴 적용

### 개선 완료 (⭐⭐⭐⭐⭐)
1. **getdaytrends** - God Object 제거 완료

### 개선 권장 (⭐⭐⭐⭐)
1. **instagram-automation** - 라우터 분리 고려

---

## 📚 참고 문서

- **[CLAUDE.md](CLAUDE.md#architecture)** - 전체 프로젝트 구조
- **[getdaytrends/REFACTORING.md](getdaytrends/REFACTORING.md)** - getdaytrends 리팩토링 상세
- **FastAPI Best Practices**: https://fastapi.tiangolo.com/tutorial/bigger-applications/

---

## 🎯 다음 액션 아이템

### 즉시 (완료)
- [x] getdaytrends 리팩토링 완료
- [x] CLAUDE.md 업데이트
- [x] 리팩토링 보고서 작성

### 향후 고려사항
- [ ] instagram-automation 라우터 분리 (팀 성장 시)
- [ ] getdaytrends Phase 2-6 진행 (필요 시)
  - collectors/ (수집기 분리)
  - generation/ (생성기 분리)
  - analysis/ (분석기 분리)

---

**작성**: Claude (Anthropic)
**검토**: AI 프로젝트 팀
**버전**: 1.0
**최종 업데이트**: 2026-03-23
