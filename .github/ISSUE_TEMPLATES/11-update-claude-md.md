# Update CLAUDE.md with Latest Changes

**Labels**: `documentation`
**Priority**: 📝 **Documentation** - 진행 중

---

## Description

최근 변경 사항을 반영하여 CLAUDE.md를 업데이트합니다.

---

## Tasks

- [ ] Python 버전 요구사항 업데이트 (3.13.3 필수)
- [ ] Node.js 버전 요구사항 업데이트 (22.12.0+ 필수)
- [ ] Gemini 2.0 Flash 제거 반영
- [ ] PostgreSQL 마이그레이션 반영 (SQLite → PostgreSQL)
- [ ] Docker Compose 가이드 추가
- [ ] 비용 최적화 전략 추가 (Batch API)
- [ ] Gotchas 섹션 업데이트
- [ ] Pre-commit hooks 설치 가이드 링크 추가

---

## Sections to Update

### 1. 필수 설정 섹션
```markdown
## ⚠️ 필수 설정 (신규 팀원)

# Python/Node 버전 확인
python --version  # 3.13.3 필요
node --version    # 22.12.0+ 필요
```

### 2. Gotchas 섹션
```markdown
## Gotchas

- **Python 버전**: 3.13.3 필수 (langchain 호환)
- **Gemini 2.0 Flash**: 제거됨 (2026-06-01 종료)
- **AgriGuard DB**: PostgreSQL 사용 (SQLite 제거)
```

---

## Acceptance Criteria

- ✅ 모든 버전 정보가 최신화됨
- ✅ Deprecated 정보 제거됨
- ✅ 새로운 기능 추가됨 (Batch API, Docker Compose)

---

**Estimated Time**: 1-2시간
