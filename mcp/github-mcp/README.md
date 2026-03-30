# GitHub MCP 설정 가이드 (GitHub MCP Setup Guide)

## ⚙️ MCP settings.json에 추가할 내용 (Configuration for settings.json)

IDE의 MCP 설정 파일에 아래 내용을 추가하세요:
Add the following content to your IDE's MCP configuration file:

```json
{
  "mcpServers": {
    "github": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "YOUR_GITHUB_PAT_HERE"
      }
    }
  }
}
```

## 🧪 테스트 방법 (Testing Methodology)

1. IDE 재시작 (Restart IDE)
2. MCP 연결 상태 확인 (Verify MCP connection status)
3. GitHub 관련 명령어 테스트 (Test GitHub-related commands)

## ✨ 사용 가능한 기능 (Available Features)

- 리포지토리 목록 조회 (List repositories)
- 이슈 생성/관리 (Create/manage issues)
- PR 생성/관리 (Create/manage Pull Requests)
- 파일 읽기/쓰기 (Read/write files)
- 브랜치 관리 (Manage branches)
