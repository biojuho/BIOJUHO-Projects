# 📋 Notion 데이터베이스 세팅 가이드

## 1단계 — Notion Integration 생성
1. https://www.notion.so/my-integrations 접속
2. [+ New integration] 클릭
3. 이름: "트윗 자동화 봇" 입력
4. Submit → **Internal Integration Token** 복사 → `.env`의 `NOTION_TOKEN`에 붙여넣기

---

## 2단계 — Notion 데이터베이스 생성

새 페이지에서 `/database` 입력 후 **Table** 선택.

아래 속성들을 생성하세요:

| 속성 이름     | 속성 타입  | 비고               |
|-------------|----------|------------------|
| 제목         | Title    | 기본 생성됨         |
| 주제         | Text     |                  |
| 순위         | Number   |                  |
| 생성시각      | Date     |                  |
| 공감유도형    | Text     |                  |
| 꿀팁형       | Text     |                  |
| 찬반질문형    | Text     |                  |
| 명언형       | Text     |                  |
| 유머밈형     | Text     |                  |
| 상태         | Select   | 옵션: 대기중, 게시완료 |

---

## 3단계 — Integration을 데이터베이스에 연결
1. 데이터베이스 우측 상단 **[...]** 클릭
2. **Connections** → 생성한 Integration 추가

---

## 4단계 — Database ID 복사
데이터베이스 URL 예시:
```
https://www.notion.so/myworkspace/abc1234def5678abc1234def5678?v=xxx
```
`/` 뒤, `?` 앞의 **32자리** → `.env`의 `NOTION_DATABASE_ID`에 입력


# 📊 Google Sheets 세팅 가이드 (Notion 대신 사용 시)

## 1단계 — Google Cloud 서비스 계정 생성
1. https://console.cloud.google.com 접속
2. 새 프로젝트 생성
3. [API 및 서비스] → [사용 설정된 API] → Google Sheets API & Google Drive API 활성화
4. [사용자 인증 정보] → [서비스 계정] → 새 서비스 계정 생성
5. JSON 키 다운로드 → `credentials.json`으로 저장 (main.py와 같은 폴더)

## 2단계 — 스프레드시트 공유
1. 새 Google 스프레드시트 생성
2. 우측 상단 공유 → 서비스 계정 이메일 추가 (편집자 권한)
3. 스프레드시트 URL에서 ID 복사 → `.env`의 `GOOGLE_SHEET_ID`에 입력

## 3단계 — .env 수정
```
STORAGE_TYPE=google_sheets
GOOGLE_SERVICE_ACCOUNT_JSON=credentials.json
GOOGLE_SHEET_ID=your_sheet_id
```
