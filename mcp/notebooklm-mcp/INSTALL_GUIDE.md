# NotebookLM MCP 설치 가이드

## 다른 컴퓨터에 설치하기

### 1단계: 폴더 복사
```
notebooklm-mcp 폴더 전체를 복사 (venv 제외)
필요 파일:
- credentials.json
- install.bat
- requirements.txt
- authenticate_notebooklm.bat
- run_notebooklm.bat
```

### 2단계: 설치 실행
```batch
cd notebooklm-mcp
install.bat
```

### 3단계: 인증
```batch
authenticate_notebooklm.bat
```
브라우저가 열리면 Google 계정으로 로그인

### 4단계: MCP 설정 (settings.json)
```json
{
  "mcpServers": {
    "notebooklm": {
      "command": "python",
      "args": ["-m", "notebooklm_mcp"],
      "cwd": "C:/경로/notebooklm-mcp",
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "C:/경로/notebooklm-mcp/credentials.json"
      }
    }
  }
}
```

### 5단계: 테스트
```batch
run_notebooklm.bat
```

## 필수 조건
- Python 3.10+
- Google Cloud 프로젝트 (동일 credentials.json 사용 가능)
