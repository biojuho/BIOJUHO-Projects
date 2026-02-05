# Notion MCP Server for Antigravity

Antigravity(또는 Gemini)와 같은 AI 모델이 사용자의 **Notion 페이지를 검색하고 내용을 읽을 수 있도록** 도와주는 MCP(Model Context Protocol) 서버입니다.

이 프로젝트를 통해 AI에게 "내 노션에서 회의록 찾아줘"와 같은 질문을 할 수 있습니다.

## ✨ 주요 기능

- **🔍 검색 (`search_notion`)**: 키워드로 Notion 페이지를 검색하여 제목, ID, URL을 반환합니다.
- **📖 읽기 (`read_page`)**: 특정 페이지의 내용을 텍스트로 읽어옵니다. (현재 텍스트, 헤딩, 리스트 지원)

## 🛠 설치 및 실행 방법

### 1. 사전 준비
- Python 3.10 이상
- Notion API Key (Integration Secret)

### 2. 설치
```bash
# 저장소 클론
git clone https://github.com/byulsi/MCP_notion-antigravity.git
cd MCP_notion-antigravity

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 3. 환경 설정 (.env)
프로젝트 루트에 `.env` 파일을 생성하고 Notion API 키를 입력하세요.
```bash
NOTION_API_KEY=secret_your_notion_api_key_here
```
> **주의**: 검색하려는 Notion 페이지에 해당 봇(Integration)이 초대되어 있어야 합니다.

### 4. 실행
```bash
# 간편 실행 스크립트 사용
./run_server.sh
```

## 🔌 Antigravity 연동

Antigravity 설정 파일(`~/.gemini/antigravity/mcp_config.json`)에 다음 내용을 추가하세요.

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

## 📝 라이선스
MIT License
