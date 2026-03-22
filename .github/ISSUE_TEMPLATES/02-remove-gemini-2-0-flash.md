# Remove Deprecated Gemini 2.0 Flash Model

**Labels**: `technical-debt`, `critical`, `backend`
**Priority**: 🚨 **Critical** - 2026-06-01 종료 예정

---

## Description

Gemini 2.0 Flash 모델이 2026-06-01에 종료 예정입니다. 레거시 폴백 체인에서 제거 필요.

---

## Current Usage

**30일 통계** (from cost report):
- 호출 횟수: 2,502회
- 비용: $0.00 (Free tier)
- 위치:
  - `shared/llm/config.py` (line 50, 58)
  - `agents/trend_analyzer.py` (line 65)

---

## Tasks

- [ ] `shared/llm/config.py`에서 `gemini-2.0-flash` 제거
- [ ] `agents/trend_analyzer.py` 기본 모델을 `gemini-2.5-flash-lite`로 변경
- [ ] 테스트 파일 업데이트 (`tests/test_shared_llm.py`, `tests/test_llm_enhancements.py`)
- [ ] 변경 사항 테스트 (단위 테스트 + 통합 테스트)
- [ ] 문서 업데이트 (SYSTEM_AUDIT_ACTION_PLAN.md)

---

## Migration Path

### Before
```python
TIER_CHAINS = {
    TaskTier.MEDIUM: [
        ("gemini", "gemini-2.5-flash-lite"),
        ("gemini", "gemini-2.0-flash"),  # ❌ Remove
        ("openai", "gpt-4o-mini"),
    ]
}
```

### After
```python
TIER_CHAINS = {
    TaskTier.MEDIUM: [
        ("gemini", "gemini-2.5-flash-lite"),
        ("gemini", "gemini-2.5-flash"),  # ✅ Use 2.5 instead
        ("openai", "gpt-4o-mini"),
    ]
}
```

---

## Acceptance Criteria

- ✅ `gemini-2.0-flash` 문자열이 코드베이스에서 테스트 파일 외에는 존재하지 않음
- ✅ 모든 테스트 통과 (pytest)
- ✅ 비용 리포트에서 2.0 Flash 호출이 0으로 확인됨

---

## Testing Commands

```bash
# 1. 코드베이스에서 2.0 Flash 사용 확인
rg "gemini-2\.0-flash" --type py --glob '!tests/'

# 2. 테스트 실행
pytest shared/tests/ DailyNews/tests/ -v

# 3. 비용 리포트 생성
python scripts/cost_intelligence.py --days 7
```

---

**Estimated Time**: 1-2시간
**Deadline**: 2026-05-01 (종료 1개월 전)
