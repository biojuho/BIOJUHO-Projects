# GitHub MCP 설정 가이드

## MCP settings.json에 추가할 내용

IDE의 MCP 설정 파일에 아래 내용을 추가하세요:

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

## 테스트 방법

1. IDE 재시작
2. MCP 연결 상태 확인
3. GitHub 관련 명령어 테스트

## 사용 가능한 기능

- 리포지토리 목록 조회
- 이슈 생성/관리
- PR 생성/관리
- 파일 읽기/쓰기
- 브랜치 관리
