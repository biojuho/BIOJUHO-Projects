# 기술 부채 인벤토리 (Tech Debt Inventory)

**생성일**: 2026-03-26 07:40:08
**워크스페이스**: AI 프로젝트
**총 항목**: 62

---

## 개요

이 문서는 코드베이스에서 자동으로 수집된 기술 부채 항목(TODO, FIXME, HACK, XXX)을
우선순위 및 카테고리별로 분류한 인벤토리입니다.

### 우선순위 분류

- **P0 (Critical)**: 보안/취약점/긴급 - 즉시 수정 필요
- **P1 (High)**: 성능/버그/에러 - 2주 내 수정
- **P2 (Medium)**: 리팩토링/최적화 - 1개월 내 수정
- **P3 (Low)**: 문서화/개선 - 백로그

### 카테고리

- **security**: 보안 관련
- **performance**: 성능 관련
- **bug**: 버그 수정
- **refactor**: 리팩토링
- **documentation**: 문서화
- **testing**: 테스트
- **dependency**: 의존성 관리
- **other**: 기타

---

## 요약 통계

### 우선순위별

| 우선순위 | 항목 수 | 비율 |
|---------|--------|------|
| P0 | 0 | 0.0% |
| P1 | 6 | 9.7% |
| P2 | 0 | 0.0% |
| P3 | 56 | 90.3% |

### 카테고리별

| 카테고리 | 항목 수 |
|---------|--------|
| other | 51 |
| bug | 6 |
| documentation | 4 |
| testing | 1 |

### 프로젝트별

| 프로젝트 | 항목 수 |
|---------|--------|
| root | 21 |
| .agent | 19 |
| scripts | 7 |
| getdaytrends | 5 |
| desci-platform | 4 |
| .sessions | 3 |
| AgriGuard | 2 |
| docs | 1 |

---

## 우선순위별 상세

### P1 - 6개 항목

- **[TODO]** [QC_REPORT_2026-03-24_SYSTEM_DEBUG.md:388](QC_REPORT_2026-03-24_SYSTEM_DEBUG.md#L388)
  - Category: `bug`
  - Context: comments to Linear issues
  - Code: `- [ ] Convert TODO comments to Linear issues`

- **[TODO]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:82](SYSTEM_DEBUG_REPORT_2026-03-24.md#L82)
  - Category: `bug`
  - Context: /FIXME Comments (13 files, 23 occurrences)
  - Code: `#### 9. TODO/FIXME Comments (13 files, 23 occurrences)`

- **[TODO]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:150](SYSTEM_DEBUG_REPORT_2026-03-24.md#L150)
  - Category: `bug`
  - Context: comments to Linear issues
  - Code: `6. 🔲 Convert TODO comments to Linear issues`

- **[TODO]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:190](SYSTEM_DEBUG_REPORT_2026-03-24.md#L190)
  - Category: `bug`
  - Context: comments → Linear issues
  - Code: `- [ ] Review TODO comments → Linear issues`

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:92](TASK_COMPLETION_REPORT_2026-03-24.md#L92)
  - Category: `bug`
  - Context: → Linear Issues Migration Plan ✅
  - Code: `### 6. TODO → Linear Issues Migration Plan ✅`

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:116](TASK_COMPLETION_REPORT_2026-03-24.md#L116)
  - Category: `bug`
  - Context: s into Linear issues
  - Code: `2. Convert 3 actionable TODOs into Linear issues`

### P3 - 56개 항목

- **[TODO]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:23](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L23)
  - Category: `other`
  - Context: 로 등록. 차기 스프린트에서 진행.
  - Code: `> 30분 초과 → TODO로 등록. 차기 스프린트에서 진행.`

- **[TODO]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:93](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L93)
  - Category: `other`
  - Context: 주석 명시 |
  - Code: `| LOW | `generation/prompts.py` 마이그레이션 미완료 → 향후 작업 시 코드 위치 혼란 | 스켈레톤 파일에 TODO 주석 명시 |`

