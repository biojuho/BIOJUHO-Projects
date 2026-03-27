# AI Projects Workspace - 종합 시스템 점검 프롬프트

현재 날짜: 2026-03-22

## 점검 대상 시스템 개요

다음은 다중 프로젝트 모노레포 구조의 AI 프로젝트 워크스페이스입니다. 종합적인 시스템 점검을 수행해주세요.

---

## 1. 프로젝트 구성

### 주요 프로젝트 (5개)

| 프로젝트 | 기술 스택 | 포트 | 목적 |
|---------|----------|------|------|
| **desci-platform/biolinker** | FastAPI + ChromaDB + LangChain | 8000 | RFP 매칭 AI 에이전트 API |
| **desci-platform/frontend** | React 19 + Vite 7 + Tailwind | 5173 | DeSci 플랫폼 웹 UI |
| **desci-platform/contracts** | Hardhat + Solidity 0.8.20 | - | ERC20 (DeSciToken) + ERC721 (ResearchPaperNFT) 스마트 컨트랙트 |
| **AgriGuard/backend** | FastAPI + SQLAlchemy + Web3 | 8002 | 농업 공급망 추적 시스템 |
| **DailyNews** | Python + Notion API + LLM | - | X(트위터) 성장 엔진 + Notion 자동화 |

### MCP 서버 (6개)

| MCP 서버 | 언어/프레임워크 | 목적 |
|---------|---------------|------|
| `canva-mcp` | TypeScript/Node | Canva Connect API 디자인 자동화 |
| `github-mcp` | Python | 저장소 생성 및 메타데이터 관리 |
| `notebooklm-mcp` | Python | Google NotebookLM 리서치 |
| `telegram-mcp` | Python/FastMCP | Telegram 알림 및 승인 (7개 도구) |
| `desci-research-mcp` | Python/FastMCP | arXiv/Semantic Scholar 학술 검색 |
| `DailyNews/src/antigravity_mcp` | Python/FastMCP | 콘텐츠 발행 파이프라인 (15개 도구) |

### 자동화 스크립트

- `scripts/orchestrator.py` - 크로스 프로젝트 파이프라인 (수집→검증→생성→발행→추적)
- `scripts/cost_intelligence.py` - LLM 비용 분석, 예측, 최적화 제안
- `scripts/linear_sync.py` - ROADMAP.md → Linear 이슈 동기화
- `scripts/check_security.py` - 시크릿/API 키 스캐너 (pre-commit, Claude Code Hooks용)
- `getdaytrends/firecrawl_bridge.py` - Firecrawl 통합 (트렌드 컨텍스트 수집)
- `getdaytrends/firecrawl_client.py` - Firecrawl API 비동기 클라이언트 (rate limiting)

### 커스텀 스킬 (`.agent/skills/`)

- `cost-intelligence` - LLM 비용 보고서 및 최적화
- `content-performance` - 발행된 콘텐츠 성능 추적 및 피드백 루프
- `content-publisher` - Notion/Markdown → Blog/Newsletter 변환
- `deep-research` - 멀티 소스 딥 리서치
- `project-organizer` - 프로젝트 폴더 조직화 및 히스토리
- `web-auditor` - SEO 및 성능 감사
- `youtube-intelligence` - YouTube 비디오 트랜스크립트 분석

---

## 2. 최근 Git 상태

**현재 브랜치**: `main` (origin/main과 동기화됨)

**최근 커밋** (5c6e287):
```
fix: test improvements + QC updates + Badge component
```

**수정된 파일 (미스테이징)**:
```
.claude/settings.local.json
DailyNews/src/antigravity_mcp/integrations/llm_adapter.py
DailyNews/src/antigravity_mcp/pipelines/analyze.py
DailyNews/src/antigravity_mcp/state/mixins.py
DailyNews/tests/unit/test_pipelines.py
shared/llm/config.py
```

**추적되지 않은 파일**:
```
DailyNews/output/daily_tweets_2026-03-22_test.txt
```

---

## 3. 환경 변수 및 보안

### 주요 환경 변수 (`.env.example` 파일 기준)

- **LLM API 키**: `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`
- **Firebase**: `VITE_FIREBASE_*` (프론트엔드), `GOOGLE_APPLICATION_CREDENTIALS` (백엔드)
- **블록체인**: `PRIVATE_KEY` (컨트랙트 배포)
- **IPFS**: `PINATA_API_KEY`, `PINATA_API_SECRET`
- **외부 서비스**: `FIRECRAWL_API_KEY`, `TELEGRAM_BOT_TOKEN`, `LINEAR_API_KEY`
- **모니터링**: `SENTRY_DSN`
- **개발 모드**: `ALLOW_TEST_BYPASS=true`

