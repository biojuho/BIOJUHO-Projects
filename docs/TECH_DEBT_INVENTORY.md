# 기술 부채 인벤토리 (Tech Debt Inventory)

**생성일**: 2026-03-26 08:08:04
**워크스페이스**: AI 프로젝트
**총 항목**: 285

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
| P1 | 7 | 2.5% |
| P2 | 0 | 0.0% |
| P3 | 278 | 97.5% |

### 카테고리별

| 카테고리 | 항목 수 |
|---------|--------|
| other | 228 |
| bug | 40 |
| documentation | 14 |
| testing | 3 |

### 프로젝트별

| 프로젝트 | 항목 수 |
|---------|--------|
| docs | 212 |
| root | 26 |
| .agent | 19 |
| scripts | 14 |
| getdaytrends | 5 |
| desci-platform | 4 |
| .sessions | 3 |
| AgriGuard | 2 |

---

## 우선순위별 상세

### P1 - 7개 항목

- **[TODO]** [scripts/generate_tech_debt_inventory.py:5](scripts/generate_tech_debt_inventory.py#L5)
  - Category: `bug`
  - Context: , FIXME, HACK, XXX 주석을 자동으로 수집하여
  - Code: `코드베이스에서 TODO, FIXME, HACK, XXX 주석을 자동으로 수집하여`

- **[TODO]** [scripts/generate_tech_debt_inventory.py:25](scripts/generate_tech_debt_inventory.py#L25)
  - Category: `bug`
  - Context: , FIXME, HACK, XXX
  - Code: `marker: str  # TODO, FIXME, HACK, XXX`

- **[TODO]** [scripts/generate_tech_debt_inventory.py:64](scripts/generate_tech_debt_inventory.py#L64)
  - Category: `bug`
  - Context: /FIXME/HACK/XXX 검색
  - Code: `# Git grep으로 TODO/FIXME/HACK/XXX 검색`

- **[TODO]** [scripts/generate_tech_debt_inventory.py:65](scripts/generate_tech_debt_inventory.py#L65)
  - Category: `bug`
  - Context: ', 'FIXME', 'HACK', 'XXX']
  - Code: `markers = ['TODO', 'FIXME', 'HACK', 'XXX']`

- **[TODO]** [scripts/generate_tech_debt_inventory.py:101](scripts/generate_tech_debt_inventory.py#L101)
  - Category: `bug`
  - Context: fix this
  - Code: `# Format: file.py:123:# TODO: fix this`

- **[TODO]** [scripts/generate_tech_debt_inventory.py:110](scripts/generate_tech_debt_inventory.py#L110)
  - Category: `bug`
  - Context: ', 'FIXME', 'HACK', 'XXX']
  - Code: `for m in ['TODO', 'FIXME', 'HACK', 'XXX']:`

- **[TODO]** [scripts/generate_tech_debt_inventory.py:211](scripts/generate_tech_debt_inventory.py#L211)
  - Category: `bug`
  - Context: , FIXME, HACK, XXX)을
  - Code: `이 문서는 코드베이스에서 자동으로 수집된 기술 부채 항목(TODO, FIXME, HACK, XXX)을`

### P3 - 278개 항목

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

- **[TODO]** [QC_REPORT_2026-03-24_SYSTEM_DEBUG.md:388](QC_REPORT_2026-03-24_SYSTEM_DEBUG.md#L388)
  - Category: `bug`
  - Context: comments to Linear issues
  - Code: `- [ ] Convert TODO comments to Linear issues`

- **[TODO]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:82](SYSTEM_DEBUG_REPORT_2026-03-24.md#L82)
  - Category: `bug`
  - Context: /FIXME Comments (13 files, 23 occurrences)
  - Code: `#### 9. TODO/FIXME Comments (13 files, 23 occurrences)`

- **[TODO]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:141](SYSTEM_DEBUG_REPORT_2026-03-24.md#L141)
  - Category: `testing`
  - Context: **: Test instructor upgrade for Google GenAI
  - Code: `3. 🔲 **TODO**: Test instructor upgrade for Google GenAI`

- **[TODO]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:150](SYSTEM_DEBUG_REPORT_2026-03-24.md#L150)
  - Category: `bug`
  - Context: comments to Linear issues
  - Code: `6. 🔲 Convert TODO comments to Linear issues`

- **[TODO]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:190](SYSTEM_DEBUG_REPORT_2026-03-24.md#L190)
  - Category: `bug`
  - Context: comments → Linear issues
  - Code: `- [ ] Review TODO comments → Linear issues`

- **[TODO]** [SYSTEM_ENHANCEMENT_PLAN.md:109](SYSTEM_ENHANCEMENT_PLAN.md#L109)
  - Category: `bug`
  - Context: /FIXME (145개 에러 핸들링 검토 필요)
  - Code: `- **기술 부채**: 53개 파일에 TODO/FIXME (145개 에러 핸들링 검토 필요)`

- **[TODO]** [SYSTEM_ENHANCEMENT_PLAN.md:321](SYSTEM_ENHANCEMENT_PLAN.md#L321)
  - Category: `bug`
  - Context: /FIXME/HACK/XXX 존재
  - Code: `- 53개 파일에 TODO/FIXME/HACK/XXX 존재`

- **[TODO]** [SYSTEM_ENHANCEMENT_PLAN.md:341](SYSTEM_ENHANCEMENT_PLAN.md#L341)
  - Category: `bug`
  - Context: 주석 → GitHub Issue 자동 생성 (label: tech-debt)
  - Code: `# TODO 주석 → GitHub Issue 자동 생성 (label: tech-debt)`

- **[TODO]** [SYSTEM_ENHANCEMENT_PLAN.md:354](SYSTEM_ENHANCEMENT_PLAN.md#L354)
  - Category: `bug`
  - Context: /FIXME 50% 감소 (53 → 26개)
  - Code: `- TODO/FIXME 50% 감소 (53 → 26개)`

- **[TODO]** [SYSTEM_ENHANCEMENT_PLAN.md:1149](SYSTEM_ENHANCEMENT_PLAN.md#L1149)
  - Category: `other`
  - Context: ) | 53 files | 26 files | grep -r "TODO" |
  - Code: `| 기술 부채 (TODO) | 53 files | 26 files | grep -r "TODO" |`

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

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:92](TASK_COMPLETION_REPORT_2026-03-24.md#L92)
  - Category: `bug`
  - Context: → Linear Issues Migration Plan ✅
  - Code: `### 6. TODO → Linear Issues Migration Plan ✅`

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

- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:116](TASK_COMPLETION_REPORT_2026-03-24.md#L116)
  - Category: `bug`
  - Context: s into Linear issues
  - Code: `2. Convert 3 actionable TODOs into Linear issues`

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

- **[TODO]** [docs/SYSTEM_ENHANCEMENT_SUMMARY.md:53](docs/SYSTEM_ENHANCEMENT_SUMMARY.md#L53)
  - Category: `other`
  - Context: 제외 가능)
  - Code: `2. .agent: 19개 (세션 히스토리 내 TODO 제외 가능)`

- **[TODO]** [docs/SYSTEM_ENHANCEMENT_SUMMARY.md:60](docs/SYSTEM_ENHANCEMENT_SUMMARY.md#L60)
  - Category: `other`
  - Context: (실제 코드 버그 아님)
  - Code: `- P1 6개 항목은 대부분 문서 내 TODO (실제 코드 버그 아님)`

- **[TODO]** [docs/SYSTEM_ENHANCEMENT_SUMMARY.md:146](docs/SYSTEM_ENHANCEMENT_SUMMARY.md#L146)
  - Category: `other`
  - Context: 추가 가능
  - Code: `2. **기술 부채 백로그 증가**: 신규 개발 시 TODO 추가 가능`

- **[TODO]** [docs/SYSTEM_ENHANCEMENT_SUMMARY.md:147](docs/SYSTEM_ENHANCEMENT_SUMMARY.md#L147)
  - Category: `other`
  - Context: 경고 추가 (선택)
  - Code: `- **완화**: Pre-commit hook에 TODO 경고 추가 (선택)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:11](docs/TECH_DEBT_INVENTORY.md#L11)
  - Category: `bug`
  - Context: , FIXME, HACK, XXX)을
  - Code: `이 문서는 코드베이스에서 자동으로 수집된 기술 부채 항목(TODO, FIXME, HACK, XXX)을`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:73](docs/TECH_DEBT_INVENTORY.md#L73)
  - Category: `bug`
  - Context: ]** [QC_REPORT_2026-03-24_SYSTEM_DEBUG.md:388](QC_REPORT_2026-03-24_SYSTEM_DEBUG.md#L388)
  - Code: `- **[TODO]** [QC_REPORT_2026-03-24_SYSTEM_DEBUG.md:388](QC_REPORT_2026-03-24_SYSTEM_DEBUG.md#L388)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:76](docs/TECH_DEBT_INVENTORY.md#L76)
  - Category: `bug`
  - Context: comments to Linear issues`
  - Code: `- Code: `- [ ] Convert TODO comments to Linear issues``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:78](docs/TECH_DEBT_INVENTORY.md#L78)
  - Category: `bug`
  - Context: ]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:82](SYSTEM_DEBUG_REPORT_2026-03-24.md#L82)
  - Code: `- **[TODO]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:82](SYSTEM_DEBUG_REPORT_2026-03-24.md#L82)`

- **[FIXME]** [docs/TECH_DEBT_INVENTORY.md:80](docs/TECH_DEBT_INVENTORY.md#L80)
  - Category: `documentation`
  - Context: Comments (13 files, 23 occurrences)
  - Code: `- Context: /FIXME Comments (13 files, 23 occurrences)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:81](docs/TECH_DEBT_INVENTORY.md#L81)
  - Category: `bug`
  - Context: /FIXME Comments (13 files, 23 occurrences)`
  - Code: `- Code: `#### 9. TODO/FIXME Comments (13 files, 23 occurrences)``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:83](docs/TECH_DEBT_INVENTORY.md#L83)
  - Category: `bug`
  - Context: ]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:150](SYSTEM_DEBUG_REPORT_2026-03-24.md#L150)
  - Code: `- **[TODO]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:150](SYSTEM_DEBUG_REPORT_2026-03-24.md#L150)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:86](docs/TECH_DEBT_INVENTORY.md#L86)
  - Category: `bug`
  - Context: comments to Linear issues`
  - Code: `- Code: `6. 🔲 Convert TODO comments to Linear issues``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:88](docs/TECH_DEBT_INVENTORY.md#L88)
  - Category: `bug`
  - Context: ]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:190](SYSTEM_DEBUG_REPORT_2026-03-24.md#L190)
  - Code: `- **[TODO]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:190](SYSTEM_DEBUG_REPORT_2026-03-24.md#L190)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:91](docs/TECH_DEBT_INVENTORY.md#L91)
  - Category: `bug`
  - Context: comments → Linear issues`
  - Code: `- Code: `- [ ] Review TODO comments → Linear issues``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:93](docs/TECH_DEBT_INVENTORY.md#L93)
  - Category: `other`
  - Context: ]** [TASK_COMPLETION_REPORT_2026-03-24.md:92](TASK_COMPLETION_REPORT_2026-03-24.md#L92)
  - Code: `- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:92](TASK_COMPLETION_REPORT_2026-03-24.md#L92)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:96](docs/TECH_DEBT_INVENTORY.md#L96)
  - Category: `bug`
  - Context: → Linear Issues Migration Plan ✅`
  - Code: `- Code: `### 6. TODO → Linear Issues Migration Plan ✅``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:98](docs/TECH_DEBT_INVENTORY.md#L98)
  - Category: `other`
  - Context: ]** [TASK_COMPLETION_REPORT_2026-03-24.md:116](TASK_COMPLETION_REPORT_2026-03-24.md#L116)
  - Code: `- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:116](TASK_COMPLETION_REPORT_2026-03-24.md#L116)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:101](docs/TECH_DEBT_INVENTORY.md#L101)
  - Category: `bug`
  - Context: s into Linear issues`
  - Code: `- Code: `2. Convert 3 actionable TODOs into Linear issues``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:105](docs/TECH_DEBT_INVENTORY.md#L105)
  - Category: `other`
  - Context: ]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:23](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L23)
  - Code: `- **[TODO]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:23](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L23)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:108](docs/TECH_DEBT_INVENTORY.md#L108)
  - Category: `other`
  - Context: 로 등록. 차기 스프린트에서 진행.`
  - Code: `- Code: `> 30분 초과 → TODO로 등록. 차기 스프린트에서 진행.``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:110](docs/TECH_DEBT_INVENTORY.md#L110)
  - Category: `other`
  - Context: ]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:93](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L93)
  - Code: `- **[TODO]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:93](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L93)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:113](docs/TECH_DEBT_INVENTORY.md#L113)
  - Category: `other`
  - Context: 주석 명시 |`
  - Code: `- Code: `| LOW | `generation/prompts.py` 마이그레이션 미완료 → 향후 작업 시 코드 위치 혼란 | 스켈레톤 파일에 TODO 주석 명시 |``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:115](docs/TECH_DEBT_INVENTORY.md#L115)
  - Category: `other`
  - Context: ]** [.agent/session-history/2026-03-07.md:48](.agent/session-history/2026-03-07.md#L48)
  - Code: `- **[TODO]** [.agent/session-history/2026-03-07.md:48](.agent/session-history/2026-03-07.md#L48)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:118](docs/TECH_DEBT_INVENTORY.md#L118)
  - Category: `other`
  - Context: `
  - Code: `- Code: `## 📋 다음 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:120](docs/TECH_DEBT_INVENTORY.md#L120)
  - Category: `other`
  - Context: ]** [.agent/session-history/2026-03-08.md:36](.agent/session-history/2026-03-08.md#L36)
  - Code: `- **[TODO]** [.agent/session-history/2026-03-08.md:36](.agent/session-history/2026-03-08.md#L36)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:123](docs/TECH_DEBT_INVENTORY.md#L123)
  - Category: `other`
  - Context: `
  - Code: `- Code: `## 📋 다음 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:125](docs/TECH_DEBT_INVENTORY.md#L125)
  - Category: `other`
  - Context: ]** [.agent/session-history/2026-03-08.md:99](.agent/session-history/2026-03-08.md#L99)
  - Code: `- **[TODO]** [.agent/session-history/2026-03-08.md:99](.agent/session-history/2026-03-08.md#L99)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:128](docs/TECH_DEBT_INVENTORY.md#L128)
  - Category: `other`
  - Context: `
  - Code: `- Code: `### 📋 다음 세션 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:130](docs/TECH_DEBT_INVENTORY.md#L130)
  - Category: `other`
  - Context: ]** [.agent/session-history/2026-03-08.md:135](.agent/session-history/2026-03-08.md#L135)
  - Code: `- **[TODO]** [.agent/session-history/2026-03-08.md:135](.agent/session-history/2026-03-08.md#L135)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:133](docs/TECH_DEBT_INVENTORY.md#L133)
  - Category: `other`
  - Context: `
  - Code: `- Code: `### 📋 다음 세션 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:135](docs/TECH_DEBT_INVENTORY.md#L135)
  - Category: `other`
  - Context: ]** [.agent/session-history/2026-03-08.md:161](.agent/session-history/2026-03-08.md#L161)
  - Code: `- **[TODO]** [.agent/session-history/2026-03-08.md:161](.agent/session-history/2026-03-08.md#L161)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:138](docs/TECH_DEBT_INVENTORY.md#L138)
  - Category: `other`
  - Context: `
  - Code: `- Code: `### 📋 다음 세션 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:140](docs/TECH_DEBT_INVENTORY.md#L140)
  - Category: `other`
  - Context: ]** [.agent/session-history/2026-03-08.md:184](.agent/session-history/2026-03-08.md#L184)
  - Code: `- **[TODO]** [.agent/session-history/2026-03-08.md:184](.agent/session-history/2026-03-08.md#L184)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:143](docs/TECH_DEBT_INVENTORY.md#L143)
  - Category: `other`
  - Context: `
  - Code: `- Code: `### 📋 다음 세션 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:145](docs/TECH_DEBT_INVENTORY.md#L145)
  - Category: `other`
  - Context: ]** [.agent/session-history/2026-03-08.md:235](.agent/session-history/2026-03-08.md#L235)
  - Code: `- **[TODO]** [.agent/session-history/2026-03-08.md:235](.agent/session-history/2026-03-08.md#L235)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:148](docs/TECH_DEBT_INVENTORY.md#L148)
  - Category: `other`
  - Context: `
  - Code: `- Code: `### 📋 다음 세션 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:150](docs/TECH_DEBT_INVENTORY.md#L150)
  - Category: `other`
  - Context: ]** [.agent/session-history/2026-03-08.md:275](.agent/session-history/2026-03-08.md#L275)
  - Code: `- **[TODO]** [.agent/session-history/2026-03-08.md:275](.agent/session-history/2026-03-08.md#L275)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:153](docs/TECH_DEBT_INVENTORY.md#L153)
  - Category: `other`
  - Context: `
  - Code: `- Code: `### 📋 다음 세션 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:155](docs/TECH_DEBT_INVENTORY.md#L155)
  - Category: `other`
  - Context: ]** [.agent/session-history/2026-03-08.md:313](.agent/session-history/2026-03-08.md#L313)
  - Code: `- **[TODO]** [.agent/session-history/2026-03-08.md:313](.agent/session-history/2026-03-08.md#L313)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:158](docs/TECH_DEBT_INVENTORY.md#L158)
  - Category: `other`
  - Context: `
  - Code: `- Code: `### 📋 다음 세션 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:160](docs/TECH_DEBT_INVENTORY.md#L160)
  - Category: `other`
  - Context: ]** [.agent/session-history/2026-03-21.md:36](.agent/session-history/2026-03-21.md#L36)
  - Code: `- **[TODO]** [.agent/session-history/2026-03-21.md:36](.agent/session-history/2026-03-21.md#L36)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:163](docs/TECH_DEBT_INVENTORY.md#L163)
  - Category: `other`
  - Context: `
  - Code: `- Code: `### 다음 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:165](docs/TECH_DEBT_INVENTORY.md#L165)
  - Category: `other`
  - Context: ]** [.agent/session-history/2026-03-21.md:104](.agent/session-history/2026-03-21.md#L104)
  - Code: `- **[TODO]** [.agent/session-history/2026-03-21.md:104](.agent/session-history/2026-03-21.md#L104)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:168](docs/TECH_DEBT_INVENTORY.md#L168)
  - Category: `other`
  - Context: `
  - Code: `- Code: `### 다음 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:170](docs/TECH_DEBT_INVENTORY.md#L170)
  - Category: `other`
  - Context: ]** [.agent/session-history/2026-03-24.md:44](.agent/session-history/2026-03-24.md#L44)
  - Code: `- **[TODO]** [.agent/session-history/2026-03-24.md:44](.agent/session-history/2026-03-24.md#L44)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:173](docs/TECH_DEBT_INVENTORY.md#L173)
  - Category: `other`
  - Context: `
  - Code: `- Code: `### 다음 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:175](docs/TECH_DEBT_INVENTORY.md#L175)
  - Category: `other`
  - Context: ]** [.agent/workflows/qa-qc.md:110](.agent/workflows/qa-qc.md#L110)
  - Code: `- **[TODO]** [.agent/workflows/qa-qc.md:110](.agent/workflows/qa-qc.md#L110)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:178](docs/TECH_DEBT_INVENTORY.md#L178)
  - Category: `other`
  - Context: 로 등록하고 넘어감`
  - Code: `- Code: `- 30분 초과 예상이면 TODO로 등록하고 넘어감``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:180](docs/TECH_DEBT_INVENTORY.md#L180)
  - Category: `other`
  - Context: ]** [.agent/workflows/session-workflow.md:50](.agent/workflows/session-workflow.md#L50)
  - Code: `- **[TODO]** [.agent/workflows/session-workflow.md:50](.agent/workflows/session-workflow.md#L50)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:183](docs/TECH_DEBT_INVENTORY.md#L183)
  - Category: `other`
  - Context: ``
  - Code: `- Code: `- `다음 TODO```

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:185](docs/TECH_DEBT_INVENTORY.md#L185)
  - Category: `other`
  - Context: ]** [.agent/workflows/session-workflow.md:87](.agent/workflows/session-workflow.md#L87)
  - Code: `- **[TODO]** [.agent/workflows/session-workflow.md:87](.agent/workflows/session-workflow.md#L87)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:188](docs/TECH_DEBT_INVENTORY.md#L188)
  - Category: `other`
  - Context: **: [항목 나열]`
  - Code: `- Code: `- **미완료 TODO**: [항목 나열]``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:190](docs/TECH_DEBT_INVENTORY.md#L190)
  - Category: `other`
  - Context: ]** [.agent/workflows/session-workflow.md:148](.agent/workflows/session-workflow.md#L148)
  - Code: `- **[TODO]** [.agent/workflows/session-workflow.md:148](.agent/workflows/session-workflow.md#L148)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:193](docs/TECH_DEBT_INVENTORY.md#L193)
  - Category: `other`
  - Context: **: 구체적이고 실행 가능한 항목`
  - Code: `- Code: `- **다음 TODO**: 구체적이고 실행 가능한 항목``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:195](docs/TECH_DEBT_INVENTORY.md#L195)
  - Category: `other`
  - Context: ]** [.agent/workflows/session-workflow.md:186](.agent/workflows/session-workflow.md#L186)
  - Code: `- **[TODO]** [.agent/workflows/session-workflow.md:186](.agent/workflows/session-workflow.md#L186)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:198](docs/TECH_DEBT_INVENTORY.md#L198)
  - Category: `other`
  - Context: `
  - Code: `- Code: `### 다음 세션 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:200](docs/TECH_DEBT_INVENTORY.md#L200)
  - Category: `other`
  - Context: ]** [.sessions/README.md:49](.sessions/README.md#L49)
  - Code: `- **[TODO]** [.sessions/README.md:49](.sessions/README.md#L49)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:203](docs/TECH_DEBT_INVENTORY.md#L203)
  - Category: `other`
  - Context: **: Handoff tasks`
  - Code: `- Code: `- **Next Agent TODO**: Handoff tasks``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:205](docs/TECH_DEBT_INVENTORY.md#L205)
  - Category: `other`
  - Context: ]** [.sessions/SESSION_LOG_2026-03-23.md:32](.sessions/SESSION_LOG_2026-03-23.md#L32)
  - Code: `- **[TODO]** [.sessions/SESSION_LOG_2026-03-23.md:32](.sessions/SESSION_LOG_2026-03-23.md#L32)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:208](docs/TECH_DEBT_INVENTORY.md#L208)
  - Category: `other`
  - Context: /IN_PROGRESS/DONE, priority levels, tool assignment guide`
  - Code: `- Code: `- **Features**: TODO/IN_PROGRESS/DONE, priority levels, tool assignment guide``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:210](docs/TECH_DEBT_INVENTORY.md#L210)
  - Category: `other`
  - Context: ]** [.sessions/SESSION_LOG_2026-03-23.md:160](.sessions/SESSION_LOG_2026-03-23.md#L160)
  - Code: `- **[TODO]** [.sessions/SESSION_LOG_2026-03-23.md:160](.sessions/SESSION_LOG_2026-03-23.md#L160)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:213](docs/TECH_DEBT_INVENTORY.md#L213)
  - Category: `other`
  - Context: `
  - Code: `- Code: `## Next Agent TODO``

- **[XXX]** [docs/TECH_DEBT_INVENTORY.md:215](docs/TECH_DEBT_INVENTORY.md#L215)
  - Category: `other`
  - Context: ]** [AgriGuard/contracts/package-lock.json:6142](AgriGuard/contracts/package-lock.json#L6142)
  - Code: `- **[XXX]** [AgriGuard/contracts/package-lock.json:6142](AgriGuard/contracts/package-lock.json#L6142)`

- **[XXX]** [docs/TECH_DEBT_INVENTORY.md:218](docs/TECH_DEBT_INVENTORY.md#L218)
  - Category: `other`
  - Context: evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",`
  - Code: `- Code: `"integrity": "sha512-YZo3K82SD7Riyi0E1EQPojLz7kpepnSQI9IyPbHHg1XXXevb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",``

- **[XXX]** [docs/TECH_DEBT_INVENTORY.md:220](docs/TECH_DEBT_INVENTORY.md#L220)
  - Category: `other`
  - Context: ]** [AgriGuard/frontend/package-lock.json:1475](AgriGuard/frontend/package-lock.json#L1475)
  - Code: `- **[XXX]** [AgriGuard/frontend/package-lock.json:1475](AgriGuard/frontend/package-lock.json#L1475)`

- **[XXX]** [docs/TECH_DEBT_INVENTORY.md:223](docs/TECH_DEBT_INVENTORY.md#L223)
  - Category: `other`
  - Context: /8R7JOTXStz/nBbRw==",`
  - Code: `- Code: `"integrity": "sha512-XREFCPo6ksxVzP4E0ekD5aMdf8WMwmdNaz6vuvxgI40UaEiu6q3p8X52aU6GdyvLY3XXX/8R7JOTXStz/nBbRw==",``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:225](docs/TECH_DEBT_INVENTORY.md#L225)
  - Category: `other`
  - Context: ]** [CONTEXT.md:14](CONTEXT.md#L14)
  - Code: `- **[TODO]** [CONTEXT.md:14](CONTEXT.md#L14)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:228](docs/TECH_DEBT_INVENTORY.md#L228)
  - Category: `other`
  - Context: /IN_PROGRESS/DONE)`
  - Code: `- Code: `2. **[TASKS.md](TASKS.md)** - Active task board (TODO/IN_PROGRESS/DONE)``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:230](docs/TECH_DEBT_INVENTORY.md#L230)
  - Category: `bug`
  - Context: ]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:141](SYSTEM_DEBUG_REPORT_2026-03-24.md#L141)
  - Code: `- **[TODO]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:141](SYSTEM_DEBUG_REPORT_2026-03-24.md#L141)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:233](docs/TECH_DEBT_INVENTORY.md#L233)
  - Category: `testing`
  - Context: **: Test instructor upgrade for Google GenAI`
  - Code: `- Code: `3. 🔲 **TODO**: Test instructor upgrade for Google GenAI``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:235](docs/TECH_DEBT_INVENTORY.md#L235)
  - Category: `other`
  - Context: ]** [TASKS.md:4](TASKS.md#L4)
  - Code: `- **[TODO]** [TASKS.md:4](TASKS.md#L4)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:238](docs/TECH_DEBT_INVENTORY.md#L238)
  - Category: `other`
  - Context: / IN_PROGRESS / DONE)`
  - Code: `- Code: `**Board Type**: Kanban (TODO / IN_PROGRESS / DONE)``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:240](docs/TECH_DEBT_INVENTORY.md#L240)
  - Category: `other`
  - Context: ]** [TASKS.md:8](TASKS.md#L8)
  - Code: `- **[TODO]** [TASKS.md:8](TASKS.md#L8)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:243](docs/TECH_DEBT_INVENTORY.md#L243)
  - Category: `other`
  - Context: `
  - Code: `- Code: `## TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:245](docs/TECH_DEBT_INVENTORY.md#L245)
  - Category: `other`
  - Context: ]** [TASKS.md:10](TASKS.md#L10)
  - Code: `- **[TODO]** [TASKS.md:10](TASKS.md#L10)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:248](docs/TECH_DEBT_INVENTORY.md#L248)
  - Category: `other`
  - Context: *`
  - Code: `- Code: `*No tasks in TODO*``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:250](docs/TECH_DEBT_INVENTORY.md#L250)
  - Category: `other`
  - Context: ]** [TASK_COMPLETION_REPORT_2026-03-24.md:96](TASK_COMPLETION_REPORT_2026-03-24.md#L96)
  - Code: `- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:96](TASK_COMPLETION_REPORT_2026-03-24.md#L96)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:253](docs/TECH_DEBT_INVENTORY.md#L253)
  - Category: `documentation`
  - Context: Comment Audit Results**:`
  - Code: `- Code: `**TODO Comment Audit Results**:``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:255](docs/TECH_DEBT_INVENTORY.md#L255)
  - Category: `other`
  - Context: ]** [TASK_COMPLETION_REPORT_2026-03-24.md:98](TASK_COMPLETION_REPORT_2026-03-24.md#L98)
  - Code: `- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:98](TASK_COMPLETION_REPORT_2026-03-24.md#L98)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:258](docs/TECH_DEBT_INVENTORY.md#L258)
  - Category: `documentation`
  - Context: comments found: 4 across 3 Python files`
  - Code: `- Code: `Total TODO comments found: 4 across 3 Python files``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:260](docs/TECH_DEBT_INVENTORY.md#L260)
  - Category: `other`
  - Context: ]** [TASK_COMPLETION_REPORT_2026-03-24.md:103](TASK_COMPLETION_REPORT_2026-03-24.md#L103)
  - Code: `- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:103](TASK_COMPLETION_REPORT_2026-03-24.md#L103)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:263](docs/TECH_DEBT_INVENTORY.md#L263)
  - Category: `other`
  - Context: Integrate with crawler.py and ntis_crawler.py`
  - Code: `- Code: `- TODO: Integrate with crawler.py and ntis_crawler.py``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:265](docs/TECH_DEBT_INVENTORY.md#L265)
  - Category: `other`
  - Context: ]** [TASK_COMPLETION_REPORT_2026-03-24.md:106](TASK_COMPLETION_REPORT_2026-03-24.md#L106)
  - Code: `- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:106](TASK_COMPLETION_REPORT_2026-03-24.md#L106)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:268](docs/TECH_DEBT_INVENTORY.md#L268)
  - Category: `other`
  - Context: Integrate with vector_store.py and vc_crawler.py`
  - Code: `- Code: `- TODO: Integrate with vector_store.py and vc_crawler.py``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:270](docs/TECH_DEBT_INVENTORY.md#L270)
  - Category: `other`
  - Context: ]** [TASK_COMPLETION_REPORT_2026-03-24.md:109](TASK_COMPLETION_REPORT_2026-03-24.md#L109)
  - Code: `- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:109](TASK_COMPLETION_REPORT_2026-03-24.md#L109)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:273](docs/TECH_DEBT_INVENTORY.md#L273)
  - Category: `other`
  - Context: 실제 Canva API 통신 로직 병합`
  - Code: `- Code: `- TODO: 실제 Canva API 통신 로직 병합``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:275](docs/TECH_DEBT_INVENTORY.md#L275)
  - Category: `other`
  - Context: ]** [TASK_COMPLETION_REPORT_2026-03-24.md:112](TASK_COMPLETION_REPORT_2026-03-24.md#L112)
  - Code: `- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:112](TASK_COMPLETION_REPORT_2026-03-24.md#L112)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:278](docs/TECH_DEBT_INVENTORY.md#L278)
  - Category: `documentation`
  - Context: s (meta comment, not actionable)`
  - Code: `- Code: `- Comment about extracting TODOs (meta comment, not actionable)``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:280](docs/TECH_DEBT_INVENTORY.md#L280)
  - Category: `other`
  - Context: ]** [TASK_COMPLETION_REPORT_2026-03-24.md:175](TASK_COMPLETION_REPORT_2026-03-24.md#L175)
  - Code: `- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:175](TASK_COMPLETION_REPORT_2026-03-24.md#L175)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:283](docs/TECH_DEBT_INVENTORY.md#L283)
  - Category: `other`
  - Context: → Linear migration (4 items identified)`
  - Code: `- Code: `7. ✅ Planned TODO → Linear migration (4 items identified)``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:285](docs/TECH_DEBT_INVENTORY.md#L285)
  - Category: `other`
  - Context: ]** [TASK_COMPLETION_REPORT_2026-03-24.md:185](TASK_COMPLETION_REPORT_2026-03-24.md#L185)
  - Code: `- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:185](TASK_COMPLETION_REPORT_2026-03-24.md#L185)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:288](docs/TECH_DEBT_INVENTORY.md#L288)
  - Category: `other`
  - Context: s**: `python scripts/linear_sync.py` (requires LINEAR_API_KEY)`
  - Code: `- Code: `4. **Migrate TODOs**: `python scripts/linear_sync.py` (requires LINEAR_API_KEY)``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:290](docs/TECH_DEBT_INVENTORY.md#L290)
  - Category: `other`
  - Context: ]** [TASK_COMPLETION_REPORT_2026-03-24.md:190](TASK_COMPLETION_REPORT_2026-03-24.md#L190)
  - Code: `- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:190](TASK_COMPLETION_REPORT_2026-03-24.md#L190)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:293](docs/TECH_DEBT_INVENTORY.md#L293)
  - Category: `other`
  - Context: migration`
  - Code: `- Code: `- ✅ **Mid-term** (next sprint): Frontend updates, TODO migration``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:295](docs/TECH_DEBT_INVENTORY.md#L295)
  - Category: `other`
  - Context: ]** [TASK_COMPLETION_REPORT_2026-03-24.md:205](TASK_COMPLETION_REPORT_2026-03-24.md#L205)
  - Code: `- **[TODO]** [TASK_COMPLETION_REPORT_2026-03-24.md:205](TASK_COMPLETION_REPORT_2026-03-24.md#L205)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:298](docs/TECH_DEBT_INVENTORY.md#L298)
  - Category: `documentation`
  - Context: comments to migrate`
  - Code: `- Code: `**Technical Debt**: 3 TODO comments to migrate``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:300](docs/TECH_DEBT_INVENTORY.md#L300)
  - Category: `other`
  - Context: ]** [desci-platform/IMPROVEMENT_PLAN.md:39](desci-platform/IMPROVEMENT_PLAN.md#L39)
  - Code: `- **[TODO]** [desci-platform/IMPROVEMENT_PLAN.md:39](desci-platform/IMPROVEMENT_PLAN.md#L39)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:303](docs/TECH_DEBT_INVENTORY.md#L303)
  - Category: `other`
  - Context: )`
  - Code: `- Code: `## 5. 다음 단계 (TODO)``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:305](docs/TECH_DEBT_INVENTORY.md#L305)
  - Category: `other`
  - Context: ]** [desci-platform/biolinker/services/agent_graph.py:70](desci-platform/biolinker/services/agent_graph.py#L70)
  - Code: `- **[TODO]** [desci-platform/biolinker/services/agent_graph.py:70](desci-platform/biolinker/services/agent_graph.py#L70)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:308](docs/TECH_DEBT_INVENTORY.md#L308)
  - Category: `other`
  - Context: Integrate with crawler.py and ntis_crawler.py`
  - Code: `- Code: `# TODO: Integrate with crawler.py and ntis_crawler.py``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:310](docs/TECH_DEBT_INVENTORY.md#L310)
  - Category: `other`
  - Context: ]** [desci-platform/biolinker/services/agent_graph.py:125](desci-platform/biolinker/services/agent_graph.py#L125)
  - Code: `- **[TODO]** [desci-platform/biolinker/services/agent_graph.py:125](desci-platform/biolinker/services/agent_graph.py#L125)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:313](docs/TECH_DEBT_INVENTORY.md#L313)
  - Category: `other`
  - Context: Integrate with vector_store.py and vc_crawler.py`
  - Code: `- Code: `# TODO: Integrate with vector_store.py and vc_crawler.py``

- **[XXX]** [docs/TECH_DEBT_INVENTORY.md:315](docs/TECH_DEBT_INVENTORY.md#L315)
  - Category: `other`
  - Context: ]** [desci-platform/contracts/package-lock.json:5865](desci-platform/contracts/package-lock.json#L5865)
  - Code: `- **[XXX]** [desci-platform/contracts/package-lock.json:5865](desci-platform/contracts/package-lock.json#L5865)`

- **[XXX]** [docs/TECH_DEBT_INVENTORY.md:318](docs/TECH_DEBT_INVENTORY.md#L318)
  - Category: `other`
  - Context: evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",`
  - Code: `- Code: `"integrity": "sha512-YZo3K82SD7Riyi0E1EQPojLz7kpepnSQI9IyPbHHg1XXXevb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:320](docs/TECH_DEBT_INVENTORY.md#L320)
  - Category: `other`
  - Context: ]** [docs/WORKSPACE-STATUS-2026-03-22.md:98](docs/WORKSPACE-STATUS-2026-03-22.md#L98)
  - Code: `- **[TODO]** [docs/WORKSPACE-STATUS-2026-03-22.md:98](docs/WORKSPACE-STATUS-2026-03-22.md#L98)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:323](docs/TECH_DEBT_INVENTORY.md#L323)
  - Category: `other`
  - Context: `
  - Code: `- Code: `## 남은 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:325](docs/TECH_DEBT_INVENTORY.md#L325)
  - Category: `other`
  - Context: ]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:185](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L185)
  - Code: `- **[TODO]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:185](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L185)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:328](docs/TECH_DEBT_INVENTORY.md#L328)
  - Category: `other`
  - Context: | Config exists, not integrated |`
  - Code: `- Code: `| **C-4: Canva Visuals** | ⏭️ TODO | Config exists, not integrated |``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:330](docs/TECH_DEBT_INVENTORY.md#L330)
  - Category: `other`
  - Context: ]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:186](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L186)
  - Code: `- **[TODO]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:186](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L186)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:333](docs/TECH_DEBT_INVENTORY.md#L333)
  - Category: `other`
  - Context: | Only Telegram/Discord |`
  - Code: `- Code: `| **C-5: Slack/Email Alerts** | ⏭️ TODO | Only Telegram/Discord |``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:335](docs/TECH_DEBT_INVENTORY.md#L335)
  - Category: `other`
  - Context: ]** [getdaytrends/canva.py:26](getdaytrends/canva.py#L26)
  - Code: `- **[TODO]** [getdaytrends/canva.py:26](getdaytrends/canva.py#L26)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:338](docs/TECH_DEBT_INVENTORY.md#L338)
  - Category: `other`
  - Context: 실제 Canva API 통신 로직 병합`
  - Code: `- Code: `# TODO: 실제 Canva API 통신 로직 병합``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:340](docs/TECH_DEBT_INVENTORY.md#L340)
  - Category: `other`
  - Context: ]** [getdaytrends/generation/audit.py:15](getdaytrends/generation/audit.py#L15)
  - Code: `- **[TODO]** [getdaytrends/generation/audit.py:15](getdaytrends/generation/audit.py#L15)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:343](docs/TECH_DEBT_INVENTORY.md#L343)
  - Category: `other`
  - Context: generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.`
  - Code: `- Code: `TODO: generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:345](docs/TECH_DEBT_INVENTORY.md#L345)
  - Category: `other`
  - Context: ]** [getdaytrends/generation/prompts.py:13](getdaytrends/generation/prompts.py#L13)
  - Code: `- **[TODO]** [getdaytrends/generation/prompts.py:13](getdaytrends/generation/prompts.py#L13)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:348](docs/TECH_DEBT_INVENTORY.md#L348)
  - Category: `other`
  - Context: generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.`
  - Code: `- Code: `TODO: generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:350](docs/TECH_DEBT_INVENTORY.md#L350)
  - Category: `other`
  - Context: ]** [scripts/workspace_summary.py:7](scripts/workspace_summary.py#L7)
  - Code: `- **[TODO]** [scripts/workspace_summary.py:7](scripts/workspace_summary.py#L7)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:353](docs/TECH_DEBT_INVENTORY.md#L353)
  - Category: `other`
  - Context: 추출`
  - Code: `- Code: `- 최신 세션 히스토리 → TODO 추출``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:355](docs/TECH_DEBT_INVENTORY.md#L355)
  - Category: `other`
  - Context: ]** [scripts/workspace_summary.py:64](scripts/workspace_summary.py#L64)
  - Code: `- **[TODO]** [scripts/workspace_summary.py:64](scripts/workspace_summary.py#L64)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:358](docs/TECH_DEBT_INVENTORY.md#L358)
  - Category: `other`
  - Context: 추출."""`
  - Code: `- Code: `"""최신 세션 히스토리에서 TODO 추출."""``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:360](docs/TECH_DEBT_INVENTORY.md#L360)
  - Category: `other`
  - Context: ]** [scripts/workspace_summary.py:80](scripts/workspace_summary.py#L80)
  - Code: `- **[TODO]** [scripts/workspace_summary.py:80](scripts/workspace_summary.py#L80)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:363](docs/TECH_DEBT_INVENTORY.md#L363)
  - Category: `other`
  - Context: 추출`
  - Code: `- Code: `# TODO 추출``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:365](docs/TECH_DEBT_INVENTORY.md#L365)
  - Category: `other`
  - Context: ]** [scripts/workspace_summary.py:83](scripts/workspace_summary.py#L83)
  - Code: `- **[TODO]** [scripts/workspace_summary.py:83](scripts/workspace_summary.py#L83)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:368](docs/TECH_DEBT_INVENTORY.md#L368)
  - Category: `other`
  - Context: " in line or "다음 세션" in line:`
  - Code: `- Code: `if "다음 TODO" in line or "다음 세션" in line:``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:370](docs/TECH_DEBT_INVENTORY.md#L370)
  - Category: `other`
  - Context: ]** [scripts/workspace_summary.py:194](scripts/workspace_summary.py#L194)
  - Code: `- **[TODO]** [scripts/workspace_summary.py:194](scripts/workspace_summary.py#L194)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:373](docs/TECH_DEBT_INVENTORY.md#L373)
  - Category: `other`
  - Context: `
  - Code: `- Code: `# 이전 세션 TODO``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:375](docs/TECH_DEBT_INVENTORY.md#L375)
  - Category: `other`
  - Context: ]** [scripts/workspace_summary.py:198](scripts/workspace_summary.py#L198)
  - Code: `- **[TODO]** [scripts/workspace_summary.py:198](scripts/workspace_summary.py#L198)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:378](docs/TECH_DEBT_INVENTORY.md#L378)
  - Category: `other`
  - Context: ({len(todos['todos'])}개):")`
  - Code: `- Code: `lines.append(f"\n🎯 미완료 TODO ({len(todos['todos'])}개):")``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:380](docs/TECH_DEBT_INVENTORY.md#L380)
  - Category: `other`
  - Context: ]** [scripts/workspace_summary.py:225](scripts/workspace_summary.py#L225)
  - Code: `- **[TODO]** [scripts/workspace_summary.py:225](scripts/workspace_summary.py#L225)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:383](docs/TECH_DEBT_INVENTORY.md#L383)
  - Category: `other`
  - Context: 이어서 작업")`
  - Code: `- Code: `lines.append(f"   3. 이전 세션 TODO 이어서 작업")``

- **[FIXME]** [docs/TECH_DEBT_INVENTORY.md:550](docs/TECH_DEBT_INVENTORY.md#L550)
  - Category: `documentation`
  - Context: Comments (13 files, 23 occurrences)
  - Code: `- /FIXME Comments (13 files, 23 occurrences)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:592](docs/TECH_DEBT_INVENTORY.md#L592)
  - Category: `bug`
  - Context: ] comments to Linear issues
  - Code: `- [TODO] comments to Linear issues`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:595](docs/TECH_DEBT_INVENTORY.md#L595)
  - Category: `bug`
  - Context: ] /FIXME Comments (13 files, 23 occurrences)
  - Code: `- [TODO] /FIXME Comments (13 files, 23 occurrences)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:598](docs/TECH_DEBT_INVENTORY.md#L598)
  - Category: `bug`
  - Context: ] comments to Linear issues
  - Code: `- [TODO] comments to Linear issues`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:601](docs/TECH_DEBT_INVENTORY.md#L601)
  - Category: `bug`
  - Context: ] comments → Linear issues
  - Code: `- [TODO] comments → Linear issues`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:604](docs/TECH_DEBT_INVENTORY.md#L604)
  - Category: `bug`
  - Context: ] → Linear Issues Migration Plan ✅
  - Code: `- [TODO] → Linear Issues Migration Plan ✅`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:607](docs/TECH_DEBT_INVENTORY.md#L607)
  - Category: `bug`
  - Context: ] s into Linear issues
  - Code: `- [TODO] s into Linear issues`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:610](docs/TECH_DEBT_INVENTORY.md#L610)
  - Category: `other`
  - Context: ] /IN_PROGRESS/DONE)
  - Code: `- [TODO] /IN_PROGRESS/DONE)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:613](docs/TECH_DEBT_INVENTORY.md#L613)
  - Category: `testing`
  - Context: ] **: Test instructor upgrade for Google GenAI
  - Code: `- [TODO] **: Test instructor upgrade for Google GenAI`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:616](docs/TECH_DEBT_INVENTORY.md#L616)
  - Category: `other`
  - Context: ] / IN_PROGRESS / DONE)
  - Code: `- [TODO] / IN_PROGRESS / DONE)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:619](docs/TECH_DEBT_INVENTORY.md#L619)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:622](docs/TECH_DEBT_INVENTORY.md#L622)
  - Category: `other`
  - Context: ] *
  - Code: `- [TODO] *`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:625](docs/TECH_DEBT_INVENTORY.md#L625)
  - Category: `documentation`
  - Context: ] Comment Audit Results**
  - Code: `- [TODO] Comment Audit Results**`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:628](docs/TECH_DEBT_INVENTORY.md#L628)
  - Category: `documentation`
  - Context: ] comments found: 4 across 3 Python files
  - Code: `- [TODO] comments found: 4 across 3 Python files`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:631](docs/TECH_DEBT_INVENTORY.md#L631)
  - Category: `other`
  - Context: ] Integrate with crawler.py and ntis_crawler.py
  - Code: `- [TODO] Integrate with crawler.py and ntis_crawler.py`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:634](docs/TECH_DEBT_INVENTORY.md#L634)
  - Category: `other`
  - Context: ] Integrate with vector_store.py and vc_crawler.py
  - Code: `- [TODO] Integrate with vector_store.py and vc_crawler.py`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:637](docs/TECH_DEBT_INVENTORY.md#L637)
  - Category: `other`
  - Context: ] 실제 Canva API 통신 로직 병합
  - Code: `- [TODO] 실제 Canva API 통신 로직 병합`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:640](docs/TECH_DEBT_INVENTORY.md#L640)
  - Category: `documentation`
  - Context: ] s (meta comment, not actionable)
  - Code: `- [TODO] s (meta comment, not actionable)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:643](docs/TECH_DEBT_INVENTORY.md#L643)
  - Category: `other`
  - Context: ] → Linear migration (4 items identified)
  - Code: `- [TODO] → Linear migration (4 items identified)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:646](docs/TECH_DEBT_INVENTORY.md#L646)
  - Category: `other`
  - Context: ] s**: `python scripts/linear_sync.py` (requires LINEAR_API_KEY)
  - Code: `- [TODO] s**: `python scripts/linear_sync.py` (requires LINEAR_API_KEY)`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:649](docs/TECH_DEBT_INVENTORY.md#L649)
  - Category: `other`
  - Context: ] migration
  - Code: `- [TODO] migration`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:652](docs/TECH_DEBT_INVENTORY.md#L652)
  - Category: `documentation`
  - Context: ] comments to migrate
  - Code: `- [TODO] comments to migrate`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:659](docs/TECH_DEBT_INVENTORY.md#L659)
  - Category: `other`
  - Context: ] 로 등록. 차기 스프린트에서 진행.
  - Code: `- [TODO] 로 등록. 차기 스프린트에서 진행.`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:662](docs/TECH_DEBT_INVENTORY.md#L662)
  - Category: `other`
  - Context: ] 주석 명시 |
  - Code: `- [TODO] 주석 명시 |`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:665](docs/TECH_DEBT_INVENTORY.md#L665)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:668](docs/TECH_DEBT_INVENTORY.md#L668)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:671](docs/TECH_DEBT_INVENTORY.md#L671)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:674](docs/TECH_DEBT_INVENTORY.md#L674)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:677](docs/TECH_DEBT_INVENTORY.md#L677)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:680](docs/TECH_DEBT_INVENTORY.md#L680)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:683](docs/TECH_DEBT_INVENTORY.md#L683)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:686](docs/TECH_DEBT_INVENTORY.md#L686)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:689](docs/TECH_DEBT_INVENTORY.md#L689)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:692](docs/TECH_DEBT_INVENTORY.md#L692)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:695](docs/TECH_DEBT_INVENTORY.md#L695)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:698](docs/TECH_DEBT_INVENTORY.md#L698)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:701](docs/TECH_DEBT_INVENTORY.md#L701)
  - Category: `other`
  - Context: ] 로 등록하고 넘어감
  - Code: `- [TODO] 로 등록하고 넘어감`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:704](docs/TECH_DEBT_INVENTORY.md#L704)
  - Category: `other`
  - Context: ] `
  - Code: `- [TODO] ``

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:707](docs/TECH_DEBT_INVENTORY.md#L707)
  - Category: `other`
  - Context: ] **: [항목 나열]
  - Code: `- [TODO] **: [항목 나열]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:710](docs/TECH_DEBT_INVENTORY.md#L710)
  - Category: `other`
  - Context: ] **: 구체적이고 실행 가능한 항목
  - Code: `- [TODO] **: 구체적이고 실행 가능한 항목`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:713](docs/TECH_DEBT_INVENTORY.md#L713)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:720](docs/TECH_DEBT_INVENTORY.md#L720)
  - Category: `other`
  - Context: ] 추출
  - Code: `- [TODO] 추출`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:723](docs/TECH_DEBT_INVENTORY.md#L723)
  - Category: `other`
  - Context: ] 추출."""
  - Code: `- [TODO] 추출."""`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:726](docs/TECH_DEBT_INVENTORY.md#L726)
  - Category: `other`
  - Context: ] 추출
  - Code: `- [TODO] 추출`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:729](docs/TECH_DEBT_INVENTORY.md#L729)
  - Category: `other`
  - Context: ] " in line or "다음 세션" in line
  - Code: `- [TODO] " in line or "다음 세션" in line`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:732](docs/TECH_DEBT_INVENTORY.md#L732)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:735](docs/TECH_DEBT_INVENTORY.md#L735)
  - Category: `other`
  - Context: ] ({len(todos['todos'])}개):")
  - Code: `- [TODO] ({len(todos['todos'])}개):")`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:738](docs/TECH_DEBT_INVENTORY.md#L738)
  - Category: `other`
  - Context: ] 이어서 작업")
  - Code: `- [TODO] 이어서 작업")`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:745](docs/TECH_DEBT_INVENTORY.md#L745)
  - Category: `other`
  - Context: ] | Config exists, not integrated |
  - Code: `- [TODO] | Config exists, not integrated |`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:748](docs/TECH_DEBT_INVENTORY.md#L748)
  - Category: `other`
  - Context: ] | Only Telegram/Discord |
  - Code: `- [TODO] | Only Telegram/Discord |`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:751](docs/TECH_DEBT_INVENTORY.md#L751)
  - Category: `other`
  - Context: ] 실제 Canva API 통신 로직 병합
  - Code: `- [TODO] 실제 Canva API 통신 로직 병합`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:754](docs/TECH_DEBT_INVENTORY.md#L754)
  - Category: `other`
  - Context: ] generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.
  - Code: `- [TODO] generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:757](docs/TECH_DEBT_INVENTORY.md#L757)
  - Category: `other`
  - Context: ] generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.
  - Code: `- [TODO] generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:764](docs/TECH_DEBT_INVENTORY.md#L764)
  - Category: `other`
  - Context: ] )
  - Code: `- [TODO] )`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:767](docs/TECH_DEBT_INVENTORY.md#L767)
  - Category: `other`
  - Context: ] Integrate with crawler.py and ntis_crawler.py
  - Code: `- [TODO] Integrate with crawler.py and ntis_crawler.py`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:770](docs/TECH_DEBT_INVENTORY.md#L770)
  - Category: `other`
  - Context: ] Integrate with vector_store.py and vc_crawler.py
  - Code: `- [TODO] Integrate with vector_store.py and vc_crawler.py`

- **[XXX]** [docs/TECH_DEBT_INVENTORY.md:773](docs/TECH_DEBT_INVENTORY.md#L773)
  - Category: `other`
  - Context: ] evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",
  - Code: `- [XXX] evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:780](docs/TECH_DEBT_INVENTORY.md#L780)
  - Category: `other`
  - Context: ] **: Handoff tasks
  - Code: `- [TODO] **: Handoff tasks`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:783](docs/TECH_DEBT_INVENTORY.md#L783)
  - Category: `other`
  - Context: ] /IN_PROGRESS/DONE, priority levels, tool assignment guide
  - Code: `- [TODO] /IN_PROGRESS/DONE, priority levels, tool assignment guide`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:786](docs/TECH_DEBT_INVENTORY.md#L786)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[XXX]** [docs/TECH_DEBT_INVENTORY.md:793](docs/TECH_DEBT_INVENTORY.md#L793)
  - Category: `other`
  - Context: ] evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",
  - Code: `- [XXX] evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",`

- **[XXX]** [docs/TECH_DEBT_INVENTORY.md:796](docs/TECH_DEBT_INVENTORY.md#L796)
  - Category: `other`
  - Context: ] /8R7JOTXStz/nBbRw==",
  - Code: `- [XXX] /8R7JOTXStz/nBbRw==",`

- **[TODO]** [docs/TECH_DEBT_INVENTORY.md:803](docs/TECH_DEBT_INVENTORY.md#L803)
  - Category: `other`
  - Context: ]
  - Code: `- [TODO]`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:11](docs/TECH_DEBT_P1_REVIEW.md#L11)
  - Category: `other`
  - Context: **(Linear 이슈 변환 관련)로, 실제 코드 버그가 아닙니다.
  - Code: `자동 수집된 P1 항목 6개는 **문서 내 메타 TODO**(Linear 이슈 변환 관련)로, 실제 코드 버그가 아닙니다.`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:13](docs/TECH_DEBT_P1_REVIEW.md#L13)
  - Category: `other`
  - Context: 는 3개이며, 모두 **리팩토링/마이그레이션 계획**으로 긴급하지 않습니다.
  - Code: `실제 코드베이스에서 발견된 의미있는 TODO는 3개이며, 모두 **리팩토링/마이그레이션 계획**으로 긴급하지 않습니다.`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:25](docs/TECH_DEBT_P1_REVIEW.md#L25)
  - Category: `other`
  - Context: 언급**입니다
  - Code: `모든 항목이 **문서 내부의 TODO 언급**입니다:`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:29](docs/TECH_DEBT_P1_REVIEW.md#L29)
  - Category: `bug`
  - Context: comments to Linear issues" |
  - Code: `| QC_REPORT_2026-03-24_SYSTEM_DEBUG.md | 388 | "Convert TODO comments to Linear issues" |`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:30](docs/TECH_DEBT_P1_REVIEW.md#L30)
  - Category: `bug`
  - Context: /FIXME 통계 및 Linear 마이그레이션 계획 |
  - Code: `| SYSTEM_DEBUG_REPORT_2026-03-24.md | 82, 150, 190 | TODO/FIXME 통계 및 Linear 마이그레이션 계획 |`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:36](docs/TECH_DEBT_P1_REVIEW.md#L36)
  - Category: `bug`
  - Context: ", "FIXME", "bug" 키워드를 동시에 포함한 문맥을 버그로 오분류
  - Code: `- 스크립트가 "TODO", "FIXME", "bug" 키워드를 동시에 포함한 문맥을 버그로 오분류`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:56](docs/TECH_DEBT_P1_REVIEW.md#L56)
  - Category: `other`
  - Context: (3개)
  - Code: `## 2. 실제 코드 내 TODO (3개)`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:68](docs/TECH_DEBT_P1_REVIEW.md#L68)
  - Category: `other`
  - Context: 실제 Canva API 통신 로직 병합
  - Code: `# TODO: 실제 Canva API 통신 로직 병합`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:95](docs/TECH_DEBT_P1_REVIEW.md#L95)
  - Category: `other`
  - Context: generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.
  - Code: `TODO: generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:130](docs/TECH_DEBT_P1_REVIEW.md#L130)
  - Category: `other`
  - Context: generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.
  - Code: `TODO: generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:163](docs/TECH_DEBT_P1_REVIEW.md#L163)
  - Category: `other`
  - Context: 추가 발견 (수동 검색)
  - Code: `## 3. 코드 내 TODO 추가 발견 (수동 검색)`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:169](docs/TECH_DEBT_P1_REVIEW.md#L169)
  - Category: `other`
  - Context: 확인 필요** (파일 크기 때문에 세부 내용 미확인)
  - Code: `**TODO 확인 필요** (파일 크기 때문에 세부 내용 미확인)`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:182](docs/TECH_DEBT_P1_REVIEW.md#L182)
  - Category: `bug`
  - Context: " + "bug" 키워드 동시 포함 → P1 (bug)
  - Code: `1. "TODO" + "bug" 키워드 동시 포함 → P1 (bug)`

- **[FIXME]** [docs/TECH_DEBT_P1_REVIEW.md:208](docs/TECH_DEBT_P1_REVIEW.md#L208)
  - Category: `bug`
  - Context: ", "BUG", "ERROR", "CRASH"])
  - Code: `elif any(k in context.upper() for k in ["FIXME", "BUG", "ERROR", "CRASH"]):`

- **[HACK]** [docs/TECH_DEBT_P1_REVIEW.md:212](docs/TECH_DEBT_P1_REVIEW.md#L212)
  - Category: `other`
  - Context: "
  - Code: `elif keyword == "HACK":`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:275](docs/TECH_DEBT_P1_REVIEW.md#L275)
  - Category: `other`
  - Context: )
  - Code: `- **P2**: 3개 (코드 내 리팩토링 TODO)`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:292](docs/TECH_DEBT_P1_REVIEW.md#L292)
  - Category: `other`
  - Context: 는 리팩토링/마이그레이션 계획일 뿐
  - Code: `2. **코드 품질 양호**: 실제 코드 내 TODO는 리팩토링/마이그레이션 계획일 뿐`

- **[TODO]** [docs/TECH_DEBT_P1_REVIEW.md:298](docs/TECH_DEBT_P1_REVIEW.md#L298)
  - Category: `other`
  - Context: 처리 (Phase 2, 4)
  - Code: `2. GetDayTrends 리팩토링 TODO 처리 (Phase 2, 4)`

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

### Other - 228개 항목

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

- **[P3]** [SYSTEM_ENHANCEMENT_PLAN.md:1149](SYSTEM_ENHANCEMENT_PLAN.md#L1149)
  - ) | 53 files | 26 files | grep -r "TODO" |

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

- **[P3]** [docs/SYSTEM_ENHANCEMENT_SUMMARY.md:53](docs/SYSTEM_ENHANCEMENT_SUMMARY.md#L53)
  - 제외 가능)

- **[P3]** [docs/SYSTEM_ENHANCEMENT_SUMMARY.md:60](docs/SYSTEM_ENHANCEMENT_SUMMARY.md#L60)
  - (실제 코드 버그 아님)

- **[P3]** [docs/SYSTEM_ENHANCEMENT_SUMMARY.md:146](docs/SYSTEM_ENHANCEMENT_SUMMARY.md#L146)
  - 추가 가능

- **[P3]** [docs/SYSTEM_ENHANCEMENT_SUMMARY.md:147](docs/SYSTEM_ENHANCEMENT_SUMMARY.md#L147)
  - 경고 추가 (선택)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:93](docs/TECH_DEBT_INVENTORY.md#L93)
  - ]** [TASK_COMPLETION_REPORT_2026-03-24.md:92](TASK_COMPLETION_REPORT_2026-03-24.md#L92)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:98](docs/TECH_DEBT_INVENTORY.md#L98)
  - ]** [TASK_COMPLETION_REPORT_2026-03-24.md:116](TASK_COMPLETION_REPORT_2026-03-24.md#L116)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:105](docs/TECH_DEBT_INVENTORY.md#L105)
  - ]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:23](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L23)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:108](docs/TECH_DEBT_INVENTORY.md#L108)
  - 로 등록. 차기 스프린트에서 진행.`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:110](docs/TECH_DEBT_INVENTORY.md#L110)
  - ]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:93](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L93)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:113](docs/TECH_DEBT_INVENTORY.md#L113)
  - 주석 명시 |`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:115](docs/TECH_DEBT_INVENTORY.md#L115)
  - ]** [.agent/session-history/2026-03-07.md:48](.agent/session-history/2026-03-07.md#L48)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:118](docs/TECH_DEBT_INVENTORY.md#L118)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:120](docs/TECH_DEBT_INVENTORY.md#L120)
  - ]** [.agent/session-history/2026-03-08.md:36](.agent/session-history/2026-03-08.md#L36)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:123](docs/TECH_DEBT_INVENTORY.md#L123)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:125](docs/TECH_DEBT_INVENTORY.md#L125)
  - ]** [.agent/session-history/2026-03-08.md:99](.agent/session-history/2026-03-08.md#L99)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:128](docs/TECH_DEBT_INVENTORY.md#L128)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:130](docs/TECH_DEBT_INVENTORY.md#L130)
  - ]** [.agent/session-history/2026-03-08.md:135](.agent/session-history/2026-03-08.md#L135)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:133](docs/TECH_DEBT_INVENTORY.md#L133)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:135](docs/TECH_DEBT_INVENTORY.md#L135)
  - ]** [.agent/session-history/2026-03-08.md:161](.agent/session-history/2026-03-08.md#L161)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:138](docs/TECH_DEBT_INVENTORY.md#L138)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:140](docs/TECH_DEBT_INVENTORY.md#L140)
  - ]** [.agent/session-history/2026-03-08.md:184](.agent/session-history/2026-03-08.md#L184)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:143](docs/TECH_DEBT_INVENTORY.md#L143)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:145](docs/TECH_DEBT_INVENTORY.md#L145)
  - ]** [.agent/session-history/2026-03-08.md:235](.agent/session-history/2026-03-08.md#L235)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:148](docs/TECH_DEBT_INVENTORY.md#L148)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:150](docs/TECH_DEBT_INVENTORY.md#L150)
  - ]** [.agent/session-history/2026-03-08.md:275](.agent/session-history/2026-03-08.md#L275)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:153](docs/TECH_DEBT_INVENTORY.md#L153)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:155](docs/TECH_DEBT_INVENTORY.md#L155)
  - ]** [.agent/session-history/2026-03-08.md:313](.agent/session-history/2026-03-08.md#L313)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:158](docs/TECH_DEBT_INVENTORY.md#L158)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:160](docs/TECH_DEBT_INVENTORY.md#L160)
  - ]** [.agent/session-history/2026-03-21.md:36](.agent/session-history/2026-03-21.md#L36)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:163](docs/TECH_DEBT_INVENTORY.md#L163)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:165](docs/TECH_DEBT_INVENTORY.md#L165)
  - ]** [.agent/session-history/2026-03-21.md:104](.agent/session-history/2026-03-21.md#L104)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:168](docs/TECH_DEBT_INVENTORY.md#L168)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:170](docs/TECH_DEBT_INVENTORY.md#L170)
  - ]** [.agent/session-history/2026-03-24.md:44](.agent/session-history/2026-03-24.md#L44)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:173](docs/TECH_DEBT_INVENTORY.md#L173)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:175](docs/TECH_DEBT_INVENTORY.md#L175)
  - ]** [.agent/workflows/qa-qc.md:110](.agent/workflows/qa-qc.md#L110)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:178](docs/TECH_DEBT_INVENTORY.md#L178)
  - 로 등록하고 넘어감`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:180](docs/TECH_DEBT_INVENTORY.md#L180)
  - ]** [.agent/workflows/session-workflow.md:50](.agent/workflows/session-workflow.md#L50)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:183](docs/TECH_DEBT_INVENTORY.md#L183)
  - ``

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:185](docs/TECH_DEBT_INVENTORY.md#L185)
  - ]** [.agent/workflows/session-workflow.md:87](.agent/workflows/session-workflow.md#L87)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:188](docs/TECH_DEBT_INVENTORY.md#L188)
  - **: [항목 나열]`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:190](docs/TECH_DEBT_INVENTORY.md#L190)
  - ]** [.agent/workflows/session-workflow.md:148](.agent/workflows/session-workflow.md#L148)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:193](docs/TECH_DEBT_INVENTORY.md#L193)
  - **: 구체적이고 실행 가능한 항목`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:195](docs/TECH_DEBT_INVENTORY.md#L195)
  - ]** [.agent/workflows/session-workflow.md:186](.agent/workflows/session-workflow.md#L186)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:198](docs/TECH_DEBT_INVENTORY.md#L198)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:200](docs/TECH_DEBT_INVENTORY.md#L200)
  - ]** [.sessions/README.md:49](.sessions/README.md#L49)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:203](docs/TECH_DEBT_INVENTORY.md#L203)
  - **: Handoff tasks`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:205](docs/TECH_DEBT_INVENTORY.md#L205)
  - ]** [.sessions/SESSION_LOG_2026-03-23.md:32](.sessions/SESSION_LOG_2026-03-23.md#L32)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:208](docs/TECH_DEBT_INVENTORY.md#L208)
  - /IN_PROGRESS/DONE, priority levels, tool assignment guide`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:210](docs/TECH_DEBT_INVENTORY.md#L210)
  - ]** [.sessions/SESSION_LOG_2026-03-23.md:160](.sessions/SESSION_LOG_2026-03-23.md#L160)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:213](docs/TECH_DEBT_INVENTORY.md#L213)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:215](docs/TECH_DEBT_INVENTORY.md#L215)
  - ]** [AgriGuard/contracts/package-lock.json:6142](AgriGuard/contracts/package-lock.json#L6142)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:218](docs/TECH_DEBT_INVENTORY.md#L218)
  - evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:220](docs/TECH_DEBT_INVENTORY.md#L220)
  - ]** [AgriGuard/frontend/package-lock.json:1475](AgriGuard/frontend/package-lock.json#L1475)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:223](docs/TECH_DEBT_INVENTORY.md#L223)
  - /8R7JOTXStz/nBbRw==",`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:225](docs/TECH_DEBT_INVENTORY.md#L225)
  - ]** [CONTEXT.md:14](CONTEXT.md#L14)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:228](docs/TECH_DEBT_INVENTORY.md#L228)
  - /IN_PROGRESS/DONE)`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:235](docs/TECH_DEBT_INVENTORY.md#L235)
  - ]** [TASKS.md:4](TASKS.md#L4)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:238](docs/TECH_DEBT_INVENTORY.md#L238)
  - / IN_PROGRESS / DONE)`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:240](docs/TECH_DEBT_INVENTORY.md#L240)
  - ]** [TASKS.md:8](TASKS.md#L8)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:243](docs/TECH_DEBT_INVENTORY.md#L243)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:245](docs/TECH_DEBT_INVENTORY.md#L245)
  - ]** [TASKS.md:10](TASKS.md#L10)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:248](docs/TECH_DEBT_INVENTORY.md#L248)
  - *`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:250](docs/TECH_DEBT_INVENTORY.md#L250)
  - ]** [TASK_COMPLETION_REPORT_2026-03-24.md:96](TASK_COMPLETION_REPORT_2026-03-24.md#L96)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:255](docs/TECH_DEBT_INVENTORY.md#L255)
  - ]** [TASK_COMPLETION_REPORT_2026-03-24.md:98](TASK_COMPLETION_REPORT_2026-03-24.md#L98)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:260](docs/TECH_DEBT_INVENTORY.md#L260)
  - ]** [TASK_COMPLETION_REPORT_2026-03-24.md:103](TASK_COMPLETION_REPORT_2026-03-24.md#L103)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:263](docs/TECH_DEBT_INVENTORY.md#L263)
  - Integrate with crawler.py and ntis_crawler.py`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:265](docs/TECH_DEBT_INVENTORY.md#L265)
  - ]** [TASK_COMPLETION_REPORT_2026-03-24.md:106](TASK_COMPLETION_REPORT_2026-03-24.md#L106)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:268](docs/TECH_DEBT_INVENTORY.md#L268)
  - Integrate with vector_store.py and vc_crawler.py`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:270](docs/TECH_DEBT_INVENTORY.md#L270)
  - ]** [TASK_COMPLETION_REPORT_2026-03-24.md:109](TASK_COMPLETION_REPORT_2026-03-24.md#L109)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:273](docs/TECH_DEBT_INVENTORY.md#L273)
  - 실제 Canva API 통신 로직 병합`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:275](docs/TECH_DEBT_INVENTORY.md#L275)
  - ]** [TASK_COMPLETION_REPORT_2026-03-24.md:112](TASK_COMPLETION_REPORT_2026-03-24.md#L112)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:280](docs/TECH_DEBT_INVENTORY.md#L280)
  - ]** [TASK_COMPLETION_REPORT_2026-03-24.md:175](TASK_COMPLETION_REPORT_2026-03-24.md#L175)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:283](docs/TECH_DEBT_INVENTORY.md#L283)
  - → Linear migration (4 items identified)`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:285](docs/TECH_DEBT_INVENTORY.md#L285)
  - ]** [TASK_COMPLETION_REPORT_2026-03-24.md:185](TASK_COMPLETION_REPORT_2026-03-24.md#L185)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:288](docs/TECH_DEBT_INVENTORY.md#L288)
  - s**: `python scripts/linear_sync.py` (requires LINEAR_API_KEY)`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:290](docs/TECH_DEBT_INVENTORY.md#L290)
  - ]** [TASK_COMPLETION_REPORT_2026-03-24.md:190](TASK_COMPLETION_REPORT_2026-03-24.md#L190)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:293](docs/TECH_DEBT_INVENTORY.md#L293)
  - migration`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:295](docs/TECH_DEBT_INVENTORY.md#L295)
  - ]** [TASK_COMPLETION_REPORT_2026-03-24.md:205](TASK_COMPLETION_REPORT_2026-03-24.md#L205)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:300](docs/TECH_DEBT_INVENTORY.md#L300)
  - ]** [desci-platform/IMPROVEMENT_PLAN.md:39](desci-platform/IMPROVEMENT_PLAN.md#L39)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:303](docs/TECH_DEBT_INVENTORY.md#L303)
  - )`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:305](docs/TECH_DEBT_INVENTORY.md#L305)
  - ]** [desci-platform/biolinker/services/agent_graph.py:70](desci-platform/biolinker/services/agent_graph.py#L70)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:308](docs/TECH_DEBT_INVENTORY.md#L308)
  - Integrate with crawler.py and ntis_crawler.py`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:310](docs/TECH_DEBT_INVENTORY.md#L310)
  - ]** [desci-platform/biolinker/services/agent_graph.py:125](desci-platform/biolinker/services/agent_graph.py#L125)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:313](docs/TECH_DEBT_INVENTORY.md#L313)
  - Integrate with vector_store.py and vc_crawler.py`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:315](docs/TECH_DEBT_INVENTORY.md#L315)
  - ]** [desci-platform/contracts/package-lock.json:5865](desci-platform/contracts/package-lock.json#L5865)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:318](docs/TECH_DEBT_INVENTORY.md#L318)
  - evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:320](docs/TECH_DEBT_INVENTORY.md#L320)
  - ]** [docs/WORKSPACE-STATUS-2026-03-22.md:98](docs/WORKSPACE-STATUS-2026-03-22.md#L98)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:323](docs/TECH_DEBT_INVENTORY.md#L323)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:325](docs/TECH_DEBT_INVENTORY.md#L325)
  - ]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:185](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L185)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:328](docs/TECH_DEBT_INVENTORY.md#L328)
  - | Config exists, not integrated |`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:330](docs/TECH_DEBT_INVENTORY.md#L330)
  - ]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:186](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L186)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:333](docs/TECH_DEBT_INVENTORY.md#L333)
  - | Only Telegram/Discord |`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:335](docs/TECH_DEBT_INVENTORY.md#L335)
  - ]** [getdaytrends/canva.py:26](getdaytrends/canva.py#L26)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:338](docs/TECH_DEBT_INVENTORY.md#L338)
  - 실제 Canva API 통신 로직 병합`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:340](docs/TECH_DEBT_INVENTORY.md#L340)
  - ]** [getdaytrends/generation/audit.py:15](getdaytrends/generation/audit.py#L15)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:343](docs/TECH_DEBT_INVENTORY.md#L343)
  - generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:345](docs/TECH_DEBT_INVENTORY.md#L345)
  - ]** [getdaytrends/generation/prompts.py:13](getdaytrends/generation/prompts.py#L13)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:348](docs/TECH_DEBT_INVENTORY.md#L348)
  - generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:350](docs/TECH_DEBT_INVENTORY.md#L350)
  - ]** [scripts/workspace_summary.py:7](scripts/workspace_summary.py#L7)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:353](docs/TECH_DEBT_INVENTORY.md#L353)
  - 추출`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:355](docs/TECH_DEBT_INVENTORY.md#L355)
  - ]** [scripts/workspace_summary.py:64](scripts/workspace_summary.py#L64)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:358](docs/TECH_DEBT_INVENTORY.md#L358)
  - 추출."""`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:360](docs/TECH_DEBT_INVENTORY.md#L360)
  - ]** [scripts/workspace_summary.py:80](scripts/workspace_summary.py#L80)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:363](docs/TECH_DEBT_INVENTORY.md#L363)
  - 추출`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:365](docs/TECH_DEBT_INVENTORY.md#L365)
  - ]** [scripts/workspace_summary.py:83](scripts/workspace_summary.py#L83)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:368](docs/TECH_DEBT_INVENTORY.md#L368)
  - " in line or "다음 세션" in line:`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:370](docs/TECH_DEBT_INVENTORY.md#L370)
  - ]** [scripts/workspace_summary.py:194](scripts/workspace_summary.py#L194)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:373](docs/TECH_DEBT_INVENTORY.md#L373)
  - `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:375](docs/TECH_DEBT_INVENTORY.md#L375)
  - ]** [scripts/workspace_summary.py:198](scripts/workspace_summary.py#L198)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:378](docs/TECH_DEBT_INVENTORY.md#L378)
  - ({len(todos['todos'])}개):")`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:380](docs/TECH_DEBT_INVENTORY.md#L380)
  - ]** [scripts/workspace_summary.py:225](scripts/workspace_summary.py#L225)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:383](docs/TECH_DEBT_INVENTORY.md#L383)
  - 이어서 작업")`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:610](docs/TECH_DEBT_INVENTORY.md#L610)
  - ] /IN_PROGRESS/DONE)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:616](docs/TECH_DEBT_INVENTORY.md#L616)
  - ] / IN_PROGRESS / DONE)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:619](docs/TECH_DEBT_INVENTORY.md#L619)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:622](docs/TECH_DEBT_INVENTORY.md#L622)
  - ] *

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:631](docs/TECH_DEBT_INVENTORY.md#L631)
  - ] Integrate with crawler.py and ntis_crawler.py

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:634](docs/TECH_DEBT_INVENTORY.md#L634)
  - ] Integrate with vector_store.py and vc_crawler.py

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:637](docs/TECH_DEBT_INVENTORY.md#L637)
  - ] 실제 Canva API 통신 로직 병합

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:643](docs/TECH_DEBT_INVENTORY.md#L643)
  - ] → Linear migration (4 items identified)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:646](docs/TECH_DEBT_INVENTORY.md#L646)
  - ] s**: `python scripts/linear_sync.py` (requires LINEAR_API_KEY)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:649](docs/TECH_DEBT_INVENTORY.md#L649)
  - ] migration

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:659](docs/TECH_DEBT_INVENTORY.md#L659)
  - ] 로 등록. 차기 스프린트에서 진행.

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:662](docs/TECH_DEBT_INVENTORY.md#L662)
  - ] 주석 명시 |

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:665](docs/TECH_DEBT_INVENTORY.md#L665)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:668](docs/TECH_DEBT_INVENTORY.md#L668)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:671](docs/TECH_DEBT_INVENTORY.md#L671)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:674](docs/TECH_DEBT_INVENTORY.md#L674)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:677](docs/TECH_DEBT_INVENTORY.md#L677)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:680](docs/TECH_DEBT_INVENTORY.md#L680)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:683](docs/TECH_DEBT_INVENTORY.md#L683)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:686](docs/TECH_DEBT_INVENTORY.md#L686)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:689](docs/TECH_DEBT_INVENTORY.md#L689)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:692](docs/TECH_DEBT_INVENTORY.md#L692)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:695](docs/TECH_DEBT_INVENTORY.md#L695)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:698](docs/TECH_DEBT_INVENTORY.md#L698)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:701](docs/TECH_DEBT_INVENTORY.md#L701)
  - ] 로 등록하고 넘어감

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:704](docs/TECH_DEBT_INVENTORY.md#L704)
  - ] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:707](docs/TECH_DEBT_INVENTORY.md#L707)
  - ] **: [항목 나열]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:710](docs/TECH_DEBT_INVENTORY.md#L710)
  - ] **: 구체적이고 실행 가능한 항목

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:713](docs/TECH_DEBT_INVENTORY.md#L713)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:720](docs/TECH_DEBT_INVENTORY.md#L720)
  - ] 추출

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:723](docs/TECH_DEBT_INVENTORY.md#L723)
  - ] 추출."""

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:726](docs/TECH_DEBT_INVENTORY.md#L726)
  - ] 추출

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:729](docs/TECH_DEBT_INVENTORY.md#L729)
  - ] " in line or "다음 세션" in line

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:732](docs/TECH_DEBT_INVENTORY.md#L732)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:735](docs/TECH_DEBT_INVENTORY.md#L735)
  - ] ({len(todos['todos'])}개):")

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:738](docs/TECH_DEBT_INVENTORY.md#L738)
  - ] 이어서 작업")

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:745](docs/TECH_DEBT_INVENTORY.md#L745)
  - ] | Config exists, not integrated |

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:748](docs/TECH_DEBT_INVENTORY.md#L748)
  - ] | Only Telegram/Discord |

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:751](docs/TECH_DEBT_INVENTORY.md#L751)
  - ] 실제 Canva API 통신 로직 병합

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:754](docs/TECH_DEBT_INVENTORY.md#L754)
  - ] generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:757](docs/TECH_DEBT_INVENTORY.md#L757)
  - ] generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:764](docs/TECH_DEBT_INVENTORY.md#L764)
  - ] )

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:767](docs/TECH_DEBT_INVENTORY.md#L767)
  - ] Integrate with crawler.py and ntis_crawler.py

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:770](docs/TECH_DEBT_INVENTORY.md#L770)
  - ] Integrate with vector_store.py and vc_crawler.py

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:773](docs/TECH_DEBT_INVENTORY.md#L773)
  - ] evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:780](docs/TECH_DEBT_INVENTORY.md#L780)
  - ] **: Handoff tasks

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:783](docs/TECH_DEBT_INVENTORY.md#L783)
  - ] /IN_PROGRESS/DONE, priority levels, tool assignment guide

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:786](docs/TECH_DEBT_INVENTORY.md#L786)
  - ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:793](docs/TECH_DEBT_INVENTORY.md#L793)
  - ] evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:796](docs/TECH_DEBT_INVENTORY.md#L796)
  - ] /8R7JOTXStz/nBbRw==",

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:803](docs/TECH_DEBT_INVENTORY.md#L803)
  - ]

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:11](docs/TECH_DEBT_P1_REVIEW.md#L11)
  - **(Linear 이슈 변환 관련)로, 실제 코드 버그가 아닙니다.

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:13](docs/TECH_DEBT_P1_REVIEW.md#L13)
  - 는 3개이며, 모두 **리팩토링/마이그레이션 계획**으로 긴급하지 않습니다.

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:25](docs/TECH_DEBT_P1_REVIEW.md#L25)
  - 언급**입니다

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:56](docs/TECH_DEBT_P1_REVIEW.md#L56)
  - (3개)

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:68](docs/TECH_DEBT_P1_REVIEW.md#L68)
  - 실제 Canva API 통신 로직 병합

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:95](docs/TECH_DEBT_P1_REVIEW.md#L95)
  - generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:130](docs/TECH_DEBT_P1_REVIEW.md#L130)
  - generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:163](docs/TECH_DEBT_P1_REVIEW.md#L163)
  - 추가 발견 (수동 검색)

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:169](docs/TECH_DEBT_P1_REVIEW.md#L169)
  - 확인 필요** (파일 크기 때문에 세부 내용 미확인)

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:212](docs/TECH_DEBT_P1_REVIEW.md#L212)
  - "

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:275](docs/TECH_DEBT_P1_REVIEW.md#L275)
  - )

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:292](docs/TECH_DEBT_P1_REVIEW.md#L292)
  - 는 리팩토링/마이그레이션 계획일 뿐

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:298](docs/TECH_DEBT_P1_REVIEW.md#L298)
  - 처리 (Phase 2, 4)

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

### Bug - 40개 항목

- **[P1]** [scripts/generate_tech_debt_inventory.py:5](scripts/generate_tech_debt_inventory.py#L5)
  - , FIXME, HACK, XXX 주석을 자동으로 수집하여

- **[P1]** [scripts/generate_tech_debt_inventory.py:25](scripts/generate_tech_debt_inventory.py#L25)
  - , FIXME, HACK, XXX

- **[P1]** [scripts/generate_tech_debt_inventory.py:64](scripts/generate_tech_debt_inventory.py#L64)
  - /FIXME/HACK/XXX 검색

- **[P1]** [scripts/generate_tech_debt_inventory.py:65](scripts/generate_tech_debt_inventory.py#L65)
  - ', 'FIXME', 'HACK', 'XXX']

- **[P1]** [scripts/generate_tech_debt_inventory.py:101](scripts/generate_tech_debt_inventory.py#L101)
  - fix this

- **[P1]** [scripts/generate_tech_debt_inventory.py:110](scripts/generate_tech_debt_inventory.py#L110)
  - ', 'FIXME', 'HACK', 'XXX']

- **[P1]** [scripts/generate_tech_debt_inventory.py:211](scripts/generate_tech_debt_inventory.py#L211)
  - , FIXME, HACK, XXX)을

- **[P3]** [QC_REPORT_2026-03-24_SYSTEM_DEBUG.md:388](QC_REPORT_2026-03-24_SYSTEM_DEBUG.md#L388)
  - comments to Linear issues

- **[P3]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:82](SYSTEM_DEBUG_REPORT_2026-03-24.md#L82)
  - /FIXME Comments (13 files, 23 occurrences)

- **[P3]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:150](SYSTEM_DEBUG_REPORT_2026-03-24.md#L150)
  - comments to Linear issues

- **[P3]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:190](SYSTEM_DEBUG_REPORT_2026-03-24.md#L190)
  - comments → Linear issues

- **[P3]** [SYSTEM_ENHANCEMENT_PLAN.md:109](SYSTEM_ENHANCEMENT_PLAN.md#L109)
  - /FIXME (145개 에러 핸들링 검토 필요)

- **[P3]** [SYSTEM_ENHANCEMENT_PLAN.md:321](SYSTEM_ENHANCEMENT_PLAN.md#L321)
  - /FIXME/HACK/XXX 존재

- **[P3]** [SYSTEM_ENHANCEMENT_PLAN.md:341](SYSTEM_ENHANCEMENT_PLAN.md#L341)
  - 주석 → GitHub Issue 자동 생성 (label: tech-debt)

- **[P3]** [SYSTEM_ENHANCEMENT_PLAN.md:354](SYSTEM_ENHANCEMENT_PLAN.md#L354)
  - /FIXME 50% 감소 (53 → 26개)

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:92](TASK_COMPLETION_REPORT_2026-03-24.md#L92)
  - → Linear Issues Migration Plan ✅

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:116](TASK_COMPLETION_REPORT_2026-03-24.md#L116)
  - s into Linear issues

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:11](docs/TECH_DEBT_INVENTORY.md#L11)
  - , FIXME, HACK, XXX)을

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:73](docs/TECH_DEBT_INVENTORY.md#L73)
  - ]** [QC_REPORT_2026-03-24_SYSTEM_DEBUG.md:388](QC_REPORT_2026-03-24_SYSTEM_DEBUG.md#L388)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:76](docs/TECH_DEBT_INVENTORY.md#L76)
  - comments to Linear issues`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:78](docs/TECH_DEBT_INVENTORY.md#L78)
  - ]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:82](SYSTEM_DEBUG_REPORT_2026-03-24.md#L82)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:81](docs/TECH_DEBT_INVENTORY.md#L81)
  - /FIXME Comments (13 files, 23 occurrences)`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:83](docs/TECH_DEBT_INVENTORY.md#L83)
  - ]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:150](SYSTEM_DEBUG_REPORT_2026-03-24.md#L150)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:86](docs/TECH_DEBT_INVENTORY.md#L86)
  - comments to Linear issues`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:88](docs/TECH_DEBT_INVENTORY.md#L88)
  - ]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:190](SYSTEM_DEBUG_REPORT_2026-03-24.md#L190)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:91](docs/TECH_DEBT_INVENTORY.md#L91)
  - comments → Linear issues`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:96](docs/TECH_DEBT_INVENTORY.md#L96)
  - → Linear Issues Migration Plan ✅`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:101](docs/TECH_DEBT_INVENTORY.md#L101)
  - s into Linear issues`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:230](docs/TECH_DEBT_INVENTORY.md#L230)
  - ]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:141](SYSTEM_DEBUG_REPORT_2026-03-24.md#L141)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:592](docs/TECH_DEBT_INVENTORY.md#L592)
  - ] comments to Linear issues

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:595](docs/TECH_DEBT_INVENTORY.md#L595)
  - ] /FIXME Comments (13 files, 23 occurrences)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:598](docs/TECH_DEBT_INVENTORY.md#L598)
  - ] comments to Linear issues

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:601](docs/TECH_DEBT_INVENTORY.md#L601)
  - ] comments → Linear issues

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:604](docs/TECH_DEBT_INVENTORY.md#L604)
  - ] → Linear Issues Migration Plan ✅

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:607](docs/TECH_DEBT_INVENTORY.md#L607)
  - ] s into Linear issues

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:29](docs/TECH_DEBT_P1_REVIEW.md#L29)
  - comments to Linear issues" |

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:30](docs/TECH_DEBT_P1_REVIEW.md#L30)
  - /FIXME 통계 및 Linear 마이그레이션 계획 |

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:36](docs/TECH_DEBT_P1_REVIEW.md#L36)
  - ", "FIXME", "bug" 키워드를 동시에 포함한 문맥을 버그로 오분류

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:182](docs/TECH_DEBT_P1_REVIEW.md#L182)
  - " + "bug" 키워드 동시 포함 → P1 (bug)

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:208](docs/TECH_DEBT_P1_REVIEW.md#L208)
  - ", "BUG", "ERROR", "CRASH"])

### Documentation - 14개 항목

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:96](TASK_COMPLETION_REPORT_2026-03-24.md#L96)
  - Comment Audit Results**

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:98](TASK_COMPLETION_REPORT_2026-03-24.md#L98)
  - comments found: 4 across 3 Python files

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:112](TASK_COMPLETION_REPORT_2026-03-24.md#L112)
  - s (meta comment, not actionable)

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:205](TASK_COMPLETION_REPORT_2026-03-24.md#L205)
  - comments to migrate

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:80](docs/TECH_DEBT_INVENTORY.md#L80)
  - Comments (13 files, 23 occurrences)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:253](docs/TECH_DEBT_INVENTORY.md#L253)
  - Comment Audit Results**:`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:258](docs/TECH_DEBT_INVENTORY.md#L258)
  - comments found: 4 across 3 Python files`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:278](docs/TECH_DEBT_INVENTORY.md#L278)
  - s (meta comment, not actionable)`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:298](docs/TECH_DEBT_INVENTORY.md#L298)
  - comments to migrate`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:550](docs/TECH_DEBT_INVENTORY.md#L550)
  - Comments (13 files, 23 occurrences)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:625](docs/TECH_DEBT_INVENTORY.md#L625)
  - ] Comment Audit Results**

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:628](docs/TECH_DEBT_INVENTORY.md#L628)
  - ] comments found: 4 across 3 Python files

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:640](docs/TECH_DEBT_INVENTORY.md#L640)
  - ] s (meta comment, not actionable)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:652](docs/TECH_DEBT_INVENTORY.md#L652)
  - ] comments to migrate

### Testing - 3개 항목

- **[P3]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:141](SYSTEM_DEBUG_REPORT_2026-03-24.md#L141)
  - **: Test instructor upgrade for Google GenAI

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:233](docs/TECH_DEBT_INVENTORY.md#L233)
  - **: Test instructor upgrade for Google GenAI`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:613](docs/TECH_DEBT_INVENTORY.md#L613)
  - ] **: Test instructor upgrade for Google GenAI

---

## 프로젝트별 상세

### docs - 212개 항목

**우선순위 분포**: P3: 212

- **[P3]** [docs/SYSTEM_ENHANCEMENT_SUMMARY.md:53](docs/SYSTEM_ENHANCEMENT_SUMMARY.md#L53)
  - [TODO] 제외 가능)

- **[P3]** [docs/SYSTEM_ENHANCEMENT_SUMMARY.md:60](docs/SYSTEM_ENHANCEMENT_SUMMARY.md#L60)
  - [TODO] (실제 코드 버그 아님)

- **[P3]** [docs/SYSTEM_ENHANCEMENT_SUMMARY.md:146](docs/SYSTEM_ENHANCEMENT_SUMMARY.md#L146)
  - [TODO] 추가 가능

- **[P3]** [docs/SYSTEM_ENHANCEMENT_SUMMARY.md:147](docs/SYSTEM_ENHANCEMENT_SUMMARY.md#L147)
  - [TODO] 경고 추가 (선택)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:11](docs/TECH_DEBT_INVENTORY.md#L11)
  - [TODO] , FIXME, HACK, XXX)을

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:73](docs/TECH_DEBT_INVENTORY.md#L73)
  - [TODO] ]** [QC_REPORT_2026-03-24_SYSTEM_DEBUG.md:388](QC_REPORT_2026-03-24_SYSTEM_DEBUG.md#L388)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:76](docs/TECH_DEBT_INVENTORY.md#L76)
  - [TODO] comments to Linear issues`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:78](docs/TECH_DEBT_INVENTORY.md#L78)
  - [TODO] ]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:82](SYSTEM_DEBUG_REPORT_2026-03-24.md#L82)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:80](docs/TECH_DEBT_INVENTORY.md#L80)
  - [FIXME] Comments (13 files, 23 occurrences)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:81](docs/TECH_DEBT_INVENTORY.md#L81)
  - [TODO] /FIXME Comments (13 files, 23 occurrences)`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:83](docs/TECH_DEBT_INVENTORY.md#L83)
  - [TODO] ]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:150](SYSTEM_DEBUG_REPORT_2026-03-24.md#L150)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:86](docs/TECH_DEBT_INVENTORY.md#L86)
  - [TODO] comments to Linear issues`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:88](docs/TECH_DEBT_INVENTORY.md#L88)
  - [TODO] ]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:190](SYSTEM_DEBUG_REPORT_2026-03-24.md#L190)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:91](docs/TECH_DEBT_INVENTORY.md#L91)
  - [TODO] comments → Linear issues`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:93](docs/TECH_DEBT_INVENTORY.md#L93)
  - [TODO] ]** [TASK_COMPLETION_REPORT_2026-03-24.md:92](TASK_COMPLETION_REPORT_2026-03-24.md#L92)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:96](docs/TECH_DEBT_INVENTORY.md#L96)
  - [TODO] → Linear Issues Migration Plan ✅`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:98](docs/TECH_DEBT_INVENTORY.md#L98)
  - [TODO] ]** [TASK_COMPLETION_REPORT_2026-03-24.md:116](TASK_COMPLETION_REPORT_2026-03-24.md#L116)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:101](docs/TECH_DEBT_INVENTORY.md#L101)
  - [TODO] s into Linear issues`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:105](docs/TECH_DEBT_INVENTORY.md#L105)
  - [TODO] ]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:23](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L23)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:108](docs/TECH_DEBT_INVENTORY.md#L108)
  - [TODO] 로 등록. 차기 스프린트에서 진행.`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:110](docs/TECH_DEBT_INVENTORY.md#L110)
  - [TODO] ]** [.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md:93](.agent/qa-reports/2026-03-21-getdaytrends-v18-improvements.md#L93)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:113](docs/TECH_DEBT_INVENTORY.md#L113)
  - [TODO] 주석 명시 |`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:115](docs/TECH_DEBT_INVENTORY.md#L115)
  - [TODO] ]** [.agent/session-history/2026-03-07.md:48](.agent/session-history/2026-03-07.md#L48)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:118](docs/TECH_DEBT_INVENTORY.md#L118)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:120](docs/TECH_DEBT_INVENTORY.md#L120)
  - [TODO] ]** [.agent/session-history/2026-03-08.md:36](.agent/session-history/2026-03-08.md#L36)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:123](docs/TECH_DEBT_INVENTORY.md#L123)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:125](docs/TECH_DEBT_INVENTORY.md#L125)
  - [TODO] ]** [.agent/session-history/2026-03-08.md:99](.agent/session-history/2026-03-08.md#L99)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:128](docs/TECH_DEBT_INVENTORY.md#L128)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:130](docs/TECH_DEBT_INVENTORY.md#L130)
  - [TODO] ]** [.agent/session-history/2026-03-08.md:135](.agent/session-history/2026-03-08.md#L135)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:133](docs/TECH_DEBT_INVENTORY.md#L133)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:135](docs/TECH_DEBT_INVENTORY.md#L135)
  - [TODO] ]** [.agent/session-history/2026-03-08.md:161](.agent/session-history/2026-03-08.md#L161)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:138](docs/TECH_DEBT_INVENTORY.md#L138)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:140](docs/TECH_DEBT_INVENTORY.md#L140)
  - [TODO] ]** [.agent/session-history/2026-03-08.md:184](.agent/session-history/2026-03-08.md#L184)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:143](docs/TECH_DEBT_INVENTORY.md#L143)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:145](docs/TECH_DEBT_INVENTORY.md#L145)
  - [TODO] ]** [.agent/session-history/2026-03-08.md:235](.agent/session-history/2026-03-08.md#L235)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:148](docs/TECH_DEBT_INVENTORY.md#L148)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:150](docs/TECH_DEBT_INVENTORY.md#L150)
  - [TODO] ]** [.agent/session-history/2026-03-08.md:275](.agent/session-history/2026-03-08.md#L275)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:153](docs/TECH_DEBT_INVENTORY.md#L153)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:155](docs/TECH_DEBT_INVENTORY.md#L155)
  - [TODO] ]** [.agent/session-history/2026-03-08.md:313](.agent/session-history/2026-03-08.md#L313)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:158](docs/TECH_DEBT_INVENTORY.md#L158)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:160](docs/TECH_DEBT_INVENTORY.md#L160)
  - [TODO] ]** [.agent/session-history/2026-03-21.md:36](.agent/session-history/2026-03-21.md#L36)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:163](docs/TECH_DEBT_INVENTORY.md#L163)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:165](docs/TECH_DEBT_INVENTORY.md#L165)
  - [TODO] ]** [.agent/session-history/2026-03-21.md:104](.agent/session-history/2026-03-21.md#L104)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:168](docs/TECH_DEBT_INVENTORY.md#L168)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:170](docs/TECH_DEBT_INVENTORY.md#L170)
  - [TODO] ]** [.agent/session-history/2026-03-24.md:44](.agent/session-history/2026-03-24.md#L44)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:173](docs/TECH_DEBT_INVENTORY.md#L173)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:175](docs/TECH_DEBT_INVENTORY.md#L175)
  - [TODO] ]** [.agent/workflows/qa-qc.md:110](.agent/workflows/qa-qc.md#L110)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:178](docs/TECH_DEBT_INVENTORY.md#L178)
  - [TODO] 로 등록하고 넘어감`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:180](docs/TECH_DEBT_INVENTORY.md#L180)
  - [TODO] ]** [.agent/workflows/session-workflow.md:50](.agent/workflows/session-workflow.md#L50)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:183](docs/TECH_DEBT_INVENTORY.md#L183)
  - [TODO] ``

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:185](docs/TECH_DEBT_INVENTORY.md#L185)
  - [TODO] ]** [.agent/workflows/session-workflow.md:87](.agent/workflows/session-workflow.md#L87)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:188](docs/TECH_DEBT_INVENTORY.md#L188)
  - [TODO] **: [항목 나열]`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:190](docs/TECH_DEBT_INVENTORY.md#L190)
  - [TODO] ]** [.agent/workflows/session-workflow.md:148](.agent/workflows/session-workflow.md#L148)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:193](docs/TECH_DEBT_INVENTORY.md#L193)
  - [TODO] **: 구체적이고 실행 가능한 항목`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:195](docs/TECH_DEBT_INVENTORY.md#L195)
  - [TODO] ]** [.agent/workflows/session-workflow.md:186](.agent/workflows/session-workflow.md#L186)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:198](docs/TECH_DEBT_INVENTORY.md#L198)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:200](docs/TECH_DEBT_INVENTORY.md#L200)
  - [TODO] ]** [.sessions/README.md:49](.sessions/README.md#L49)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:203](docs/TECH_DEBT_INVENTORY.md#L203)
  - [TODO] **: Handoff tasks`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:205](docs/TECH_DEBT_INVENTORY.md#L205)
  - [TODO] ]** [.sessions/SESSION_LOG_2026-03-23.md:32](.sessions/SESSION_LOG_2026-03-23.md#L32)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:208](docs/TECH_DEBT_INVENTORY.md#L208)
  - [TODO] /IN_PROGRESS/DONE, priority levels, tool assignment guide`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:210](docs/TECH_DEBT_INVENTORY.md#L210)
  - [TODO] ]** [.sessions/SESSION_LOG_2026-03-23.md:160](.sessions/SESSION_LOG_2026-03-23.md#L160)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:213](docs/TECH_DEBT_INVENTORY.md#L213)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:215](docs/TECH_DEBT_INVENTORY.md#L215)
  - [XXX] ]** [AgriGuard/contracts/package-lock.json:6142](AgriGuard/contracts/package-lock.json#L6142)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:218](docs/TECH_DEBT_INVENTORY.md#L218)
  - [XXX] evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:220](docs/TECH_DEBT_INVENTORY.md#L220)
  - [XXX] ]** [AgriGuard/frontend/package-lock.json:1475](AgriGuard/frontend/package-lock.json#L1475)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:223](docs/TECH_DEBT_INVENTORY.md#L223)
  - [XXX] /8R7JOTXStz/nBbRw==",`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:225](docs/TECH_DEBT_INVENTORY.md#L225)
  - [TODO] ]** [CONTEXT.md:14](CONTEXT.md#L14)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:228](docs/TECH_DEBT_INVENTORY.md#L228)
  - [TODO] /IN_PROGRESS/DONE)`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:230](docs/TECH_DEBT_INVENTORY.md#L230)
  - [TODO] ]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:141](SYSTEM_DEBUG_REPORT_2026-03-24.md#L141)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:233](docs/TECH_DEBT_INVENTORY.md#L233)
  - [TODO] **: Test instructor upgrade for Google GenAI`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:235](docs/TECH_DEBT_INVENTORY.md#L235)
  - [TODO] ]** [TASKS.md:4](TASKS.md#L4)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:238](docs/TECH_DEBT_INVENTORY.md#L238)
  - [TODO] / IN_PROGRESS / DONE)`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:240](docs/TECH_DEBT_INVENTORY.md#L240)
  - [TODO] ]** [TASKS.md:8](TASKS.md#L8)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:243](docs/TECH_DEBT_INVENTORY.md#L243)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:245](docs/TECH_DEBT_INVENTORY.md#L245)
  - [TODO] ]** [TASKS.md:10](TASKS.md#L10)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:248](docs/TECH_DEBT_INVENTORY.md#L248)
  - [TODO] *`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:250](docs/TECH_DEBT_INVENTORY.md#L250)
  - [TODO] ]** [TASK_COMPLETION_REPORT_2026-03-24.md:96](TASK_COMPLETION_REPORT_2026-03-24.md#L96)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:253](docs/TECH_DEBT_INVENTORY.md#L253)
  - [TODO] Comment Audit Results**:`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:255](docs/TECH_DEBT_INVENTORY.md#L255)
  - [TODO] ]** [TASK_COMPLETION_REPORT_2026-03-24.md:98](TASK_COMPLETION_REPORT_2026-03-24.md#L98)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:258](docs/TECH_DEBT_INVENTORY.md#L258)
  - [TODO] comments found: 4 across 3 Python files`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:260](docs/TECH_DEBT_INVENTORY.md#L260)
  - [TODO] ]** [TASK_COMPLETION_REPORT_2026-03-24.md:103](TASK_COMPLETION_REPORT_2026-03-24.md#L103)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:263](docs/TECH_DEBT_INVENTORY.md#L263)
  - [TODO] Integrate with crawler.py and ntis_crawler.py`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:265](docs/TECH_DEBT_INVENTORY.md#L265)
  - [TODO] ]** [TASK_COMPLETION_REPORT_2026-03-24.md:106](TASK_COMPLETION_REPORT_2026-03-24.md#L106)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:268](docs/TECH_DEBT_INVENTORY.md#L268)
  - [TODO] Integrate with vector_store.py and vc_crawler.py`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:270](docs/TECH_DEBT_INVENTORY.md#L270)
  - [TODO] ]** [TASK_COMPLETION_REPORT_2026-03-24.md:109](TASK_COMPLETION_REPORT_2026-03-24.md#L109)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:273](docs/TECH_DEBT_INVENTORY.md#L273)
  - [TODO] 실제 Canva API 통신 로직 병합`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:275](docs/TECH_DEBT_INVENTORY.md#L275)
  - [TODO] ]** [TASK_COMPLETION_REPORT_2026-03-24.md:112](TASK_COMPLETION_REPORT_2026-03-24.md#L112)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:278](docs/TECH_DEBT_INVENTORY.md#L278)
  - [TODO] s (meta comment, not actionable)`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:280](docs/TECH_DEBT_INVENTORY.md#L280)
  - [TODO] ]** [TASK_COMPLETION_REPORT_2026-03-24.md:175](TASK_COMPLETION_REPORT_2026-03-24.md#L175)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:283](docs/TECH_DEBT_INVENTORY.md#L283)
  - [TODO] → Linear migration (4 items identified)`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:285](docs/TECH_DEBT_INVENTORY.md#L285)
  - [TODO] ]** [TASK_COMPLETION_REPORT_2026-03-24.md:185](TASK_COMPLETION_REPORT_2026-03-24.md#L185)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:288](docs/TECH_DEBT_INVENTORY.md#L288)
  - [TODO] s**: `python scripts/linear_sync.py` (requires LINEAR_API_KEY)`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:290](docs/TECH_DEBT_INVENTORY.md#L290)
  - [TODO] ]** [TASK_COMPLETION_REPORT_2026-03-24.md:190](TASK_COMPLETION_REPORT_2026-03-24.md#L190)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:293](docs/TECH_DEBT_INVENTORY.md#L293)
  - [TODO] migration`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:295](docs/TECH_DEBT_INVENTORY.md#L295)
  - [TODO] ]** [TASK_COMPLETION_REPORT_2026-03-24.md:205](TASK_COMPLETION_REPORT_2026-03-24.md#L205)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:298](docs/TECH_DEBT_INVENTORY.md#L298)
  - [TODO] comments to migrate`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:300](docs/TECH_DEBT_INVENTORY.md#L300)
  - [TODO] ]** [desci-platform/IMPROVEMENT_PLAN.md:39](desci-platform/IMPROVEMENT_PLAN.md#L39)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:303](docs/TECH_DEBT_INVENTORY.md#L303)
  - [TODO] )`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:305](docs/TECH_DEBT_INVENTORY.md#L305)
  - [TODO] ]** [desci-platform/biolinker/services/agent_graph.py:70](desci-platform/biolinker/services/agent_graph.py#L70)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:308](docs/TECH_DEBT_INVENTORY.md#L308)
  - [TODO] Integrate with crawler.py and ntis_crawler.py`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:310](docs/TECH_DEBT_INVENTORY.md#L310)
  - [TODO] ]** [desci-platform/biolinker/services/agent_graph.py:125](desci-platform/biolinker/services/agent_graph.py#L125)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:313](docs/TECH_DEBT_INVENTORY.md#L313)
  - [TODO] Integrate with vector_store.py and vc_crawler.py`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:315](docs/TECH_DEBT_INVENTORY.md#L315)
  - [XXX] ]** [desci-platform/contracts/package-lock.json:5865](desci-platform/contracts/package-lock.json#L5865)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:318](docs/TECH_DEBT_INVENTORY.md#L318)
  - [XXX] evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:320](docs/TECH_DEBT_INVENTORY.md#L320)
  - [TODO] ]** [docs/WORKSPACE-STATUS-2026-03-22.md:98](docs/WORKSPACE-STATUS-2026-03-22.md#L98)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:323](docs/TECH_DEBT_INVENTORY.md#L323)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:325](docs/TECH_DEBT_INVENTORY.md#L325)
  - [TODO] ]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:185](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L185)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:328](docs/TECH_DEBT_INVENTORY.md#L328)
  - [TODO] | Config exists, not integrated |`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:330](docs/TECH_DEBT_INVENTORY.md#L330)
  - [TODO] ]** [getdaytrends/V9.0_IMPLEMENTATION_STATUS.md:186](getdaytrends/V9.0_IMPLEMENTATION_STATUS.md#L186)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:333](docs/TECH_DEBT_INVENTORY.md#L333)
  - [TODO] | Only Telegram/Discord |`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:335](docs/TECH_DEBT_INVENTORY.md#L335)
  - [TODO] ]** [getdaytrends/canva.py:26](getdaytrends/canva.py#L26)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:338](docs/TECH_DEBT_INVENTORY.md#L338)
  - [TODO] 실제 Canva API 통신 로직 병합`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:340](docs/TECH_DEBT_INVENTORY.md#L340)
  - [TODO] ]** [getdaytrends/generation/audit.py:15](getdaytrends/generation/audit.py#L15)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:343](docs/TECH_DEBT_INVENTORY.md#L343)
  - [TODO] generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:345](docs/TECH_DEBT_INVENTORY.md#L345)
  - [TODO] ]** [getdaytrends/generation/prompts.py:13](getdaytrends/generation/prompts.py#L13)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:348](docs/TECH_DEBT_INVENTORY.md#L348)
  - [TODO] generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:350](docs/TECH_DEBT_INVENTORY.md#L350)
  - [TODO] ]** [scripts/workspace_summary.py:7](scripts/workspace_summary.py#L7)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:353](docs/TECH_DEBT_INVENTORY.md#L353)
  - [TODO] 추출`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:355](docs/TECH_DEBT_INVENTORY.md#L355)
  - [TODO] ]** [scripts/workspace_summary.py:64](scripts/workspace_summary.py#L64)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:358](docs/TECH_DEBT_INVENTORY.md#L358)
  - [TODO] 추출."""`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:360](docs/TECH_DEBT_INVENTORY.md#L360)
  - [TODO] ]** [scripts/workspace_summary.py:80](scripts/workspace_summary.py#L80)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:363](docs/TECH_DEBT_INVENTORY.md#L363)
  - [TODO] 추출`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:365](docs/TECH_DEBT_INVENTORY.md#L365)
  - [TODO] ]** [scripts/workspace_summary.py:83](scripts/workspace_summary.py#L83)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:368](docs/TECH_DEBT_INVENTORY.md#L368)
  - [TODO] " in line or "다음 세션" in line:`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:370](docs/TECH_DEBT_INVENTORY.md#L370)
  - [TODO] ]** [scripts/workspace_summary.py:194](scripts/workspace_summary.py#L194)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:373](docs/TECH_DEBT_INVENTORY.md#L373)
  - [TODO] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:375](docs/TECH_DEBT_INVENTORY.md#L375)
  - [TODO] ]** [scripts/workspace_summary.py:198](scripts/workspace_summary.py#L198)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:378](docs/TECH_DEBT_INVENTORY.md#L378)
  - [TODO] ({len(todos['todos'])}개):")`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:380](docs/TECH_DEBT_INVENTORY.md#L380)
  - [TODO] ]** [scripts/workspace_summary.py:225](scripts/workspace_summary.py#L225)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:383](docs/TECH_DEBT_INVENTORY.md#L383)
  - [TODO] 이어서 작업")`

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:550](docs/TECH_DEBT_INVENTORY.md#L550)
  - [FIXME] Comments (13 files, 23 occurrences)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:592](docs/TECH_DEBT_INVENTORY.md#L592)
  - [TODO] ] comments to Linear issues

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:595](docs/TECH_DEBT_INVENTORY.md#L595)
  - [TODO] ] /FIXME Comments (13 files, 23 occurrences)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:598](docs/TECH_DEBT_INVENTORY.md#L598)
  - [TODO] ] comments to Linear issues

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:601](docs/TECH_DEBT_INVENTORY.md#L601)
  - [TODO] ] comments → Linear issues

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:604](docs/TECH_DEBT_INVENTORY.md#L604)
  - [TODO] ] → Linear Issues Migration Plan ✅

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:607](docs/TECH_DEBT_INVENTORY.md#L607)
  - [TODO] ] s into Linear issues

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:610](docs/TECH_DEBT_INVENTORY.md#L610)
  - [TODO] ] /IN_PROGRESS/DONE)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:613](docs/TECH_DEBT_INVENTORY.md#L613)
  - [TODO] ] **: Test instructor upgrade for Google GenAI

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:616](docs/TECH_DEBT_INVENTORY.md#L616)
  - [TODO] ] / IN_PROGRESS / DONE)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:619](docs/TECH_DEBT_INVENTORY.md#L619)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:622](docs/TECH_DEBT_INVENTORY.md#L622)
  - [TODO] ] *

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:625](docs/TECH_DEBT_INVENTORY.md#L625)
  - [TODO] ] Comment Audit Results**

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:628](docs/TECH_DEBT_INVENTORY.md#L628)
  - [TODO] ] comments found: 4 across 3 Python files

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:631](docs/TECH_DEBT_INVENTORY.md#L631)
  - [TODO] ] Integrate with crawler.py and ntis_crawler.py

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:634](docs/TECH_DEBT_INVENTORY.md#L634)
  - [TODO] ] Integrate with vector_store.py and vc_crawler.py

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:637](docs/TECH_DEBT_INVENTORY.md#L637)
  - [TODO] ] 실제 Canva API 통신 로직 병합

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:640](docs/TECH_DEBT_INVENTORY.md#L640)
  - [TODO] ] s (meta comment, not actionable)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:643](docs/TECH_DEBT_INVENTORY.md#L643)
  - [TODO] ] → Linear migration (4 items identified)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:646](docs/TECH_DEBT_INVENTORY.md#L646)
  - [TODO] ] s**: `python scripts/linear_sync.py` (requires LINEAR_API_KEY)

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:649](docs/TECH_DEBT_INVENTORY.md#L649)
  - [TODO] ] migration

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:652](docs/TECH_DEBT_INVENTORY.md#L652)
  - [TODO] ] comments to migrate

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:659](docs/TECH_DEBT_INVENTORY.md#L659)
  - [TODO] ] 로 등록. 차기 스프린트에서 진행.

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:662](docs/TECH_DEBT_INVENTORY.md#L662)
  - [TODO] ] 주석 명시 |

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:665](docs/TECH_DEBT_INVENTORY.md#L665)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:668](docs/TECH_DEBT_INVENTORY.md#L668)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:671](docs/TECH_DEBT_INVENTORY.md#L671)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:674](docs/TECH_DEBT_INVENTORY.md#L674)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:677](docs/TECH_DEBT_INVENTORY.md#L677)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:680](docs/TECH_DEBT_INVENTORY.md#L680)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:683](docs/TECH_DEBT_INVENTORY.md#L683)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:686](docs/TECH_DEBT_INVENTORY.md#L686)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:689](docs/TECH_DEBT_INVENTORY.md#L689)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:692](docs/TECH_DEBT_INVENTORY.md#L692)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:695](docs/TECH_DEBT_INVENTORY.md#L695)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:698](docs/TECH_DEBT_INVENTORY.md#L698)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:701](docs/TECH_DEBT_INVENTORY.md#L701)
  - [TODO] ] 로 등록하고 넘어감

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:704](docs/TECH_DEBT_INVENTORY.md#L704)
  - [TODO] ] `

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:707](docs/TECH_DEBT_INVENTORY.md#L707)
  - [TODO] ] **: [항목 나열]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:710](docs/TECH_DEBT_INVENTORY.md#L710)
  - [TODO] ] **: 구체적이고 실행 가능한 항목

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:713](docs/TECH_DEBT_INVENTORY.md#L713)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:720](docs/TECH_DEBT_INVENTORY.md#L720)
  - [TODO] ] 추출

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:723](docs/TECH_DEBT_INVENTORY.md#L723)
  - [TODO] ] 추출."""

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:726](docs/TECH_DEBT_INVENTORY.md#L726)
  - [TODO] ] 추출

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:729](docs/TECH_DEBT_INVENTORY.md#L729)
  - [TODO] ] " in line or "다음 세션" in line

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:732](docs/TECH_DEBT_INVENTORY.md#L732)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:735](docs/TECH_DEBT_INVENTORY.md#L735)
  - [TODO] ] ({len(todos['todos'])}개):")

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:738](docs/TECH_DEBT_INVENTORY.md#L738)
  - [TODO] ] 이어서 작업")

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:745](docs/TECH_DEBT_INVENTORY.md#L745)
  - [TODO] ] | Config exists, not integrated |

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:748](docs/TECH_DEBT_INVENTORY.md#L748)
  - [TODO] ] | Only Telegram/Discord |

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:751](docs/TECH_DEBT_INVENTORY.md#L751)
  - [TODO] ] 실제 Canva API 통신 로직 병합

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:754](docs/TECH_DEBT_INVENTORY.md#L754)
  - [TODO] ] generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:757](docs/TECH_DEBT_INVENTORY.md#L757)
  - [TODO] ] generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:764](docs/TECH_DEBT_INVENTORY.md#L764)
  - [TODO] ] )

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:767](docs/TECH_DEBT_INVENTORY.md#L767)
  - [TODO] ] Integrate with crawler.py and ntis_crawler.py

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:770](docs/TECH_DEBT_INVENTORY.md#L770)
  - [TODO] ] Integrate with vector_store.py and vc_crawler.py

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:773](docs/TECH_DEBT_INVENTORY.md#L773)
  - [XXX] ] evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:780](docs/TECH_DEBT_INVENTORY.md#L780)
  - [TODO] ] **: Handoff tasks

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:783](docs/TECH_DEBT_INVENTORY.md#L783)
  - [TODO] ] /IN_PROGRESS/DONE, priority levels, tool assignment guide

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:786](docs/TECH_DEBT_INVENTORY.md#L786)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:793](docs/TECH_DEBT_INVENTORY.md#L793)
  - [XXX] ] evb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:796](docs/TECH_DEBT_INVENTORY.md#L796)
  - [XXX] ] /8R7JOTXStz/nBbRw==",

- **[P3]** [docs/TECH_DEBT_INVENTORY.md:803](docs/TECH_DEBT_INVENTORY.md#L803)
  - [TODO] ]

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:11](docs/TECH_DEBT_P1_REVIEW.md#L11)
  - [TODO] **(Linear 이슈 변환 관련)로, 실제 코드 버그가 아닙니다.

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:13](docs/TECH_DEBT_P1_REVIEW.md#L13)
  - [TODO] 는 3개이며, 모두 **리팩토링/마이그레이션 계획**으로 긴급하지 않습니다.

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:25](docs/TECH_DEBT_P1_REVIEW.md#L25)
  - [TODO] 언급**입니다

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:29](docs/TECH_DEBT_P1_REVIEW.md#L29)
  - [TODO] comments to Linear issues" |

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:30](docs/TECH_DEBT_P1_REVIEW.md#L30)
  - [TODO] /FIXME 통계 및 Linear 마이그레이션 계획 |

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:36](docs/TECH_DEBT_P1_REVIEW.md#L36)
  - [TODO] ", "FIXME", "bug" 키워드를 동시에 포함한 문맥을 버그로 오분류

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:56](docs/TECH_DEBT_P1_REVIEW.md#L56)
  - [TODO] (3개)

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:68](docs/TECH_DEBT_P1_REVIEW.md#L68)
  - [TODO] 실제 Canva API 통신 로직 병합

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:95](docs/TECH_DEBT_P1_REVIEW.md#L95)
  - [TODO] generator.py L1745-L2044의 QA 코드를 이 파일로 마이그레이션 예정.

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:130](docs/TECH_DEBT_P1_REVIEW.md#L130)
  - [TODO] generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:163](docs/TECH_DEBT_P1_REVIEW.md#L163)
  - [TODO] 추가 발견 (수동 검색)

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:169](docs/TECH_DEBT_P1_REVIEW.md#L169)
  - [TODO] 확인 필요** (파일 크기 때문에 세부 내용 미확인)

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:182](docs/TECH_DEBT_P1_REVIEW.md#L182)
  - [TODO] " + "bug" 키워드 동시 포함 → P1 (bug)

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:208](docs/TECH_DEBT_P1_REVIEW.md#L208)
  - [FIXME] ", "BUG", "ERROR", "CRASH"])

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:212](docs/TECH_DEBT_P1_REVIEW.md#L212)
  - [HACK] "

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:275](docs/TECH_DEBT_P1_REVIEW.md#L275)
  - [TODO] )

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:292](docs/TECH_DEBT_P1_REVIEW.md#L292)
  - [TODO] 는 리팩토링/마이그레이션 계획일 뿐

- **[P3]** [docs/TECH_DEBT_P1_REVIEW.md:298](docs/TECH_DEBT_P1_REVIEW.md#L298)
  - [TODO] 처리 (Phase 2, 4)

- **[P3]** [docs/WORKSPACE-STATUS-2026-03-22.md:98](docs/WORKSPACE-STATUS-2026-03-22.md#L98)
  - [TODO] 

### root - 26개 항목

**우선순위 분포**: P3: 26

- **[P3]** [CONTEXT.md:14](CONTEXT.md#L14)
  - [TODO] /IN_PROGRESS/DONE)

- **[P3]** [QC_REPORT_2026-03-24_SYSTEM_DEBUG.md:388](QC_REPORT_2026-03-24_SYSTEM_DEBUG.md#L388)
  - [TODO] comments to Linear issues

- **[P3]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:82](SYSTEM_DEBUG_REPORT_2026-03-24.md#L82)
  - [TODO] /FIXME Comments (13 files, 23 occurrences)

- **[P3]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:141](SYSTEM_DEBUG_REPORT_2026-03-24.md#L141)
  - [TODO] **: Test instructor upgrade for Google GenAI

- **[P3]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:150](SYSTEM_DEBUG_REPORT_2026-03-24.md#L150)
  - [TODO] comments to Linear issues

- **[P3]** [SYSTEM_DEBUG_REPORT_2026-03-24.md:190](SYSTEM_DEBUG_REPORT_2026-03-24.md#L190)
  - [TODO] comments → Linear issues

- **[P3]** [SYSTEM_ENHANCEMENT_PLAN.md:109](SYSTEM_ENHANCEMENT_PLAN.md#L109)
  - [TODO] /FIXME (145개 에러 핸들링 검토 필요)

- **[P3]** [SYSTEM_ENHANCEMENT_PLAN.md:321](SYSTEM_ENHANCEMENT_PLAN.md#L321)
  - [TODO] /FIXME/HACK/XXX 존재

- **[P3]** [SYSTEM_ENHANCEMENT_PLAN.md:341](SYSTEM_ENHANCEMENT_PLAN.md#L341)
  - [TODO] 주석 → GitHub Issue 자동 생성 (label: tech-debt)

- **[P3]** [SYSTEM_ENHANCEMENT_PLAN.md:354](SYSTEM_ENHANCEMENT_PLAN.md#L354)
  - [TODO] /FIXME 50% 감소 (53 → 26개)

- **[P3]** [SYSTEM_ENHANCEMENT_PLAN.md:1149](SYSTEM_ENHANCEMENT_PLAN.md#L1149)
  - [TODO] ) | 53 files | 26 files | grep -r "TODO" |

- **[P3]** [TASKS.md:4](TASKS.md#L4)
  - [TODO] / IN_PROGRESS / DONE)

- **[P3]** [TASKS.md:8](TASKS.md#L8)
  - [TODO] 

- **[P3]** [TASKS.md:10](TASKS.md#L10)
  - [TODO] *

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:92](TASK_COMPLETION_REPORT_2026-03-24.md#L92)
  - [TODO] → Linear Issues Migration Plan ✅

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

- **[P3]** [TASK_COMPLETION_REPORT_2026-03-24.md:116](TASK_COMPLETION_REPORT_2026-03-24.md#L116)
  - [TODO] s into Linear issues

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

### scripts - 14개 항목

**우선순위 분포**: P1: 7, P3: 7

- **[P1]** [scripts/generate_tech_debt_inventory.py:5](scripts/generate_tech_debt_inventory.py#L5)
  - [TODO] , FIXME, HACK, XXX 주석을 자동으로 수집하여

- **[P1]** [scripts/generate_tech_debt_inventory.py:25](scripts/generate_tech_debt_inventory.py#L25)
  - [TODO] , FIXME, HACK, XXX

- **[P1]** [scripts/generate_tech_debt_inventory.py:64](scripts/generate_tech_debt_inventory.py#L64)
  - [TODO] /FIXME/HACK/XXX 검색

- **[P1]** [scripts/generate_tech_debt_inventory.py:65](scripts/generate_tech_debt_inventory.py#L65)
  - [TODO] ', 'FIXME', 'HACK', 'XXX']

- **[P1]** [scripts/generate_tech_debt_inventory.py:101](scripts/generate_tech_debt_inventory.py#L101)
  - [TODO] fix this

- **[P1]** [scripts/generate_tech_debt_inventory.py:110](scripts/generate_tech_debt_inventory.py#L110)
  - [TODO] ', 'FIXME', 'HACK', 'XXX']

- **[P1]** [scripts/generate_tech_debt_inventory.py:211](scripts/generate_tech_debt_inventory.py#L211)
  - [TODO] , FIXME, HACK, XXX)을

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

---

## 다음 단계

1. **P0 항목 즉시 처리**: 보안 및 긴급 이슈부터 해결
2. **GitHub Issues 생성**: 각 항목을 이슈로 등록하여 추적
3. **주간 부채 상환**: 매주 금요일 "Tech Debt Friday" 운영
4. **월간 리뷰**: 진행 상황 및 남은 부채 리뷰

---

**자동 생성 스크립트**: `scripts/generate_tech_debt_inventory.py`
**마지막 업데이트**: 2026-03-26 08:08:04
