# QC Report - Brief Style and Automation Check
**Date**: 2026-03-29
**Project**: DailyNews
**Status**: PASS

---

## Summary

This QC pass validated the updated DailyNews morning briefing flow after the writing-style rollback and Notion publish fixes.

The current default output is now the concise `v1-brief` mode with:
- `오늘의 핫 이슈` opener
- emoji section headings
- natural paragraph flow
- no explicit labels such as `핵심 사실:`, `배경/디테일:`, or `전망/의미:`

The scheduled morning job remains enabled for **2026-03-30 07:00 KST** and will use the updated prompt path automatically.

---

## Scope

- Confirm prompt default is concise brief mode
- Confirm `Brief` body is parsed and rendered into Notion-friendly markdown
- Confirm forbidden label words are removed from saved brief bodies
- Confirm scheduled publish path uses generated `report_id` values
- Confirm shared LLM path no longer fails on unsupported `temperature` args

---

## Changes Validated

### 1. Brief style default
- Default prompt mode now resolves to `v1-brief`
- Detailed mode still remains available via environment override

### 2. Brief body structure
- Main body starts with `오늘의 핫 이슈: {category}. ...`
- Uses markdown headings like `## [emoji] short title`
- Writes short editorial paragraphs instead of field labels

### 3. Persistence and publish rendering
- Parsed `brief_body` is saved into `analysis_meta`
- Stored brief body is normalized before persistence
- `v1-brief` reports render the styled body first in Notion markdown

### 4. Shared LLM compatibility
- `shared.llm` calls now retry without `temperature` when the client signature rejects it
- This removes the avoidable first-hop failure that previously caused fallback noise during generation

---

## Verification

### Automated tests

Command:

```powershell
python -m pytest automation/DailyNews/tests/unit -q
```

Result:

```text
64 passed in 22.82s
```

Additional covered cases:
- concise prompt mode default
- env-driven detailed mode fallback
- `v1-brief` parsing and insight limit
- brief body normalization before persistence
- styled markdown rendering for `v1-brief`
- fact-check adapter resolver path
- frozen eval prompt mode expectations
- shared LLM retry without `temperature`

### Functional smoke check

Smoke run target:
- category: `Economy_Global`
- window: `morning`
- database: temporary local DB

Observed result:

```json
{
  "generation_mode": "v1-brief",
  "quality_state": "ok",
  "summary_count": 3,
  "insight_count": 2,
  "has_brief_body": true,
  "has_forbidden_labels": false,
  "x_draft_length": 135
}
```

Only non-blocking warning in the smoke run:
- cluster analysis detected one multi-source topic

---

## Operational Notes

- The morning scheduler is enabled and currently set to run at **2026-03-30 07:00:00 KST**
- The scheduled task still uses **Interactive** logon mode
- Practical implication: the PC should be awake and logged in at run time for the job to start on schedule

---

## Limitations

- This QC did **not** re-run a live Notion write during the final verification pass
- Live publish behavior was validated earlier in the session, but the final QC focused on local generation, persistence, parser behavior, and renderer correctness

---

## Conclusion

The current DailyNews brief pipeline is in a good state for the next scheduled morning run.

The new concise format is active by default, the forbidden label words are removed, the styled brief body persists correctly, and the shared LLM path is more stable than before.