- **[TODO]** [.agent/session-history/2026-03-07.md:48](.agent/session-history/2026-03-07.md#L48)
  - Category: `other`
  - Context: 
  - Code: `## 📋 다음 TODO`

- **[TODO]** [.agent/session-history/2026-03-08.md:36](.agent/session-history/2026-03-08.md#L36)
  - Category: `other`
  - Context: 
  - Code: `## 📋 다음 TODO`

- **[TODO]** [.agent/session-history/2026-03-08.md:99](.agent/session-history/2026-03-08.md#L99)
  - Category: `other`
  - Context: 
  - Code: `### 📋 다음 세션 TODO`

- **[TODO]** [.agent/session-history/2026-03-08.md:135](.agent/session-history/2026-03-08.md#L135)
  - Category: `other`
  - Context: 
  - Code: `### 📋 다음 세션 TODO`

- **[TODO]** [.agent/session-history/2026-03-08.md:161](.agent/session-history/2026-03-08.md#L161)
  - Category: `other`
  - Context: 
  - Code: `### 📋 다음 세션 TODO`

- **[TODO]** [.agent/session-history/2026-03-08.md:184](.agent/session-history/2026-03-08.md#L184)
  - Category: `other`
  - Context: 
  - Code: `### 📋 다음 세션 TODO`

- **[TODO]** [.agent/session-history/2026-03-08.md:235](.agent/session-history/2026-03-08.md#L235)
  - Category: `other`
  - Context: 
  - Code: `### 📋 다음 세션 TODO`

- **[TODO]** [.agent/session-history/2026-03-08.md:275](.agent/session-history/2026-03-08.md#L275)
  - Category: `other`
  - Context: 
  - Code: `### 📋 다음 세션 TODO`

- **[TODO]** [.agent/session-history/2026-03-08.md:313](.agent/session-history/2026-03-08.md#L313)
  - Category: `other`
  - Context: 
  - Code: `### 📋 다음 세션 TODO`

- **[TODO]** [.agent/session-history/2026-03-21.md:36](.agent/session-history/2026-03-21.md#L36)
  - Category: `other`
  - Context: 
  - Code: `### 다음 TODO`

- **[TODO]** [.agent/session-history/2026-03-21.md:104](.agent/session-history/2026-03-21.md#L104)
  - Category: `other`
  - Context: 
  - Code: `### 다음 TODO`

- **[TODO]** [.agent/session-history/2026-03-24.md:44](.agent/session-history/2026-03-24.md#L44)
  - Category: `other`
  - Context: 
  - Code: `### 다음 TODO`

- **[TODO]** [.agent/workflows/qa-qc.md:110](.agent/workflows/qa-qc.md#L110)
  - Category: `other`
  - Context: 로 등록하고 넘어감
  - Code: `- 30분 초과 예상이면 TODO로 등록하고 넘어감`

- **[TODO]** [.agent/workflows/session-workflow.md:50](.agent/workflows/session-workflow.md#L50)
  - Category: `other`
  - Context: `
  - Code: `- `다음 TODO``

- **[TODO]** [.agent/workflows/session-workflow.md:87](.agent/workflows/session-workflow.md#L87)
  - Category: `other`
  - Context: **: [항목 나열]
  - Code: `- **미완료 TODO**: [항목 나열]`

- **[TODO]** [.agent/workflows/session-workflow.md:148](.agent/workflows/session-workflow.md#L148)
  - Category: `other`
  - Context: **: 구체적이고 실행 가능한 항목
  - Code: `- **다음 TODO**: 구체적이고 실행 가능한 항목`

- **[TODO]** [.agent/workflows/session-workflow.md:186](.agent/workflows/session-workflow.md#L186)
  - Category: `other`
  - Context: 
  - Code: `### 다음 세션 TODO`

- **[TODO]** [.sessions/README.md:49](.sessions/README.md#L49)
  - Category: `other`
  - Context: **: Handoff tasks
  - Code: `- **Next Agent TODO**: Handoff tasks`

- **[TODO]** [.sessions/SESSION_LOG_2026-03-23.md:32](.sessions/SESSION_LOG_2026-03-23.md#L32)
  - Category: `other`
  - Context: /IN_PROGRESS/DONE, priority levels, tool assignment guide
  - Code: `- **Features**: TODO/IN_PROGRESS/DONE, priority levels, tool assignment guide`

- **[TODO]** [.sessions/SESSION_LOG_2026-03-23.md:160](.sessions/SESSION_LOG_2026-03-23.md#L160)
  - Category: `other`
  - Context: 
  - Code: `## Next Agent TODO`

- **[XXX]** [AgriGuard/contracts/package-lock.json:6142](AgriGuard/contracts/package-lock.json#L6142)
  - Category: `other`
  - Context: evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",
  - Code: `"integrity": "sha512-YZo3K82SD7Riyi0E1EQPojLz7kpepnSQI9IyPbHHg1XXXevb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",`

- **[XXX]** [AgriGuard/frontend/package-lock.json:1475](AgriGuard/frontend/package-lock.json#L1475)
  - Category: `other`
  - Context: /8R7JOTXStz/nBbRw==",
  - Code: `"integrity": "sha512-XREFCPo6ksxVzP4E0ekD5aMdf8WMwmdNaz6vuvxgI40UaEiu6q3p8X52aU6GdyvLY3XXX/8R7JOTXStz/nBbRw==",`

- **[TODO]** [CONTEXT.md:14](CONTEXT.md#L14)
  - Category: `other`
  - Context: /IN_PROGRESS/DONE)
  - Code: `2. **[TASKS.md](TASKS.md)** - Active task board (TODO/IN_PROGRESS/DONE)`

- **[TODO]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:141](SYSTEM_DEBUG_REPORT_2026-03-24.md#L141)
  - Category: `testing`
  - Context: **: Test instructor upgrade for Google GenAI
  - Code: `3. 🔲 **TODO**: Test instructor upgrade for Google GenAI`

- **[TODO]** [TASKS.md:4](TASKS.md#L4)
  - Category: `other`
  - Context: / IN_PROGRESS / DONE)
  - Code: `**Board Type**: Kanban (TODO / IN_PROGRESS / DONE)`

- **[TODO]** [TASKS.md:8](TASKS.md#L8)
  - Category: `other`
  - Context: 
  - Code: `## TODO`

- **[TODO]** [TASKS.md:10](TASKS.md#L10)
  - Category: `other`
  - Context: *
  - Code: `*No tasks in TODO*`

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:96](TASK_COMPLETION_REPORT_2026-03-24.md#L96)
  - Category: `documentation`
  - Context: Comment Audit Results**
  - Code: `**TODO Comment Audit Results**:`

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:98](TASK_COMPLETION_REPORT_2026-03-24.md#L98)
  - Category: `documentation`
  - Context: comments found: 4 across 3 Python files
  - Code: `Total TODO comments found: 4 across 3 Python files`

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:103](TASK_COMPLETION_REPORT_2026-03-24.md#L103)
  - Category: `other`
  - Context: Integrate with crawler.py and ntis_crawler.py
  - Code: `- TODO: Integrate with crawler.py and ntis_crawler.py`

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:106](TASK_COMPLETION_REPORT_2026-03-24.md#L106)
  - Category: `other`
  - Context: Integrate with vector_store.py and vc_crawler.py
  - Code: `- TODO: Integrate with vector_store.py and vc_crawler.py`

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:109](TASK_COMPLETION_REPORT_2026-03-24.md#L109)
  - Category: `other`
  - Context: 실제 Canva API 통신 로직 병합
  - Code: `- TODO: 실제 Canva API 통신 로직 병합`

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:112](TASK_COMPLETION_REPORT_2026-03-24.md#L112)
  - Category: `documentation`
  - Context: s (meta comment, not actionable)
  - Code: `- Comment about extracting TODOs (meta comment, not actionable)`

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:175](TASK_COMPLETION_REPORT_2026-03-24.md#L175)
  - Category: `other`
  - Context: → Linear migration (4 items identified)
  - Code: `7. ✅ Planned TODO → Linear migration (4 items identified)`

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:185](TASK_COMPLETION_REPORT_2026-03-24.md#L185)
  - Category: `other`
  - Context: s**: `python scripts/linear_sync.py` (requires LINEAR_API_KEY)
  - Code: `4. **Migrate TODOs**: `python scripts/linear_sync.py` (requires LINEAR_API_KEY)`

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:190](TASK_COMPLETION_REPORT_2026-03-24.md#L190)
  - Category: `other`
  - Context: migration
  - Code: `- ✅ **Mid-term** (next sprint): Frontend updates, TODO migration`

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:205](TASK_COMPLETION_REPORT_2026-03-24.md#L205)
  - Category: `documentation`
  - Context: comments to migrate
  - Code: `**Technical Debt**: 3 TODO comments to migrate`

- **[TODO]** [desci-platform/IMPROVEMENT_PLAN.md:39](desci-platform/IMPROVEMENT_PLAN.md#L39)
  - Category: `other`
  - Context: )
  - Code: `## 5. 다음 단계 (TODO)`

- **[TODO]** [desci-platform/biolinker/services/agent_graph.py:70](desci-platform/biolinker/services/agent_graph.py#L70)
  - Category: `other`
  - Context: Integrate with crawler.py and ntis_crawler.py
  - Code: `# TODO: Integrate with crawler.py and ntis_crawler.py`

- **[TODO]** [desci-platform/biolinker/services/agent_graph.py:125](desci-platform/biolinker/services/agent_graph.py#L125)
  - Category: `other`
  - Context: Integrate with vector_store.py and vc_crawler.py
  - Code: `# TODO: Integrate with vector_store.py and vc_crawler.py`

- **[XXX]** [desci-platform/contracts/package-lock.json:5865](desci-platform/contracts/package-lock.json#L5865)
  - Category: `other`
  - Context: evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",
  - Code: `"integrity": "sha512-YZo3K82SD7Riyi0E1EQPojLz7kpepnSQI9IyPbHHg1XXXevb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",`

- **[TODO]** [docs/WORKSPACE-STATUS-2026-03-22.md:98](docs/WORKSPACE-STATUS-2026-03-22.md#L98)
  - Category: `other`
  - Context: 
  - Code: `## 남은 TODO`

- **[TODO]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:185](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L185)
  - Category: `other`
  - Context: | Config exists, not integrated |
  - Code: `| **C-4: Canva Visuals** | ⏭️ TODO | Config exists, not integrated |`

- **[TODO]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:186](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L186)
  - Category: `other`
  - Context: | Only Telegram/Discord |
  - Code: `| **C-5: Slack/Email Alerts** | ⏭️ TODO | Only Telegram/Discord |`

- **[TODO]** [getdaytrends/canva.py:26](getdaytrends/canva.py#L26)
  - Category: `other`
  - Context: 실제 Canva API 통신 로직 병합
  - Code: `# TODO: 실제 Canva API 통신 로직 병합`

- **[TODO]** [getdaytrends/generation/audit.py:15](getdaytrends/generation/audit.py#L15)
  - Category: `other`
  - Context: generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.
  - Code: `TODO: generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.`

- **[TODO]** [getdaytrends/generation/prompts.py:13](getdaytrends/generation/prompts.py#L13)
  - Category: `other`
  - Context: generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.
  - Code: `TODO: generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.`

- **[TODO]** [scripts/workspace_summary.py:7](scripts/workspace_summary.py#L7)
  - Category: `other`
  - Context: 추출
  - Code: `- 최신 세션 히스토리 → TODO 추출`

- **[TODO]** [scripts/workspace_summary.py:64](scripts/workspace_summary.py#L64)
  - Category: `other`
  - Context: 추출."""
  - Code: `"""최신 세션 히스토리에서 TODO 추출."""`

- **[TODO]** [scripts/workspace_summary.py:80](scripts/workspace_summary.py#L80)
  - Category: `other`
  - Context: 추출
  - Code: `# TODO 추출`

- **[TODO]** [scripts/workspace_summary.py:83](scripts/workspace_summary.py#L83)
  - Category: `other`
  - Context: " in line or "다음 세션" in line
  - Code: `if "다음 TODO" in line or "다음 세션" in line:`

- **[TODO]** [scripts/workspace_summary.py:194](scripts/workspace_summary.py#L194)
  - Category: `other`
  - Context: 
  - Code: `# 이전 세션 TODO`

- **[TODO]** [scripts/workspace_summary.py:198](scripts/workspace_summary.py#L198)
  - Category: `other`
  - Context: ({len(todos['todos'])}개):")
  - Code: `lines.append(f"\n🎯 미완료 TODO ({len(todos['todos'])}개):")`

- **[TODO]** [scripts/workspace_summary.py:225](scripts/workspace_summary.py#L225)
  - Category: `other`
  - Context: 이어서 작업")
  - Code: `lines.append(f"   3. 이전 세션 TODO 이어서 작업")`

---

## 카테고리별 상세

### Other - 51개 항목

- **[P3]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:23](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L23)
  - 로 등록. 차기 스프린트에서 진행.

- **[P3]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:93](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L93)
  - 주석 명시 |

- **[P3]** [.agent/session-history/2026-03-07.md:48](.agent/session-history/2026-03-07.md#L48)
  - 

- **[P3]** [.agent/session-history/2026-03-08.md:36](.agent/session-history/2026-03-08.md#L36)
  - 

- **[P3]** [.agent/session-history/2026-03-08.md:99](.agent/session-history/2026-03-08.md#L99)
  - 

- **[P3]** [.agent/session-history/2026-03-08.md:135](.agent/session-history/2026-03-08.md#L135)
  - 

- **[P3]** [.agent/session-history/2026-03-08.md:161](.agent/session-history/2026-03-08.md#L161)
  - 

- **[P3]** [.agent/session-history/2026-03-08.md:184](.agent/session-history/2026-03-08.md#L184)
  - 

- **[P3]** [.agent/session-history/2026-03-08.md:235](.agent/session-history/2026-03-08.md#L235)
  - 

- **[P3]** [.agent/session-history/2026-03-08.md:275](.agent/session-history/2026-03-08.md#L275)
  - 

- **[P3]** [.agent/session-history/2026-03-08.md:313](.agent/session-history/2026-03-08.md#L313)
  - 

- **[P3]** [.agent/session-history/2026-03-21.md:36](.agent/session-history/2026-03-21.md#L36)
  - 

- **[P3]** [.agent/session-history/2026-03-21.md:104](.agent/session-history/2026-03-21.md#L104)
  - 

- **[P3]** [.agent/session-history/2026-03-24.md:44](.agent/session-history/2026-03-24.md#L44)
  - 

- **[P3]** [.agent/workflows/qa-qc.md:110](.agent/workflows/qa-qc.md#L110)
  - 로 등록하고 넘어감

- **[P3]** [.agent/workflows/session-workflow.md:50](.agent/workflows/session-workflow.md#L50)
  - `

- **[P3]** [.agent/workflows/session-workflow.md:87](.agent/workflows/session-workflow.md#L87)
  - **: [항목 나열]

- **[P3]** [.agent/workflows/session-workflow.md:148](.agent/workflows/session-workflow.md#L148)
  - **: 구체적이고 실행 가능한 항목

- **[P3]** [.agent/workflows/session-workflow.md:186](.agent/workflows/session-workflow.md#L186)
  - 

- **[P3]** [.sessions/README.md:49](.sessions/README.md#L49)
  - **: Handoff tasks

- **[P3]** [.sessions/SESSION_LOG_2026-03-23.md:32](.sessions/SESSION_LOG_2026-03-23.md#L32)
  - /IN_PROGRESS/DONE, priority levels, tool assignment guide

- **[P3]** [.sessions/SESSION_LOG_2026-03-23.md:160](.sessions/SESSION_LOG_2026-03-23.md#L160)
  - 

- **[P3]** [AgriGuard/contracts/package-lock.json:6142](AgriGuard/contracts/package-lock.json#L6142)
  - evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",

- **[P3]** [AgriGuard/frontend/package-lock.json:1475](AgriGuard/frontend/package-lock.json#L1475)
  - /8R7JOTXStz/nBbRw==",

- **[P3]** [CONTEXT.md:14](CONTEXT.md#L14)
  - /IN_PROGRESS/DONE)

- **[P3]** [TASKS.md:4](TASKS.md#L4)
  - / IN_PROGRESS / DONE)

- **[P3]** [TASKS.md:8](TASKS.md#L8)
  - 

- **[P3]** [TASKS.md:10](TASKS.md#L10)
  - *

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:103](TASK_COMPLETION_REPORT_2026-03-24.md#L103)
  - Integrate with crawler.py and ntis_crawler.py

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:106](TASK_COMPLETION_REPORT_2026-03-24.md#L106)
  - Integrate with vector_store.py and vc_crawler.py

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:109](TASK_COMPLETION_REPORT_2026-03-24.md#L109)
  - 실제 Canva API 통신 로직 병합

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:175](TASK_COMPLETION_REPORT_2026-03-24.md#L175)
  - → Linear migration (4 items identified)

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:185](TASK_COMPLETION_REPORT_2026-03-24.md#L185)
  - s**: `python scripts/linear_sync.py` (requires LINEAR_API_KEY)

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:190](TASK_COMPLETION_REPORT_2026-03-24.md#L190)
  - migration

- **[P3]** [desci-platform/IMPROVEMENT_PLAN.md:39](desci-platform/IMPROVEMENT_PLAN.md#L39)
  - )

- **[P3]** [desci-platform/biolinker/services/agent_graph.py:70](desci-platform/biolinker/services/agent_graph.py#L70)
  - Integrate with crawler.py and ntis_crawler.py

- **[P3]** [desci-platform/biolinker/services/agent_graph.py:125](desci-platform/biolinker/services/agent_graph.py#L125)
  - Integrate with vector_store.py and vc_crawler.py

- **[P3]** [desci-platform/contracts/package-lock.json:5865](desci-platform/contracts/package-lock.json#L5865)
  - evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",

- **[P3]** [docs/WORKSPACE-STATUS-2026-03-22.md:98](docs/WORKSPACE-STATUS-2026-03-22.md#L98)
  - 

- **[P3]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:185](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L185)
  - | Config exists, not integrated |

- **[P3]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:186](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L186)
  - | Only Telegram/Discord |

- **[P3]** [getdaytrends/canva.py:26](getdaytrends/canva.py#L26)
  - 실제 Canva API 통신 로직 병합

- **[P3]** [getdaytrends/generation/audit.py:15](getdaytrends/generation/audit.py#L15)
  - generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.

- **[P3]** [getdaytrends/generation/prompts.py:13](getdaytrends/generation/prompts.py#L13)
  - generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.

- **[P3]** [scripts/workspace_summary.py:7](scripts/workspace_summary.py#L7)
  - 추출

- **[P3]** [scripts/workspace_summary.py:64](scripts/workspace_summary.py#L64)
  - 추출."""

- **[P3]** [scripts/workspace_summary.py:80](scripts/workspace_summary.py#L80)
  - 추출

- **[P3]** [scripts/workspace_summary.py:83](scripts/workspace_summary.py#L83)
  - " in line or "다음 세션" in line

- **[P3]** [scripts/workspace_summary.py:194](scripts/workspace_summary.py#L194)
  - 

- **[P3]** [scripts/workspace_summary.py:198](scripts/workspace_summary.py#L198)
  - ({len(todos['todos'])}개):")

- **[P3]** [scripts/workspace_summary.py:225](scripts/workspace_summary.py#L225)
  - 이어서 작업")

### Bug - 6개 항목

- **[P1]** [QC_REPORT_2026-03-24_SYSTEM_DEBUG.md:388](QC_REPORT_2026-03-24_SYSTEM_DEBUG.md#L388)
  - comments to Linear issues

- **[P1]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:82](SYSTEM_DEBUG_REPORT_2026-03-24.md#L82)
  - /FIXME Comments (13 files, 23 occurrences)

- **[P1]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:150](SYSTEM_DEBUG_REPORT_2026-03-24.md#L150)
  - comments to Linear issues

- **[P1]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:190](SYSTEM_DEBUG_REPORT_2026-03-24.md#L190)
  - comments → Linear issues

- **[P1]** [TASK_COMPLETION_REPORT_2026-03-24.md:92](TASK_COMPLETION_REPORT_2026-03-24.md#L92)
  - → Linear Issues Migration Plan ✅

- **[P1]** [TASK_COMPLETION_REPORT_2026-03-24.md:116](TASK_COMPLETION_REPORT_2026-03-24.md#L116)
  - s into Linear issues

### Documentation - 4개 항목

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:96](TASK_COMPLETION_REPORT_2026-03-24.md#L96)
  - Comment Audit Results**

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:98](TASK_COMPLETION_REPORT_2026-03-24.md#L98)
  - comments found: 4 across 3 Python files

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:112](TASK_COMPLETION_REPORT_2026-03-24.md#L112)
  - s (meta comment, not actionable)

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:205](TASK_COMPLETION_REPORT_2026-03-24.md#L205)
  - comments to migrate

### Testing - 1개 항목

- **[P3]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:141](SYSTEM_DEBUG_REPORT_2026-03-24.md#L141)
  - **: Test instructor upgrade for Google GenAI

---

## 프로젝트별 상세

### root - 21개 항목

**우선순위 분포**: P1: 6, P3: 15

- **[P1]** [QC_REPORT_2026-03-24_SYSTEM_DEBUG.md:388](QC_REPORT_2026-03-24_SYSTEM_DEBUG.md#L388)
  - [TODO] comments to Linear issues

- **[P1]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:82](SYSTEM_DEBUG_REPORT_2026-03-24.md#L82)
  - [TODO] /FIXME Comments (13 files, 23 occurrences)

- **[P1]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:150](SYSTEM_DEBUG_REPORT_2026-03-24.md#L150)
  - [TODO] comments to Linear issues

- **[P1]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:190](SYSTEM_DEBUG_REPORT_2026-03-24.md#L190)
  - [TODO] comments → Linear issues

- **[P1]** [TASK_COMPLETION_REPORT_2026-03-24.md:92](TASK_COMPLETION_REPORT_2026-03-24.md#L92)
  - [TODO] → Linear Issues Migration Plan ✅

- **[P1]** [TASK_COMPLETION_REPORT_2026-03-24.md:116](TASK_COMPLETION_REPORT_2026-03-24.md#L116)
  - [TODO] s into Linear issues

- **[P3]** [CONTEXT.md:14](CONTEXT.md#L14)
  - [TODO] /IN_PROGRESS/DONE)

- **[P3]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:141](SYSTEM_DEBUG_REPORT_2026-03-24.md#L141)
  - [TODO] **: Test instructor upgrade for Google GenAI

- **[P3]** [TASKS.md:4](TASKS.md#L4)
  - [TODO] / IN_PROGRESS / DONE)

- **[P3]** [TASKS.md:8](TASKS.md#L8)
  - [TODO] 

- **[P3]** [TASKS.md:10](TASKS.md#L10)
  - [TODO] *

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:96](TASK_COMPLETION_REPORT_2026-03-24.md#L96)
  - [TODO] Comment Audit Results**

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:98](TASK_COMPLETION_REPORT_2026-03-24.md#L98)
  - [TODO] comments found: 4 across 3 Python files

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:103](TASK_COMPLETION_REPORT_2026-03-24.md#L103)
  - [TODO] Integrate with crawler.py and ntis_crawler.py

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:106](TASK_COMPLETION_REPORT_2026-03-24.md#L106)
  - [TODO] Integrate with vector_store.py and vc_crawler.py

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:109](TASK_COMPLETION_REPORT_2026-03-24.md#L109)
  - [TODO] 실제 Canva API 통신 로직 병합

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:112](TASK_COMPLETION_REPORT_2026-03-24.md#L112)
  - [TODO] s (meta comment, not actionable)

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:175](TASK_COMPLETION_REPORT_2026-03-24.md#L175)
  - [TODO] → Linear migration (4 items identified)

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:185](TASK_COMPLETION_REPORT_2026-03-24.md#L185)
  - [TODO] s**: `python scripts/linear_sync.py` (requires LINEAR_API_KEY)

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:190](TASK_COMPLETION_REPORT_2026-03-24.md#L190)
  - [TODO] migration

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:205](TASK_COMPLETION_REPORT_2026-03-24.md#L205)
  - [TODO] comments to migrate

### .agent - 19개 항목

**우선순위 분포**: P3: 19

- **[P3]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:23](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L23)
  - [TODO] 로 등록. 차기 스프린트에서 진행.

- **[P3]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:93](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L93)
  - [TODO] 주석 명시 |

- **[P3]** [.agent/session-history/2026-03-07.md:48](.agent/session-history/2026-03-07.md#L48)
  - [TODO] 

- **[P3]** [.agent/session-history/2026-03-08.md:36](.agent/session-history/2026-03-08.md#L36)
  - [TODO] 

- **[P3]** [.agent/session-history/2026-03-08.md:99](.agent/session-history/2026-03-08.md#L99)
  - [TODO] 

- **[P3]** [.agent/session-history/2026-03-08.md:135](.agent/session-history/2026-03-08.md#L135)
  - [TODO] 

- **[P3]** [.agent/session-history/2026-03-08.md:161](.agent/session-history/2026-03-08.md#L161)
  - [TODO] 

- **[P3]** [.agent/session-history/2026-03-08.md:184](.agent/session-history/2026-03-08.md#L184)
  - [TODO] 

- **[P3]** [.agent/session-history/2026-03-08.md:235](.agent/session-history/2026-03-08.md#L235)
  - [TODO] 

- **[P3]** [.agent/session-history/2026-03-08.md:275](.agent/session-history/2026-03-08.md#L275)
  - [TODO] 

- **[P3]** [.agent/session-history/2026-03-08.md:313](.agent/session-history/2026-03-08.md#L313)
  - [TODO] 

- **[P3]** [.agent/session-history/2026-03-21.md:36](.agent/session-history/2026-03-21.md#L36)
  - [TODO] 

- **[P3]** [.agent/session-history/2026-03-21.md:104](.agent/session-history/2026-03-21.md#L104)
  - [TODO] 

- **[P3]** [.agent/session-history/2026-03-24.md:44](.agent/session-history/2026-03-24.md#L44)
  - [TODO] 

- **[P3]** [.agent/workflows/qa-qc.md:110](.agent/workflows/qa-qc.md#L110)
  - [TODO] 로 등록하고 넘어감

- **[P3]** [.agent/workflows/session-workflow.md:50](.agent/workflows/session-workflow.md#L50)
  - [TODO] `

- **[P3]** [.agent/workflows/session-workflow.md:87](.agent/workflows/session-workflow.md#L87)
  - [TODO] **: [항목 나열]

- **[P3]** [.agent/workflows/session-workflow.md:148](.agent/workflows/session-workflow.md#L148)
  - [TODO] **: 구체적이고 실행 가능한 항목

- **[P3]** [.agent/workflows/session-workflow.md:186](.agent/workflows/session-workflow.md#L186)
  - [TODO] 

### scripts - 7개 항목

**우선순위 분포**: P3: 7

- **[P3]** [scripts/workspace_summary.py:7](scripts/workspace_summary.py#L7)
  - [TODO] 추출

- **[P3]** [scripts/workspace_summary.py:64](scripts/workspace_summary.py#L64)
  - [TODO] 추출."""

- **[P3]** [scripts/workspace_summary.py:80](scripts/workspace_summary.py#L80)
  - [TODO] 추출

- **[P3]** [scripts/workspace_summary.py:83](scripts/workspace_summary.py#L83)
  - [TODO] " in line or "다음 세션" in line

- **[P3]** [scripts/workspace_summary.py:194](scripts/workspace_summary.py#L194)
  - [TODO] 

- **[P3]** [scripts/workspace_summary.py:198](scripts/workspace_summary.py#L198)
  - [TODO] ({len(todos['todos'])}개):")

- **[P3]** [scripts/workspace_summary.py:225](scripts/workspace_summary.py#L225)
  - [TODO] 이어서 작업")

### getdaytrends - 5개 항목

**우선순위 분포**: P3: 5

- **[P3]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:185](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L185)
  - [TODO] | Config exists, not integrated |

- **[P3]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:186](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L186)
  - [TODO] | Only Telegram/Discord |

- **[P3]** [getdaytrends/canva.py:26](getdaytrends/canva.py#L26)
  - [TODO] 실제 Canva API 통신 로직 병합

- **[P3]** [getdaytrends/generation/audit.py:15](getdaytrends/generation/audit.py#L15)
  - [TODO] generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.

- **[P3]** [getdaytrends/generation/prompts.py:13](getdaytrends/generation/prompts.py#L13)
  - [TODO] generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.

### desci-platform - 4개 항목

**우선순위 분포**: P3: 4

- **[P3]** [desci-platform/IMPROVEMENT_PLAN.md:39](desci-platform/IMPROVEMENT_PLAN.md#L39)
  - [TODO] )

- **[P3]** [desci-platform/biolinker/services/agent_graph.py:70](desci-platform/biolinker/services/agent_graph.py#L70)
  - [TODO] Integrate with crawler.py and ntis_crawler.py

- **[P3]** [desci-platform/biolinker/services/agent_graph.py:125](desci-platform/biolinker/services/agent_graph.py#L125)
  - [TODO] Integrate with vector_store.py and vc_crawler.py

- **[P3]** [desci-platform/contracts/package-lock.json:5865](desci-platform/contracts/package-lock.json#L5865)
  - [XXX] evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",

### .sessions - 3개 항목

**우선순위 분포**: P3: 3

- **[P3]** [.sessions/README.md:49](.sessions/README.md#L49)
  - [TODO] **: Handoff tasks

- **[P3]** [.sessions/SESSION_LOG_2026-03-23.md:32](.sessions/SESSION_LOG_2026-03-23.md#L32)
  - [TODO] /IN_PROGRESS/DONE, priority levels, tool assignment guide

- **[P3]** [.sessions/SESSION_LOG_2026-03-23.md:160](.sessions/SESSION_LOG_2026-03-23.md#L160)
  - [TODO] 

### AgriGuard - 2개 항목

**우선순위 분포**: P3: 2

- **[P3]** [AgriGuard/contracts/package-lock.json:6142](AgriGuard/contracts/package-lock.json#L6142)
  - [XXX] evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",

- **[P3]** [AgriGuard/frontend/package-lock.json:1475](AgriGuard/frontend/package-lock.json#L1475)
  - [XXX] /8R7JOTXStz/nBbRw==",

### docs - 1개 항목

**우선순위 분포**: P3: 1

- **[P3]** [docs/WORKSPACE-STATUS-2026-03-22.md:98](docs/WORKSPACE-STATUS-2026-03-22.md#L98)
  - [TODO] 

---

## 다음 단계

1. **P0 항목 즉시 처리**: 보안 및 긴급 이슈부터 해결
2. **GitHub Issues 생성**: 각 항목을 이슈로 등록하여 추적
3. **주간 부채 상환**: 매주 금요일 "Tech Debt Friday" 운영
4. **월간 리뷰**: 진행 상황 및 남은 부채 리뷰

---

**자동 생성 스크립트**: `scripts/generate_tech_debt_inventory.py`
**마지막 업데이트**: 2026-03-26 07:40:08
