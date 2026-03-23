# Google Generative AI Migration Plan

**Status**: 🔴 Critical - Deprecated Package EOL
**Deadline**: Before 2026-06-01 (google.generativeai EOL date)
**Created**: 2026-03-24

## Overview

The `google.generativeai` package has been deprecated and will no longer receive updates or bug fixes. We must migrate to the `google.genai` package.

**Impact**: Currently affecting `getdaytrends` project via `instructor` library dependency.

## Current State

### Affected Files
- `getdaytrends/` - Uses instructor library which depends on google.generativeai
- Warning location: `instructor/providers/gemini/client.py:5`

### Current Dependencies
```python
# getdaytrends/requirements.txt
google-genai>=1.0.0  # ✅ Already using new package!
instructor>=1.14.0    # ⚠️ Still imports old google.generativeai
```

### Warning Message
```
FutureWarning: All support for the `google.generativeai` package has ended.
It will no longer be receiving updates or bug fixes.
Please switch to the `google.genai` package as soon as possible.
```

## Root Cause

The `instructor` library (version 1.14.0) internally imports `google.generativeai` for Gemini provider support, even though we're using `google-genai` in our code.

## Migration Options

### Option 1: Update Instructor Library (Recommended)
**Pros**:
- Official support from instructor maintainers
- Clean, minimal code changes
- Future-proof

**Cons**:
- Requires instructor team to update (may already be done)
- Need to test compatibility

**Action**:
```bash
# Check for newer instructor version
pip install --upgrade instructor

# Test in getdaytrends
cd getdaytrends
python -m pytest tests/ -k "test_analyzer or test_generator"
```

### Option 2: Patch Instructor Locally
**Pros**:
- Immediate fix
- Full control

**Cons**:
- Maintenance burden
- May break on instructor updates

**Action**:
Create `getdaytrends/patches/instructor_gemini.py` with monkey patch

### Option 3: Use Alternative Structured Output Library
**Pros**:
- No dependency on instructor's Gemini support
- Potential performance improvements

**Cons**:
- Major refactoring required
- Risk of introducing bugs

**Alternatives**:
- Pydantic AI (by Pydantic team)
- LangChain structured output
- Raw google-genai with manual validation

## Recommended Approach

**Phase 1: Immediate (This Week)**
1. Check instructor GitHub releases for google.genai support
2. If available, update instructor: `pip install --upgrade instructor`
3. Run full test suite: `pytest getdaytrends/tests/`
4. Monitor logs for FutureWarning removal

**Phase 2: Fallback (If Phase 1 Fails)**
1. Open issue on instructor GitHub requesting migration
2. Implement temporary warning suppression:
   ```python
   import warnings
   warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
   ```
3. Schedule follow-up check in 2 weeks

**Phase 3: Long-term (Before 2026-06-01)**
1. If instructor hasn't migrated, switch to Pydantic AI or manual validation
2. Update all structured output calls in:
   - `getdaytrends/analyzer.py`
   - `getdaytrends/generator.py`
   - `getdaytrends/structured_output.py`

## Testing Checklist

- [ ] `test_analyzer.py` - JSON parsing with structured output
- [ ] `test_generator.py` - Tweet generation with Pydantic models
- [ ] `test_e2e.py` - Full pipeline with LLM calls
- [ ] `test_fact_checker.py` - Claim extraction structured output
- [ ] Manual test: Run `python main.py --one-shot --limit 3`
- [ ] Check logs for warnings: `grep -i "futurewarning" logs/*.log`

## Rollback Plan

If migration causes issues:

1. Pin instructor version:
   ```python
   instructor==1.14.0  # Last known working version
   ```

2. Suppress warnings temporarily:
   ```python
   # getdaytrends/main.py (top of file)
   import warnings
   warnings.filterwarnings("ignore", message=".*google.generativeai.*", category=FutureWarning)
   ```

3. Document as technical debt in TASKS.md

## Success Criteria

- ✅ No FutureWarning in logs
- ✅ All 408 tests pass
- ✅ Manual smoke test produces valid content
- ✅ No regression in generation quality
- ✅ Performance unchanged (±5%)

## Timeline

| Date | Milestone |
|------|-----------|
| 2026-03-24 | Investigation complete, plan documented |
| 2026-03-25 | Test instructor upgrade, run test suite |
| 2026-03-26 | Decision: proceed with upgrade or fallback |
| 2026-03-29 | Implementation complete, PR merged |
| 2026-06-01 | Hard deadline (package EOL) |

## References

- [Deprecated package README](https://github.com/google-gemini/deprecated-generative-ai-python/blob/main/README.md)
- [New google.genai package](https://github.com/googleapis/python-genai)
- [Instructor library](https://github.com/jxnl/instructor)

## Related Issues

- See TASKS.md for tracking
- Link to Linear issue (to be created)

---

**Last Updated**: 2026-03-24
**Owner**: System Maintenance
**Priority**: P0 (Critical)
