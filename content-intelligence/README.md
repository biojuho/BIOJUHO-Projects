# Content Intelligence Engine (CIE) v1.0

> 트렌드 & 플랫폼 규제 반영 콘텐츠 창작 시스템

## 개요

CIE는 소셜 미디어 트렌드를 자동 수집하고, 플랫폼 규제를 점검한 뒤, 최적화된 콘텐츠를 생성하는 4단계 자동화 파이프라인입니다.

```
트렌드 수집 → 규제 점검 → 콘텐츠 생성/QA → 저장/발행
```

## 지원 플랫폼

| 플랫폼 | 트렌드 수집 | 규제 점검 | 콘텐츠 생성 |
|--------|-----------|----------|-----------|
| X (Twitter) | ✅ getdaytrends DB + LLM | ✅ Shadowban/알고리즘 | ✅ 단문/장문/쓰레드 |
| Threads | ✅ LLM 분석 | ✅ Meta 정책 | ✅ 공감형/인사이트형 |
| 네이버 블로그 | ✅ DataLab API + LLM | ✅ C-Rank/D.I.A. | ✅ SEO 최적화 블로그 |

## 빠른 시작

```bash
# 1. .env 설정
cp .env.example .env
# .env 파일에서 프로젝트 정보 입력

# 2. 드라이런 (구조 검증)
python main.py --dry-run --verbose

# 3. 트렌드 수집만
python main.py --mode trend

# 4. 전체 파이프라인
python main.py --mode full --verbose

# 5. 월간 회고
python main.py --mode review
```

## 실행 모드

| 모드 | 설명 | 주기 |
|------|------|------|
| `--mode trend` | 트렌드 수집만 | 매주 월요일 |
| `--mode regulation` | 규제 점검만 | 콘텐츠 제작 전 |
| `--mode full` | 전체 파이프라인 | 콘텐츠 제작 시 |
| `--mode review` | 월간 회고 | 매월 말 |

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

## 기존 인프라 연동

- **`shared/llm`**: 통합 LLM 클라이언트 (Tier 라우팅, 폴백, 비용 추적)
- **`getdaytrends`**: X 트렌드 DB 재활용
- **Notion Content Hub**: 콘텐츠 관리 대시보드
