# 🐦 X 트렌드 자동 트윗 생성기

> 2시간마다 한국 X(트위터) 실시간 트렌드를 수집해 Claude AI로 5종 트윗 시안을 자동 생성하고,
> Notion 또는 Google Sheets에 저장하는 자동화 봇

---

## 📁 파일 구조

```
twitter_auto/
├── main.py              ← 메인 실행 파일
├── requirements.txt     ← 의존 패키지
├── .env.example         ← 환경변수 템플릿
├── .env                 ← 실제 API 키 입력 (직접 생성)
├── SETUP_GUIDE.md       ← Notion / Google Sheets 세팅 가이드
└── tweet_bot.log        ← 실행 로그 (자동 생성)
```

---

## ⚡ 빠른 시작

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정
```bash
cp .env.example .env
# .env 파일을 열어 API 키 입력
```

### 3. 실행
```bash
python main.py
```

---

## 🔑 필요한 API 키

| 키 | 발급처 | 필수 여부 |
|---|---|---|
| Anthropic API Key | https://console.anthropic.com | ✅ 필수 |
| Notion Integration Token | https://notion.so/my-integrations | Notion 사용 시 |
| Google Service Account JSON | https://console.cloud.google.com | Google Sheets 사용 시 |

---

## ⚙️ 주요 설정 (.env)

| 항목 | 기본값 | 설명 |
|---|---|---|
| STORAGE_TYPE | notion | `notion` 또는 `google_sheets` |
| SCHEDULE_INTERVAL_MINUTES | 120 | 실행 간격 (분) |
| TONE | 친근하고 위트 있는 동네 친구 | 트윗 톤앤매너 |

---

## 📊 Notion DB에 저장되는 내용

| 컬럼 | 내용 |
|---|---|
| 제목 | [트렌드 #순위] 주제 — 생성시각 |
| 공감유도형 | 트윗 시안 1 |
| 꿀팁형 | 트윗 시안 2 |
| 찬반질문형 | 트윗 시안 3 |
| 명언형 | 트윗 시안 4 |
| 유머밈형 | 트윗 시안 5 |
| 상태 | 대기중 / 게시완료 |

---

## 🔄 동작 흐름

```
실행
 │
 ▼
getdaytrends.com 스크래핑 → 실시간 트렌드 TOP 3 수집
 │
 ▼
각 트렌드별 Claude AI 호출 → 5종 트윗 시안 생성 (JSON)
 │
 ▼
Notion DB 또는 Google Sheets에 저장
 │
 ▼
120분 대기 → 반복
```

---

## 🛑 종료
실행 중 `Ctrl + C`로 종료

---

## 📝 세팅 가이드
→ [SETUP_GUIDE.md](./SETUP_GUIDE.md) 참고
