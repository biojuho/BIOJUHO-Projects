# Google Generative AI Migration Plan

**Status**: ✅ RESOLVED - No Action Required
**Investigation Completed**: 2026-03-24
**Conclusion**: Warning is cosmetic, our code already uses google.genai correctly

## Overview

The `google.generativeai` package has been deprecated and will no longer receive updates or bug fixes.

**Original Concern**: FutureWarning appearing in getdaytrends logs
**Investigation Result**: ✅ Our code is already compliant, warning comes from instructor's backward compatibility layer

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

## Investigation Results (2026-03-24) ✅

### Finding 1: Instructor Already Supports google.genai
- **Latest instructor version**: 1.14.5 (released 2026-01-29)
- **Documentation confirms**: `from_provider("google/gemini-2.5-flash")` support
- **New unified API**: `instructor.from_provider()` available
- **Source**: https://python.useinstructor.com/integrations/genai/

### Finding 2: Warning Source Identified
- **Location**: `.venv/Lib/site-packages/instructor/providers/gemini/client.py:5`
- **Code**: `import google.generativeai as genai`
- **Reason**: Instructor's legacy provider support for backward compatibility
- **Impact on our code**: None - we don't use instructor's Gemini provider

### Finding 3: Current Package Status (Workspace)
```bash
google-genai                 1.62.0   # ✅ New unified SDK (what we use)
google-generativeai          0.8.6    # ⚠️ Deprecated (instructor dependency)
instructor                   1.14.5   # ✅ Latest version
```

### Finding 4: getdaytrends Does NOT Need Migration
- ✅ Uses `shared.llm` library
- ✅ `shared.llm` uses `google-genai` directly
- ❌ Does NOT use instructor's Gemini provider
- ❌ Does NOT import `google.generativeai` anywhere
- **Verification**: `grep -r "google.generativeai" getdaytrends/` → No results

## Recommended Approach

### ✅ NO MIGRATION REQUIRED

Our code is already compliant:
1. ✅ Uses `google-genai` (correct package)
2. ✅ Does not directly import `google.generativeai`
3. ✅ Will not break when `google-generativeai` reaches EOL
4. ⚠️ Warning is cosmetic (from instructor's backward compatibility)

### Option A: Do Nothing (Recommended)
- **Pros**: Zero risk, no code changes
- **Cons**: Warning continues to appear in logs
- **When to use**: If warnings don't bother you

### Option B: Suppress Warning
Add to `getdaytrends/structured_output.py` (line 1):
```python
import warnings
warnings.filterwarnings(
    "ignore",
    message=".*google.generativeai.*",
    category=FutureWarning,
)
```

- **Pros**: Clean logs
- **Cons**: May hide other legitimate warnings
- **When to use**: If log cleanliness is important

### Option C: Wait for Instructor Update
Monitor https://github.com/567-labs/instructor/releases

- **Pros**: No action, upstream fixes it
- **Cons**: Unknown timeline
- **When to use**: Patient, don't want to modify code

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

| Date | Milestone | Status |
|------|-----------|--------|
| 2026-03-24 | Investigation started | ✅ Complete |
| 2026-03-24 | Root cause identified | ✅ Complete |
| 2026-03-24 | Verified code compliance | ✅ Complete |
| 2026-03-24 | **RESOLVED**: No migration needed | ✅ Complete |
| 2026-06-01 | Hard deadline (package EOL) | ⏸️ Not applicable - we don't use deprecated package |

**Conclusion**: Investigation complete. No action required. Our code already uses `google-genai` correctly.

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
