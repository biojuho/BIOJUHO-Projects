# Incident Record: GetDayTrends Runtime Troubleshooting

**Date**: 2026-04-13  
**Timezone**: Asia/Seoul (KST)  
**Status**: Resolved  
**Severity**: SEV3  
**Affected Runtime**: `getdaytrends/`

## Executive Summary

On 2026-04-13, a report came in for `getdaytrends coroutine object is not subscriptable`.
The live runtime was checked first. In the actual execution path, `getdaytrends/main.py`, the reported exception did not reproduce, and the async `await` fixes were already present.

The current runtime issue turned out to be different. When batch scoring returned `None` for fields such as `volume_last_24h` and `trend_acceleration`, the parser raised `ValidationError` and dropped to item-level fallback, creating noisy logs and reduced batch efficiency.

The parser was updated in `getdaytrends/analysis/parsing.py` to coerce nullable values safely. Regression tests and a dry run confirmed the fix.

The largest source of confusion during investigation was that both `automation/getdaytrends/` and `getdaytrends/` appear in the same workspace. Follow-up verification confirmed that the workspace-root `getdaytrends/` path is a Windows junction alias to `automation/getdaytrends/`, not a second independent source tree. The risk was path ambiguity during triage, not divergent code.

## Reported Symptom

- User report: `'coroutine' object is not subscriptable`
- Live runtime observation: same exception did not reproduce
- Actual current symptom: `batch scoring item fallback ... ValidationError`

## Impact

- No full outage in the live runtime
- Batch scoring dropped to fallback for some items, reducing efficiency and increasing log noise
- Duplicate code trees increased the time needed to identify the true runtime path

## Timeline

All times below are on 2026-04-13 KST.

| Time | Event |
| --- | --- |
| Reported | User reported `coroutine object is not subscriptable` |
| Investigation | Ran `python .\\getdaytrends\\main.py --one-shot --dry-run --no-alerts --limit 1` against the live runtime |
| Investigation | Confirmed `getdaytrends/core/pipeline.py` already had the relevant awaited genealogy and post-run calls |
| Investigation | Found `batch scoring item fallback ... ValidationError` in current logs |
| Fix | Added nullable field coercion in `getdaytrends/analysis/parsing.py` |
| Fix | Added regression coverage in `getdaytrends/tests/test_analyzer.py` |
| Verification | `pytest getdaytrends\\tests\\test_analyzer.py -q` passed |
| Verification | `python .\\getdaytrends\\main.py --one-shot --dry-run --no-alerts --limit 1` completed successfully without the previous fallback warning |

## Root Cause Analysis

### What Happened

During batch scoring, the LLM sometimes returned nullable values such as `volume_last_24h=None` and `trend_acceleration=None`.
The parser treated those values as strict required types and raised `ValidationError`.
That pushed processing from batch mode into item-level fallback.

### Why the Original Report Was Misleading

The reported symptom matched an older or different code path, but not the live runtime path under `getdaytrends/`.
Because both `automation/getdaytrends/` and `getdaytrends/` can appear in commands, logs, and editor tabs, investigation still had to confirm which path was being used before making conclusions, even though the root path is only a junction alias.

### Contributing Factors

1. Two runtime paths appeared to exist in the same workspace, even though one was a junction alias.
2. The parser assumed stricter output than the LLM consistently guaranteed.
3. The log pattern made fallback visible, but not the distinction between degraded batch handling and a real runtime crash.

## Resolution

### Code Changes

- `getdaytrends/analysis/parsing.py`
  - Added `_coerce_nullable_int()`
  - Normalized nullable string, integer, and list fields to safe defaults
- `getdaytrends/tests/test_analyzer.py`
  - Added regression coverage for nullable optional fields
  - Added async batch scoring coverage to confirm nullable fields no longer trigger recovery

### Behavior After Fix

- `None` values are normalized to defaults and parsed successfully
- Truly malformed non-null values still raise and continue to use fallback, so the change reduces noise without hiding real errors

## Verification

### Commands

```powershell
pytest getdaytrends\tests\test_analyzer.py -q
python .\getdaytrends\main.py --one-shot --dry-run --no-alerts --limit 1
```

### Results

- `pytest getdaytrends\tests\test_analyzer.py -q`
  - `32 passed`
- `python .\getdaytrends\main.py --one-shot --dry-run --no-alerts --limit 1`
  - Exit code `0`
  - Previous `batch scoring item fallback ... ValidationError` warning did not reappear

## Lessons Learned

1. User-reported symptoms are useful starting points, but the first check should always be against the actual live entrypoint.
2. LLM-facing parsers should explicitly define how nullable fields are handled.
3. Duplicate runtime trees slow incident response and make fixes harder to track.

## Follow-up Actions

1. Document that `automation/getdaytrends/` is the canonical repo path and `getdaytrends/` is a compatibility junction alias.
2. In operational troubleshooting, always confirm the real execution command first.
3. Track batch scoring fallback counts separately so routine coercion and real quality regressions can be distinguished.
