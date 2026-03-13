# Skills & MCP 도입 기획안 v2.0

> 작성일: 2026-03-12 (v2.0 업데이트)
> 대상: AI 프로젝트 모노레포 (DeSci, AgriGuard, DailyNews, GetDayTrends, Content-Intelligence)
> 전체 기획 상세: [skills_mcp_assessment.md](../../.gemini/antigravity/brain/a2892ac4-3155-462a-b5e6-31713c82306f/skills_mcp_assessment.md)

---

## 1. 현황 요약

### MCP 서버 (6개)

| MCP Server | Stack | 상태 | 용도 |
|------------|-------|------|------|
| canva-mcp | TS/Node | ⚠️ 부분활성 | Canva Connect API 디자인 |
| github-mcp | Node.js | ✅ 활성 | 리포 생성/메타데이터 |
| notebooklm-mcp | Python | ✅ 활성 | Google NotebookLM |
| telegram-mcp | Python/FastMCP | ⚠️ 미완성 | Telegram 알림 |
| desci-research-mcp | Python/FastMCP | ⚠️ 미완성 | 학술 검색 |
| antigravity-mcp | Python/FastMCP | ✅ 운영 중 | 콘텐츠 파이프라인 (15 tools) |

### Skills (68개 설치, ~40% 활용)

- 핵심 활용 중: content-creator, deep-research, better-notion, twitter-search 등 ~27개
- 미활용: secret-hygiene, postmortem-writing, webapp-testing 등 ~25개
- 중복 과다: Notion(6개→2개 권장), Twitter(7개→3개 권장), 에이전트소셜(4개→비활성화 권장)

---

## 2. GAP 분석 핵심

### 🔴 Critical (즉시)
1. **모니터링 부재** → Telegram MCP 완성 + Sentry
2. **스케줄러 불안정** (3-Day Failure Loop) → GitHub Actions 이전
3. **DB 관리 자동화 부재** → Supabase MCP 활성화

### 🟡 High-Value (2~4주)
4. **콘텐츠 성과 추적 없음** → Content Performance Tracker Skill 신규
5. **Firecrawl 미활용** → GetDayTrends 파이프라인 연동
6. **코드 품질 수동 검증** → Claude Code Hooks 시스템

### 🟢 Nice-to-Have (5주+)
7. Linear 프로젝트 관리 활성화
8. DeSci Research MCP 완성
9. Orchestration Skill 고도화

---

## 3. 구현 로드맵

```
Phase 1 (Week 1-2): 운영 안정성
├─ Claude Code Hooks (.claude/hooks.json)
├─ Telegram MCP 완성
├─ Supabase MCP 활성화
├─ GitHub Actions 스케줄러 이전
└─ 기설치 Skills 즉시 활용 (secret-hygiene, smoke-check 등)

Phase 2 (Week 3-4): 콘텐츠 고도화
├─ Firecrawl 파이프라인 통합
├─ Content Performance Tracker Skill 개발
├─ Sentry MCP 설정
└─ Skills 중복 정리 (68개 → ~45개)

Phase 3 (Week 5-6): 개발 생산성
├─ Linear MCP 활성화
├─ DeSci Research MCP 완성
└─ Orchestration Skill 고도화

Phase 4 (Week 7+): 고급 자동화
├─ Cost Intelligence Skill 고도화
└─ AgriGuard IoT Simulator MCP
```

---

## 4. 비용 영향

| 구분 | 추가 비용 |
|------|----------|
| Phase 1 | **$0**/월 (모두 무료 티어) |
| Phase 2 | **$0~16**/월 (Firecrawl 초과 시) |
| Phase 3-4 | **$0**/월 |
| **전체** | **$0~$16/월** (기존 대비 0~8% 증가) |

---

## 5. 즉시 실행 가능 (Quick Wins)

| 작업 | 소요 | 비용 |
|------|------|------|
| secret-hygiene Hooks 연동 | 15분 | $0 |
| multi-project-smoke-check 실행 | 5분 | $0 |
| Supabase 플러그인 활성화 | 5분 | $0 |
| Linear 플러그인 활성화 | 5분 | $0 |
| windows-encoding-safe-test 적용 | 10분 | $0 |

---

## 6. 예상 KPI

| 지표 | 현재 | 목표 (전체 완료) |
|------|------|-----------------|
| 에러 인지 시간 | ~수시간 | ~즉시 |
| 스케줄러 실패율 | ~30% | <1% |
| 트렌드 소스 | 2개 | 5개+ |
| 콘텐츠 피드백 루프 | 없음 | 자동 |
| Skills 활용률 | ~40% | ~70% |

---

## 7. 리스크

1. **MCP 서버 과다** (최대 9개) → Docker Compose 프로필으로 선택 실행
2. **API Rate Limit** → per-service 세마포어 + 지수 백오프
3. **GitHub Actions 시크릿** → org-level secrets 사용
4. **Skills 관리 부담** (68개) → Phase 2에서 중복 정리
5. **cp949 인코딩** → windows-encoding-safe-test 표준화
6. **클라우드/로컬 괴리** → Docker Compose dev 프로필 미러링

> **핵심 권고**: GitHub Actions 스케줄러 이전 + Telegram MCP 완성이 가장 높은 ROI.
> "3-Day Failure Loop"를 끊는 것이 전체 시스템 안정성의 핵심.
