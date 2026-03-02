# Notion MCP Server for Antigravity

Antigravity(또는 Gemini)와 같은 AI 모델이 사용자의 **Notion 페이지를 검색하고 내용을 읽을 수 있도록** 도와주는 MCP(Model Context Protocol) 서버입니다.  
This is a Model Context Protocol (MCP) server that helps AI models like Antigravity (or Gemini) **search and read contents from users' Notion pages**.

이 프로젝트를 통해 AI에게 "내 노션에서 회의록 찾아줘"와 같은 질문을 할 수 있습니다.  
With this project, you can ask the AI questions like "Find the meeting minutes in my Notion."

---

## ✨ 주요 기능 (Key Features)

- **🔍 검색 (`search_notion`)**: 키워드로 Notion 페이지를 검색하여 제목, ID, URL을 반환합니다.
- **🔍 Search (`search_notion`)**: Searches Notion pages by keyword and returns titles, IDs, and URLs.
<br>

- **📖 읽기 (`read_page`)**: 특정 페이지의 내용을 텍스트로 읽어옵니다. (현재 텍스트, 헤딩, 리스트 지원)
- **📖 Read (`read_page`)**: Reads the content of a specific page as text. (Currently supports text, headings, and lists)

---

## 🛠 설치 및 실행 방법 (Installation & Usage)

### 1. 사전 준비 (Prerequisites)
- Python 3.10 이상 (Python 3.10 or higher)
- Notion API Key (Integration Secret)

### 2. 설치 (Installation)
```bash
# 저장소 클론 (Clone the repository)
git clone https://github.com/byulsi/MCP_notion-antigravity.git
cd MCP_notion-antigravity

# 가상환경 생성 및 활성화 (Create and activate a virtual environment)
python3 -m venv venv
source venv/bin/activate

# 의존성 설치 (Install dependencies)
pip install -r requirements.txt
```

### 3. 환경 설정 (Environment Setup - .env)
프로젝트 루트에 `.env` 파일을 생성하고 Notion API 키를 입력하세요.  
Create a `.env` file in the project root and enter your Notion API key.
```bash
NOTION_API_KEY=secret_your_notion_api_key_here
```
> **주의 (Note)**: 검색하려는 Notion 페이지에 해당 봇(Integration)이 초대되어 있어야 합니다.  
> The bot (Integration) must be invited to the Notion pages you wish to search.

### 4. 실행 (Running the Server)
```bash
# 간편 실행 스크립트 사용 (Use the convenience script)
./run_server.sh
```

### 5. 테스트 및 모의 DB 구축 (Mock DB Setup for Testing)
안전한 모의 환경에서 에이전트를 테스트하고 싶다면, 제공되는 모의 데이터베이스 파이프라인을 사용하세요.
If you want to test agents in a safe sandbox, use the provided mock database pipeline.

1. `.env.example` 파일을 복사하여 새로운 테스트용 `.env` 파일을 구성합니다.
   Copy `.env.example` and set `NOTION_MOCK_DB_ID` to your test database.
2. 로컬 SQLite 상태 확인용 DB를 초기화합니다.
   Run the initialization script.
```bash
python init_mock_db.py --reset --posts 25 --trends 8
```

---

## 🔌 Antigravity 연동 (Antigravity Integration)

Antigravity 설정 파일(`~/.gemini/antigravity/mcp_config.json`)에 다음 내용을 추가하세요.  
Add the following to your Antigravity configuration file (`~/.gemini/antigravity/mcp_config.json`).

```json
{
  "mcpServers": {
    "notion-server": {
      "command": "/absolute/path/to/MCP_notion-antigravity/run_server.sh",
      "args": [],
      "cwd": "/absolute/path/to/MCP_notion-antigravity"
    }
  }
}
```
*`/absolute/path/to/...` 부분을 실제 프로젝트 경로로 변경해주세요.*  
*Replace `/absolute/path/to/...` with the actual path to your project.*

---

## 📝 라이선스 (License)
MIT License