### 보안 체크리스트
- [ ] `.env` 파일들이 `.gitignore`에 포함되어 있는가?
- [ ] `scripts/check_security.py`가 정상 작동하는가?
- [ ] 하드코딩된 API 키가 없는가?
- [ ] Firebase 서비스 계정 JSON이 안전하게 관리되고 있는가?

---

## 4. 코드 스타일 및 규칙

### Python (3.12 / 3.13)
- **이유**: `langchain`/`google.genai` 라이브러리가 Python 3.14+와 호환 문제
- **타입 힌팅**: 서드파티 라이브러리에 `# type: ignore` 사용 허용
- **디자인 패턴**: `get_*()` 팩토리 함수를 통한 싱글톤 패턴

### React (프론트엔드)
- **컴포넌트**: 함수형 컴포넌트만 사용
- **스타일링**: Tailwind CSS
- **애니메이션**: Framer Motion
- **ID 생성**: `useId()` 사용 (`Math.random()` 금지)

### Solidity (스마트 컨트랙트)
- **OpenZeppelin**: v5 컨트랙트 사용
- **Pragma**: `^0.8.20`
- **테스트**: Hardhat

### 에러 핸들링
- **FastAPI**: DB 작업을 `try/except` 블록으로 감싸고 `db.rollback()` 호출
- **React**: `ErrorBoundary` + `ToastContext` 사용

---

## 5. 알려진 이슈 및 주의사항 (Gotchas)

1. **vector_store.py**: `search_similar()`가 `List[Tuple[RFPDocument, float]]` 반환
   - 항상 `for doc, score in results`로 언팩 필요

2. **biolinker CORS**: 개발 환경에서는 localhost 기본값
   - 프로덕션: `ENV=production` + `ALLOWED_ORIGINS` 설정 필요

3. **DeSciToken.sol**: `contracts/` 루트에 위치 (`contracts/contracts/` 아님)
   - 이전 마이그레이션으로 인한 구조

4. **DailyNews .env**: 실제 API 키 포함
   - 절대 커밋 금지 (`.gitignore`로 보호됨)

5. **React 버전**: React 19 + React Router 7
   - 의존성 업데이트 시 호환성 확인 필수

6. **AgriGuard DB**: SQLite (`agriguard.db`) 사용
   - 프로덕션 환경에서 동시성 문제 가능성

---

## 6. 점검 요청 사항

다음 영역에 대해 종합적인 시스템 점검을 수행하고, 각 항목별로 **문제점**, **권장사항**, **우선순위**를 제시해주세요.

### A. 아키텍처 및 구조
- [ ] 모노레포 구조의 적절성 (프로젝트 간 의존성, 코드 재사용성)
- [ ] 마이크로서비스 아키텍처 패턴 준수 여부
- [ ] MCP 서버들의 역할 분리 및 중복 검사
- [ ] 프론트엔드-백엔드 API 계약 (OpenAPI/Swagger 사용 여부)

### B. 코드 품질 및 유지보수성
- [ ] 코딩 스타일 일관성 (Python PEP8, React Best Practices)
- [ ] 테스트 커버리지 (단위 테스트, 통합 테스트, E2E)
- [ ] 문서화 수준 (README, API 문서, 인라인 주석)
- [ ] 타입 안전성 (Python type hints, TypeScript 사용 여부)
- [ ] 린팅 및 포맷팅 도구 설정 (ESLint, Prettier, Black, Ruff 등)

### C. 보안
- [ ] 환경 변수 관리 (`.env` 파일, 시크릿 관리 도구)
- [ ] API 키 노출 위험 (하드코딩, 로그 출력, 프론트엔드 번들)
- [ ] 인증/인가 구현 (Firebase Auth, JWT 토큰 관리)
- [ ] CORS 정책 (개발/프로덕션 환경 분리)
- [ ] 스마트 컨트랙트 보안 (Reentrancy, Overflow, Access Control)
- [ ] 의존성 취약점 (`npm audit`, `pip-audit`, Dependabot)

### D. 성능 및 확장성
- [ ] 데이터베이스 선택 (SQLite → PostgreSQL 마이그레이션 필요성)
- [ ] 벡터 DB 성능 (ChromaDB vs Qdrant, 인메모리 폴백 전략)
- [ ] LLM API 호출 최적화 (캐싱, 배치 처리, 비용 관리)
- [ ] 프론트엔드 번들 크기 (Vite 빌드 최적화, 코드 스플리팅)
- [ ] API 응답 시간 (비동기 처리, 백그라운드 작업)

