# Contributing to AI 프로젝트 Workspace

이 워크스페이스는 7개의 프로젝트를 포함합니다.

## 프로젝트 구조

| 프로젝트 | 경로 | 기술 스택 |
| :--- | :--- | :--- |
| AgriGuard | `AgriGuard/` | React 19 + FastAPI + Solidity |
| DeSci Platform | `desci-platform/` | React 19 + FastAPI + Firebase |
| MCP Notion | `DailyNews/` | Python + MCP SDK |
| GetDayTrends | `getdaytrends/` | Python + Anthropic + Notion |
| Canva MCP | `canva-mcp/` | TypeScript + React 19 + MCP SDK |
| NotebookLM MCP | `notebooklm-mcp/` | Python |
| GitHub MCP | `github-mcp/` | Python |

## 개발 환경 설정

### 필수 요구사항
- **Node.js**: ≥20.19, <24 (LTS 22 권장)
- **Python**: 3.13+ (`.venv` 사용)
- **npm**: ≥10

### 초기 설정
```bash
# 1. 루트 .env 파일 생성 (.env.example 참고)
cp .env.example .env

# 2. Python 가상환경
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 3. 프런트엔드 의존성
cd AgriGuard/frontend && npm install
cd ../../desci-platform/frontend && npm install
```

## 코드 품질 기준

### 프런트엔드 (React)
- **ESLint**: `npm run lint` — 0 errors, 0 warnings 필수
- **Tests**: `npm run test` — 모든 유닛 테스트 통과
- **Build**: `npm run build:lts` — Node 22 기준 빌드 성공
- **Bundle**: `npm run check:bundle` — 최대 청크 ≤500KB, 엔트리 ≤260KB

### 백엔드 (Python)
- **pytest**: `python -m pytest -q` — 라벨 `not integration` 기본 실행
- **Type check**: pyright/mypy 오류 없이 통과 (권장)

## 커밋 규칙

```
[Project] 변경 내용 요약

예시:
[AgriGuard] Add code-splitting with React.lazy
[DeSci] Fix lint warnings in Badge/Button/Input
[MCP Notion] Update news bot scheduling
```

## 환경 변수 보안

> ⚠️ **절대** `.env` 파일을 커밋하지 마세요.

- 모든 프로젝트의 `.gitignore`에 `.env`, `.env.*`, `!.env.example` 패턴이 포함되어 있습니다
- 새 API 키 추가 시 `.env.example`에 플레이스홀더도 함께 추가하세요
- 커밋 전 `git status`로 `.env` 파일이 staging 되지 않았는지 확인

## 워크스페이스 검증

전체 프로젝트 스모크 테스트:

```bash
python scripts/run_workspace_smoke.py --scope all --json-out smoke-all.json
```

## 공유 모듈 (shared/)

| 모듈 | 용도 |
| :--- | :--- |
| `shared/llm/` | 통합 LLM 인터페이스 (3-tier 폴백 체인) |
| `shared/config.py` | .env 로딩 + 프로젝트 디렉터리 탐지 |
| `shared/logging.py` | 통합 로깅 포맷 |
