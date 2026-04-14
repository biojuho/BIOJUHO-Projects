---
description: "세션 시작/종료 워크플로. 세션 시작 시 컨텍스트 복원, 세션 종료 시 히스토리 저장"
---

// turbo-all

# 세션 워크플로 (v4.0 - Sprint-Aware)

> **v4.0 변경사항**: GStack 스프린트 구조 (Think→Plan→Build→Review→Test→Ship→Reflect) 통합

이 워크플로는 두 가지 모드로 동작한다. 사용자가 모드를 명시하지 않으면 **자동 감지**한다:
- 대화 초반이면 → **세션 시작** 모드
- 대화 중반 이후 or "마무리/종료/끝" 키워드 → **세션 종료** 모드
- `--quick` 키워드 → **빠른 복원** 모드 (세션 시작의 경량 버전)

---

## 스프린트 페이즈 가이드 ← v4.0 신규

> **영감**: [garrytan/gstack](https://github.com/garrytan/gstack)의 Sprint 구조

각 세션은 아래 7단계 스프린트의 일부이다. 현재 작업이 어느 페이즈인지 인식하고 표시한다:

| 페이즈 | 설명 | 연결 워크플로우 |
|--------|------|---------------|
| 🧠 Think | 아이디어 탐색, 문제 정의 | `/office-hours` |
| 📋 Plan | 아키텍처 설계, 기술 결정 | (구현 계획 수립) |
| 🔨 Build | 코드 작성, 기능 구현 | `/qa-qc` STEP 1 |
| 🔍 Review | 코드 리뷰, 품질 검사 | `/qa-qc` STEP 2 |
| 🧪 Test | 테스트 실행, 버그 수정 | `/qa-qc` STEP 3-4, `/debug` |
| 🚀 Ship | 배포, 커밋, 릴리즈 | `/deploy` |
| 🪞 Reflect | 회고, 교훈 정리 | (세션 종료 시 자동) |

**핵심 원칙**: 각 스킬이 다음 스킬에 컨텍스트를 전달한다. `/office-hours` 설계 문서 → `/qa-qc` 검토 기준 → `/deploy` 배포 판단.

---

## 세션 시작 모드 (Session Start)

### Step 1: 최근 세션 히스토리 복원

가장 최근 세션 히스토리 파일을 찾아 읽는다:

```bash
dir "d:\AI 프로젝트\.agent\session-history" /o:-d /b
```

최신 파일의 **마지막 세션** 섹션에서 다음을 추출한다:
- `미완성/버그 이슈`
- `다음 TODO`
- `검증 결과`

### Step 1.5: Next Actions 큐 확인 ← VSC3

`next-actions.md` 파일이 존재하면 읽어서 현재 작업 큐를 파악한다:
- `[safe_auto]` 항목이 있으면 → "해줘" 입력 시 바로 실행 가능한 작업으로 표시
- `[needs_approval]`만 남아 있으면 → 사용자에게 선택지 안내
- 파일이 없으면 → 스킵 (session-history의 "다음 TODO"로 대체)

### Step 2: Knowledge Base 컨텍스트 복원

대화에 제공된 KI 요약 목록을 확인하고, 현재 사용자의 활성 문서와 관련된 KI 아티팩트를 읽는다.
특히 다음 KI를 우선 확인한다:

- `AI Automation, Autonomous Intelligence & Knowledge Synthesis`
- `Cross-Project Orchestration Patterns`
- 사용자가 열고 있는 프로젝트와 관련된 KI

> `--quick` 모드에서는 이 단계를 **스킵**하고 Step 1의 히스토리만 사용한다.

### Step 3: Git 상태 + Workspace Summary

```bash
git -C "d:\AI 프로젝트" status --short
```

workspace_summary 스크립트가 있으면 실행한다:
```bash
python "d:\AI 프로젝트\scripts\workspace_summary.py"
```

### Step 4: 프로젝트 통계 및 상태 리포트 생성

DORA Metrics 스크립트를 통해 현재 생산성을 확인한다:
```bash
python "d:\AI 프로젝트\scripts\dora_metrics.py" --days 7
```

수집한 정보를 바탕으로 사용자에게 **간결한 상태 리포트**를 제공한다:

```markdown
## 📋 현재 상태 요약
- **마지막 작업**: [히스토리에서 파악한 내용]
- **미완료 TODO**: [항목 나열]
- **Git 변경사항**: [uncommitted 변경 요약]
- **프로젝트 건강도**: [healthcheck 결과 요약]
- **현재 스프린트 페이즈**: [🧠Think / 📋Plan / 🔨Build / 🔍Review / 🧪Test / 🚀Ship / 🪞Reflect]
- **오늘 추천 작업**: [우선순위 기반 제안 + 다음 페이즈 안내]
```

### Step 5: Rules & QA/QC 활성화

```bash
type "d:\AI 프로젝트\.agent\rules\project-rules.md"
```

규칙 파일이 정상 로드되었는지 확인하고, 이번 세션에서 코드 변경 시 **QA/QC 4단계 워크플로**가 자동 적용됨을 상기한다:
1. **개발** → 2. **QA 검토 + AUTO-FIX** → 3. **수정 + 회귀 테스트** → 4. **QC 보고서**

상세 절차는 `d:\AI 프로젝트\.agent\workflows\qa-qc.md` 참조.

---

## 빠른 복원 모드 (Quick Restore)

`--quick` 또는 "빠르게" 키워드 시 실행. Step 1 + Step 3만 실행하고 즉시 작업 시작.

---

## 세션 종료 모드 (Session End)

### Step 1: 변경 파일 목록 수집

```bash
git -C "d:\AI 프로젝트" diff --name-status HEAD
```

```bash
git -C "d:\AI 프로젝트" log --oneline -5
```

### Step 2: QA/QC 미실행 코드 확인

이번 세션에서 변경된 코드 파일 중 QA/QC를 거치지 않은 파일이 있는지 확인한다.

**QA/QC 필요 여부 판단 기준:**
- `.py`/`.js`/`.ts`/`.jsx`/`.tsx` 로직 변경 → ✅ 필요
- `.md`/`.yml`/`.json`/`.css` 변경 → ⏭️ 불필요
- 테스트 코드만 변경 → ⏭️ 불필요

미검토 코드가 있으면 사용자에게 알리고 QA/QC 실행 여부를 확인한다.

### Step 3: 변경 내용 자동 정리

이번 세션에서 변경/생성/삭제된 파일의 목록을 수집하고, 각 변경의 이유를 정리한다.

### Step 4: 세션 히스토리 저장

다음 내용을 포함하는 세션 리포트를 작성하여 워크스페이스에 저장한다:

- **날짜**: 현재 날짜
- **변경 파일 목록**: 파일명 + 변경 유형(생성/수정/삭제) + 변경 이유
- **진행 상황 요약**: 이번 세션에서 달성한 것
- **미완성/버그 이슈**: 알려진 문제점
- **다음 TODO**: 구체적이고 실행 가능한 항목

저장 경로: `d:\AI 프로젝트\.agent\session-history\YYYY-MM-DD.md`

> ⚠️ **누적 저장**: 같은 날짜의 파일이 이미 존재하면 **덮어쓰지 않고** 하단에 `---` 구분선 후 새 세션 섹션을 추가한다. 세션 번호는 기존 파일의 마지막 세션 번호 + 1로 자동 할당한다.

### Step 4.5: Next Actions 큐 갱신 제안 ← VSC3

세션 히스토리의 "다음 TODO"를 `next-actions.md` 형식으로 분류하여 갱신을 제안한다:
- 자동 진행 가능한 항목 → `[safe_auto]`
- 패키지 설치·DB 변경·인증 변경 등 → `[needs_approval]`
- 완료된 항목은 제거 제안
- 사용자 승인 후에만 실제 파일 수정

### Step 5: Git 커밋 제안 (선택)

uncommitted 변경사항이 있으면 커밋 메시지를 제안한다:

```
[Project] 변경 내용 요약
```

사용자에게 커밋 여부를 확인한 후에만 실행한다.

### Step 6: 스프린트 회고 (Reflect) + 최종 요약 ← v4.0 강화

> **영감**: GStack 스프린트의 Reflect 단계 — 단순 기록이 아닌 교훈 추출

이번 세션의 DORA 지표 요약과 함께 **스프린트 회고**를 제공한다.

```markdown
## 🪞 세션 회고 (Reflect)

### 스프린트 진행 상태
- **시작 페이즈**: [세션 시작 시 페이즈]
- **종료 페이즈**: [세션 종료 시 페이즈]
- **다음 세션 페이즈**: [다음에 시작할 페이즈 + 이유]

### 달성 vs 미달성
- ✅ **완료**: [달성 항목]
- ⏳ **미완료**: [남은 항목 + 이유]
- 🔄 **방향 변경**: [계획과 달라진 점 + 왜]

### 핵심 교훈
- 💡 [이번 세션에서 배운 것 / 다음에 다르게 할 것]

### 다음 세션 TODO
1. [구체적 항목] — 페이즈: [Build/Review/...]
2. [구체적 항목] — 페이즈: [Build/Review/...]

### 생산성 Metrics
- 커밋: [N건]
- 변경 파일: [N개]
- 테스트: [통과/실패 현황]
- **히스토리 저장**: session-history/YYYY-MM-DD.md ✓
```
