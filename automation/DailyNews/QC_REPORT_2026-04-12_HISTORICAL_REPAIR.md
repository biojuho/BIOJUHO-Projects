# QC Report - Historical Repair and Parser Hardening
**Date**: 2026-04-12
**Project**: DailyNews
**Status**: PASS WITH REVIEWABLE OUTPUTS

---

## Summary

This QC pass closed the remaining historical fallback/meta-response corruption in DailyNews and hardened the v1 brief parser so the same failure mode is less likely to recur.

Final verified state:
- Historical cache restore path is documented and tested
- v1 parser no longer treats preamble/title text as summary content
- v1 parser now accepts inline section forms such as `Summary - ...`
- Cache-restored reports now record accurate provenance as `sqlite-cache`
- All previously suspicious historical reports have been cleared from the repair scan
- 30 reports now carry `manual_repair` metadata
- Of those repaired reports, 4 are `ok` and 26 remain `needs_review`

---

## Scope

- QC the parser and repair changes introduced during the historical cleanup work
- Patch the two parser edge cases found during review
- Patch the repair-selection logic so clearly better contentful candidates are not left behind as fallback placeholders
- Re-run repair on the final unresolved reports
- Verify local DB state and linked Notion pages after repair

---

## Findings Addressed

### 1. v1 preamble leakage into summary lines
- Some v1 responses began with a title or preamble before the first section header
- The parser previously defaulted to `summary` mode and incorrectly stored that preamble as a summary line
- This polluted repaired reports and could worsen contract evaluation

### 2. Inline v1 section syntax not handled
- Responses of the form `Summary - ...` or `Brief - ...` were not parsed as intended
- This caused otherwise usable cache candidates to degrade or be skipped

### 3. Historical repair acceptance was too strict
- The repair script only accepted a candidate when total contract violations went down, or stayed equal for partial repair
- In practice this left broken fallback reports unrepaired even when a nearby cache entry contained real article-driven content
- A repaired report with two residual violations is still materially better than an apology/fallback body with one citation violation

### 4. Repair provenance was misleading
- Restored reports kept their old parser provider metadata instead of explicitly recording that the final body came from SQLite cache restore

---

## Changes Validated

### 1. v1 parser hardening
- `response_parser.py` now ignores content before the first recognized v1 section header
- `response_parser.py` now extracts inline section content such as `Summary - ...`, `Insights - ...`, `Brief - ...`, and `Draft - ...`
- Existing markdown header handling and bullet stripping behavior remain covered

### 2. Historical repair logic refinement
- `repair_historical_reports.py` now allows a narrow partial-repair tradeoff when:
  - the current report is clearly suspicious/fallback
  - the candidate is nearby in time
  - the candidate is contentful and non-meta
  - the candidate only introduces one extra contract issue beyond the broken fallback shell
- This specifically unlocks recovery for reports where the original placeholder only appeared better because it lacked meaningful structure

### 3. Accurate restore provenance
- Restored rows now record:
  - `parser.provider = sqlite-cache`
  - `parser.upstream_provider`
  - `parser.previous_model_name`
  - `manual_repair.source_provider_before_restore`
  - `manual_repair.source_model_before_restore`

### 4. Final unresolved historical cases repaired
- Final repaired reports in this pass:
  - `report-crypto-20260409T090403Z`
  - `report-economy_kr-20260409T012314Z`
  - `report-tech-20260408T220110Z`
- Linked Notion pages for those reports were updated and re-fetched successfully

---

## Verification

### Targeted code validation

Commands used:

```powershell
python -m py_compile src/antigravity_mcp/integrations/llm/response_parser.py scripts/repair_historical_reports.py tests/unit/test_pipelines.py tests/unit/test_repair_historical_reports.py
python -m pytest -q -p no:cacheprovider tests/unit/test_pipelines.py tests/unit/test_repair_historical_reports.py -k "parse_v1_brief_response or auto_heal_does_not_overwrite_with_meta_diagnostic_summary or repair_historical_reports"
```

Observed result:

```text
8 passed
```

### Final repair scan

Command used:

```powershell
python scripts/repair_historical_reports.py --limit 200 --lookback-minutes 720 --max-candidates 600
```

Observed result:

```text
No suspicious reports found.
```

### State summary after repair

Observed local state:

```text
manual_repair_count: 30
manual_repair_quality:
  ok: 4
  needs_review: 26
manual_repair_unique_notion_pages: 18
suspicious_count: 0
```

---

## Operational Notes

- Backup snapshots for repaired reports were written under `data/repair_backups/`
- The repair script remains intentionally conservative about far-away candidates and obvious meta/resubmission text
- `needs_review` repaired reports are no longer broken fallback/apology outputs, but they still do not satisfy every category contract requirement
- Those `needs_review` cases should remain under manual approval until a separate citation/data-anchor regeneration pass is performed

---

## Files Involved

- `src/antigravity_mcp/integrations/llm/response_parser.py`
- `scripts/repair_historical_reports.py`
- `tests/unit/test_pipelines.py`
- `tests/unit/test_repair_historical_reports.py`

---

## Conclusion

The historical repair effort is now in a clean QC state.

The parser is more robust against real-world v1 response formats, repair provenance is accurate, all suspicious fallback/meta-corrupted historical reports have been cleared, and the remaining repaired outputs are now reviewable article-based briefs rather than broken placeholders.
