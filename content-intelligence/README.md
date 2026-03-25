# Content Intelligence Engine (CIE) v2.0

> 트렌드 & 플랫폼 규제 반영 콘텐츠 창작 + 자동 발행 시스템

## 개요

CIE는 소셜 미디어 트렌드를 자동 수집하고, 플랫폼 규제를 점검한 뒤, 최적화된 콘텐츠를 생성하고 발행하는 **5단계 자동화 파이프라인**입니다.

```
수집 → 규제 점검 → 콘텐츠 생성/QA → 저장 → 발행(Notion/X)
 ↑
GDT Bridge (GetDayTrends DB 딥 연동)
```

### v2.0 새 기능

- **GetDayTrends DB 딥 연동**: 5개 테이블 (trends, tweets, content_feedback, posting_time_stats, watchlist_hits) 활용
- **자동 발행**: Notion Content Hub + X(Twitter) 자동 게시
- **확장된 트렌드 데이터**: sentiment, cross_source_confidence, hook_starter, 최적 게시 시간
- **발행 전용 모드**: `--mode publish-only`로 미발행 콘텐츠 일괄 게시

## 지원 플랫폼

| 플랫폼 | 트렌드 수집 | 규제 점검 | 콘텐츠 생성 | 자동 발행 |
|--------|-----------|----------|-----------|----------|
| X (Twitter) | ✅ GDT Bridge + LLM | ✅ Shadowban/알고리즘 | ✅ 단문/장문/쓰레드 | ✅ X API v2 |
| Threads | ✅ LLM 분석 | ✅ Meta 정책 | ✅ 공감형/인사이트형 | ⏳ Notion 저장 |
| 네이버 블로그 | ✅ DataLab API + LLM | ✅ C-Rank/D.I.A. | ✅ SEO 최적화 블로그 | ⏳ Notion 초안 |

## 빠른 시작

```bash
# 1. .env 설정
cp .env.example .env
# .env 파일에서 프로젝트 정보 입력

# 2. 드라이런 (구조 검증)
python main.py --dry-run --verbose

# 3. 트렌드 수집만
python main.py --mode trend

# 4. 전체 파이프라인 (발행 제외)
python main.py --mode full --verbose

# 5. 전체 파이프라인 + 자동 발행
python main.py --mode full --publish

# 6. 미발행 콘텐츠만 발행
python main.py --mode publish-only

# 7. 월간 회고
python main.py --mode review
```

## 실행 모드

| 모드 | 설명 | 주기 |
|------|------|------|
| `--mode trend` | 트렌드 수집만 | 매주 월요일 |
| `--mode regulation` | 규제 점검만 | 콘텐츠 제작 전 |
| `--mode full` | 전체 파이프라인 | 콘텐츠 제작 시 |
| `--mode full --publish` | 전체 + 자동 발행 | 정기 실행 시 |
| `--mode publish-only` | 미발행 콘텐츠 발행 | 수동 |
| `--mode review` | 월간 회고 | 매월 말 |
| `--dry-run` | 구조 검증 (LLM 호출 없음) | 디버깅 |

## QA 검증 (7축)

| 축 | 배점 | 설명 |
|---|---|---|
| Hook | 20 | 첫 문장 주목도 |
| Fact | 15 | 사실 일관성 |
| Tone | 15 | 톤/페르소나 일관성 |
| Kick | 15 | 결론 임팩트 |
| Angle | 15 | 고유 관점 |
| Regulation | 10 | 규제 준수 여부 |
| Algorithm | 10 | 알고리즘 최적화 |

기준 미달 시(70점 이하) 자동 재생성 → 최상위 버전 채택.

## 발행 설정

`.env`에서 발행 채널을 활성화합니다:

```ini
# Notion Content Hub
CIE_NOTION_PUBLISH=true
CIE_NOTION_DATABASE_ID=your-database-id

# X(Twitter) 자동 발행
CIE_X_PUBLISH=true
CIE_X_MIN_QA_SCORE=75  # X는 더 높은 QA 기준

# GetDayTrends DB 경로 (비워두면 자동 탐지)
CIE_GDT_DB_PATH=
```

## 프로젝트 구조

```
content-intelligence/
├── main.py                 # 5단계 파이프라인 엔트리포인트
├── config.py               # 환경변수 기반 설정 (v2.0)
├── collectors/
│   ├── base.py             # LLM 호출 공통
│   ├── gdt_bridge.py       # [v2.0] GetDayTrends DB 딥 연동
│   ├── x_collector.py      # X 트렌드 (GDT Bridge 우선)
│   ├── threads_collector.py
│   └── naver_collector.py
├── generators/
│   └── content_engine.py   # 콘텐츠 생성 + 7축 QA
├── regulators/
│   └── checklist.py        # 플랫폼별 규제 체크리스트
├── storage/
│   ├── local_db.py         # SQLite 저장 + v2.0 마이그레이션
│   ├── models.py           # 데이터 모델 (v2.0)
│   ├── notion_publisher.py # [v2.0] Notion 발행
│   └── x_publisher.py      # [v2.0] X 발행
├── prompts/                # LLM 프롬프트 템플릿
├── tests/
│   └── test_smoke.py       # 31 smoke tests
└── .env.example
```

## 기존 인프라 연동

- **`shared/llm`**: 통합 LLM 클라이언트 (Tier 라우팅, 폴백, 비용 추적)
- **`getdaytrends`**: X 트렌드 DB 딥 연동 (v2.0)
- **Notion Content Hub**: 콘텐츠 관리 대시보드 + 자동 발행
