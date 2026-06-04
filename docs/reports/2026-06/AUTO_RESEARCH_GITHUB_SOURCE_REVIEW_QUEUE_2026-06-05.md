# AutoResearch: GitHub Source Review Queue

## Objective

Convert the live GitHub source-change summary into an actionable review queue
for the next source-backed AutoResearch cycle.

## A/B Contract

- Baseline: `GITHUB_SOURCE_CHANGE_SUMMARY_2026-06-05` showed which tracked
  repositories changed, but every changed repo had to be reviewed manually.
- Variant: add a deterministic queue builder that scores changed repositories
  by source-code movement, repository policy/viability fields, issue movement,
  source category, and adoption status.
- Primary KPI: changed GitHub sources become a ranked queue with stable JSON
  and Markdown evidence.
- Decision rule: adopt if the queue ranks all changed sources, keeps new and
  removed repositories explicit, and is protected by tests plus pre-push.
- Decision: adopted. The queue ranks `27/27` changed repositories with
  `new_repositories=0` and `removed_repositories=0`.

## Queue Summary

- Source change summary:
  `docs/reports/2026-06/GITHUB_SOURCE_CHANGE_SUMMARY_2026-06-05.json`
- Queue artifacts:
  - `docs/reports/2026-06/GITHUB_SOURCE_REVIEW_QUEUE_2026-06-05.json`
  - `docs/reports/2026-06/GITHUB_SOURCE_REVIEW_QUEUE_2026-06-05.md`
- Top review candidates:
  1. `microsoft/agent-framework` - source code and issue metadata moved
  2. `mastra-ai/mastra` - source code, issue, fork, and star metadata moved
  3. `microsoft/playwright-mcp` - source code, issue, fork, and star metadata moved
  4. `vercel/ai` - source code, issue, fork, and star metadata moved

## Implementation

- `ops/scripts/github_source_review_queue.py`
  - Reads the checked-in live GitHub source change summary.
  - Reuses the modernization manifest for source category, adoption status,
    URLs, and local evidence.
  - Scores changed fields with `pushed_at` and repository policy fields above
    passive community metrics.
- `tests/test_github_source_review_queue.py`
  - Verifies source-code movement outranks passive metadata movement.
  - Rejects summaries that were not compared against a baseline.
  - Checks CLI output generation.
  - Compares checked-in JSON/Markdown artifacts to the current renderer.
- `ops/hooks/pre-push`
  - Runs `tests/test_github_source_review_queue.py` in the real pre-push
    pytest bundle.

## Verification

- `python -m pytest tests/test_github_source_review_queue.py -q`
  - `4 passed`
- `python -m pytest tests/test_github_source_review_queue.py tests/test_github_source_freshness.py tests/test_autoresearch_completion_audit.py tests/test_autoresearch_objective_coverage.py tests/test_pre_push_hook.py tests/test_canva_widget_click_smoke.py tests/test_dev_server_browser_smoke.py -q`
  - `51 passed`
- `python -m py_compile ops/scripts/github_source_review_queue.py ops/scripts/github_source_freshness.py ops/scripts/autoresearch_completion_audit.py ops/scripts/autoresearch_objective_coverage.py ops/scripts/canva_widget_click_smoke.py ops/scripts/dev_server_browser_smoke.py`
  - passed
- `python ops/scripts/autoresearch_completion_audit.py`
  - valid `40` criteria, `global_objective_complete=false`
- `python ops/scripts/autoresearch_objective_coverage.py`
  - valid `7` requirements, `global_objective_complete=false`

## Remaining Boundary

This queue ranks candidates for the next source-backed review. It does not
claim that upstream code changes have already been adopted locally, and the
global objective remains open: `global_objective_complete=false`.
