# Auto Research Loop - AgriGuard QR A/B Sample Evidence - 2026-07-06

## Objective

Refresh the QR verification page A/B quality evidence without changing the currently dirty `ab_test_qr_page.py` script. The goal is to preserve the existing analysis path while clearly separating sample-only design evidence from production telemetry evidence.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_QR_AB_SAMPLE_EVIDENCE_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Evidence

- `python apps\AgriGuard\scripts\ab_test_qr_page.py --json-out var\agriguard-qr-page-ab-auto-research-2026-07-06.json --output docs\reports\2026-07\AGRIGUARD_QR_PAGE_AB_AUTO_RESEARCH_2026-07-06.md`
  - Result: exit `0`
  - Dataset: `built-in sample`
  - Sessions: `20`
  - Control verification success: `0.60`
  - Guided variant verification success: `0.90`
  - Verification relative lift: `0.50`
  - Median time improved: `true`
  - Invalid error rate not worse: `true`
  - Decision output: `adopt_b`

## Interpretation

Adopt the guided QR verification direction as a design hypothesis for the launch candidate, not as production telemetry proof. The built-in sample favors version B strongly, but the generated report itself states that sample sessions should be replaced with real scan and verification telemetry.

## Current Blocker

This A/B run does not remove the main launch blocker. Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`. A production A/B decision should additionally be rerun against real `qr_scan_events` telemetry once the launch path can collect live scan sessions.