### E. DevOps 및 배포
- [ ] Docker/Docker Compose 설정 (컨테이너화 수준)
- [ ] CI/CD 파이프라인 (GitHub Actions, 자동 테스트, 배포)
- [ ] 로깅 및 모니터링 (Sentry, 로그 수준, 중앙화)
- [ ] 환경 분리 (개발/스테이징/프로덕션)
- [ ] 백업 및 재해 복구 계획

### F. 의존성 관리
- [ ] Python 버전 제약 (3.12/3.13, 3.14+ 호환성 로드맵)
- [ ] npm 패키지 업데이트 (React 19, Vite 7 최신 버전 추적)
- [ ] 라이브러리 라이선스 검토
- [ ] 사용하지 않는 의존성 정리

### G. 자동화 및 워크플로우
- [ ] `scripts/orchestrator.py` 파이프라인 안정성
- [ ] `scripts/cost_intelligence.py` 비용 최적화 효과
- [ ] Windows Task Scheduler 작업 (DailyNews 인사이트 생성)
- [ ] Git Hooks (pre-commit, 보안 스캐너)
- [ ] Linear 동기화 자동화

### H. 데이터 및 스토리지
- [ ] IPFS 업로드 전략 (Pinata, 대안 검토)
- [ ] Notion API 사용량 및 제한
- [ ] 로컬 파일 스토리지 관리 (`DailyNews/output/`, 임시 파일)
- [ ] 데이터 마이그레이션 계획

### I. 비용 최적화
- [ ] LLM API 비용 (Gemini vs OpenAI vs DeepSeek)
- [ ] Firebase 무료 티어 제한
- [ ] Firecrawl API 크레딧 소진율
- [ ] GitHub LFS 스토리지 (해당 시)

### J. 사용자 경험 (UX/UI)
- [ ] 프론트엔드 접근성 (ARIA, 키보드 내비게이션)
- [ ] 모바일 반응형 디자인
- [ ] 로딩 상태 및 에러 메시지
- [ ] 다국어 지원 (i18n) 준비 여부

---

## 7. 출력 형식 요청

다음 구조로 점검 결과를 작성해주세요:

```markdown
# AI Projects Workspace - 시스템 점검 보고서

## 요약 (Executive Summary)
- 전체 건강도 점수: X/100
- 주요 강점 3가지
- 치명적 이슈 (Critical Issues)
- 권장 개선 작업 우선순위 Top 5

## 상세 점검 결과

### [영역 A] 아키텍처 및 구조
- **현황**: ...
- **문제점**: ...
- **권장사항**: ...
- **우선순위**: High/Medium/Low

(B ~ J 영역 반복)

## 즉시 조치 필요 항목 (Action Items)
1. [Critical] ...
2. [High] ...
3. [Medium] ...

## 장기 개선 로드맵 (3개월/6개월/12개월)
- 3개월: ...
- 6개월: ...
- 12개월: ...

## 참고 자료 및 도구 추천
- 보안: ...
- 성능 모니터링: ...
- 테스트: ...
```

---

## 8. 추가 컨텍스트

### 최근 수정 파일 (분석 힌트)

1. **LLM 관련 파일**:
   - `DailyNews/src/antigravity_mcp/integrations/llm_adapter.py`
   - `shared/llm/config.py`

2. **파이프라인 및 상태 관리**:
   - `DailyNews/src/antigravity_mcp/pipelines/analyze.py`
   - `DailyNews/src/antigravity_mcp/state/mixins.py`

3. **테스트**:
   - `DailyNews/tests/unit/test_pipelines.py`

4. **설정**:
   - `.claude/settings.local.json`

---

## 9. 특별 요청

1. **보안 스캔**: 수정된 파일들에서 하드코딩된 시크릿이나 잘못된 환경 변수 사용이 있는지 검토
2. **LLM 비용**: `shared/llm/config.py` 변경 사항이 비용 최적화에 미치는 영향 분석
3. **테스트 전략**: `DailyNews/tests/unit/test_pipelines.py`의 테스트 커버리지 및 품질 평가
4. **설정 관리**: `.claude/settings.local.json` 변경 사항이 워크플로우에 미치는 영향

---

**점검 수행 시 주의사항**:
- 실제 파일을 확인할 수 없으므로, 제공된 정보와 일반적인 모범 사례를 기반으로 평가
- 각 권장사항에 대해 구체적인 도구/라이브러리/방법론 제시
- 산업 표준 및 최신 트렌드를 고려한 조언 (2026년 기준)

이 프롬프트를 기반으로 종합적이고 실행 가능한 시스템 점검 보고서를 작성해주세요.
