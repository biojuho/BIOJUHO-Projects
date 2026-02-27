# X 트렌드 자동 트윗 생성기 v2.0

> 멀티소스 트렌드 수집 + 바이럴 스코어링 + Claude AI 트윗/쓰레드 생성 + 자동 저장 + 알림

---

## v2.0 주요 변경사항

| 기능 | v1.0 | v2.0 |
|------|------|------|
| 데이터 소스 | getdaytrends.com만 | + X API v2, Reddit, Google News |
| 트렌드 분석 | 없음 | 바이럴 스코어링 (0-100점) |
| 트윗 생성 | 주제명만 입력 | 멀티소스 컨텍스트 + 스코어링 기반 |
| 쓰레드 | 없음 | 바이럴 80점+ 자동 생성 |
| 히스토리 | 없음 | SQLite DB (패턴 감지) |
| 알림 | 없음 | Telegram / Discord |
| CLI | 없음 | --country, --one-shot, --dry-run 등 |
| 구조 | 단일 파일 | 8개 모듈 분리 |

---

## 파일 구조

```
getdaytrends/
├── main.py          # CLI 진입점 + 파이프라인 오케스트레이터
├── config.py        # 환경변수/설정 관리
├── models.py        # 데이터 모델 (dataclass)
├── scraper.py       # 멀티소스 트렌드 수집
├── analyzer.py      # 바이럴 스코어링 (Claude Haiku)
├── generator.py     # 트윗/쓰레드 생성 (Claude Sonnet)
├── storage.py       # Notion + Google Sheets + SQLite 저장
├── alerts.py        # Telegram/Discord 알림
├── db.py            # SQLite 초기화/헬퍼
├── requirements.txt # 의존 패키지
├── .env.example     # 환경변수 템플릿
└── data/
    └── getdaytrends.db  # (자동생성) 트렌드 히스토리 DB
```

---

## 빠른 시작

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일을 열어 ANTHROPIC_API_KEY 입력

# 3. 실행
python main.py --one-shot          # 1회 실행
python main.py                      # 2시간마다 자동 실행
```

---

## CLI 사용법

```bash
# 기본 실행 (2시간 스케줄)
python main.py

# 1회 실행 후 종료
python main.py --one-shot

# 수집 + 분석만 (저장 안 함)
python main.py --one-shot --dry-run

# 미국 트렌드 Top 10 처리
python main.py --one-shot --country us --limit 10

# 상세 로그 + 알림 끄기
python main.py --one-shot --verbose --no-alerts

# 스케줄 간격 변경 (30분마다)
python main.py --schedule-min 30

# 히스토리 통계 확인
python main.py --stats
```

### CLI 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--country` | 국가 코드 (korea, us, japan, uk, india, global) | korea |
| `--limit` | 처리할 트렌드 수 | 5 |
| `--one-shot` | 1회 실행 후 종료 | false |
| `--dry-run` | 수집+분석만 (외부 저장 안 함) | false |
| `--verbose` | 상세 로그 출력 | false |
| `--no-alerts` | 알림 전송 안 함 | false |
| `--schedule-min` | 스케줄 간격(분) 오버라이드 | 120 |
| `--stats` | 히스토리 통계 출력 후 종료 | false |

---

## 데이터 플로우

```
scraper.py
  getdaytrends.com ──┐
  X API v2 ──────────┤
  Reddit ────────────┼──→ [트렌드 + 컨텍스트]
  Google News ───────┘         │
                               ▼
                        analyzer.py
                    (Claude Haiku 스코어링)
                               │
                    [ScoredTrend: 0-100점]
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
              alerts.py   generator.py  db.py
          (Telegram/Discord) (Claude)  (SQLite)
                               │
                          [TweetBatch]
                          (5종 + 쓰레드)
                               │
                               ▼
                         storage.py
                    ┌──────┬──────┐
                    ▼      ▼      ▼
                 Notion  Sheets  SQLite
```

---

## 필요한 API 키

| 키 | 발급처 | 필수 |
|---|---|---|
| Anthropic API Key | https://console.anthropic.com | 필수 |
| Notion Integration Token | https://notion.so/my-integrations | Notion 사용 시 |
| Google Service Account JSON | https://console.cloud.google.com | Google Sheets 사용 시 |
| Twitter Bearer Token | https://developer.twitter.com | 선택 (없어도 동작) |
| Telegram Bot Token | @BotFather | 선택 |
| Discord Webhook URL | 서버 설정 > 연동 > 웹훅 | 선택 |

---

## Notion DB 구조

| 컬럼 | 타입 | 내용 |
|------|------|------|
| 제목 | title | [트렌드 #순위] 주제 - 시각 |
| 주제 | rich_text | 트렌드 키워드 |
| 순위 | number | 바이럴 점수 기반 순위 |
| 생성시각 | date | ISO 8601 |
| 공감유도형 | rich_text | 트윗 시안 1 |
| 꿀팁형 | rich_text | 트윗 시안 2 |
| 찬반질문형 | rich_text | 트윗 시안 3 |
| 명언형 | rich_text | 트윗 시안 4 |
| 유머밈형 | rich_text | 트윗 시안 5 |
| 바이럴점수 | number | 0-100 (v2.0 신규) |
| 쓰레드 | rich_text | 멀티트윗 쓰레드 (v2.0 신규) |
| 상태 | select | 대기중 / 게시완료 |

---

## 종료
실행 중 `Ctrl + C`로 종료

---

## 세팅 가이드
→ [SETUP_GUIDE.md](./SETUP_GUIDE.md) 참고
