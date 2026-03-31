# Gray-Zone Closure Checklist

This runbook turns the DailyNews gray-zone discussion into concrete operating rules.

## Scope

Use this checklist when:

- updating DailyNews deployment docs,
- removing compatibility layers,
- deciding whether a build is release-ready,
- explaining report state during handoff or incident review.

## Shared Vocabulary

Use these labels consistently:

| Preferred label | Meaning |
| --- | --- |
| `draft` | Local report exists, but no Notion page ID is attached yet. |
| `notion_synced` | The report has a non-empty `notion_page_id` and has been mirrored to Notion. |
| `external_posted` | A channel adapter actually delivered content to an external destination. |
| `approval_mode` | Review policy only. It does not prove delivery. |

Avoid using the bare word `published` unless the target is stated explicitly.

## Legacy Retirement Checklist

- [ ] No new code paths call compatibility entrypoints such as `server.py`, `admin_dashboard.py`, `run_server.bat`, or `run_server.sh`.
- [ ] No new MCP integrations use deprecated tool names (`search_notion`, `read_page`, `add_task`, `create_page`, `append_block`).
- [ ] Deployment automation uses canonical env vars only:
  - `NOTION_TASKS_DATABASE_ID`
  - `NOTION_REPORTS_DATABASE_ID`
  - `NOTION_DASHBOARD_PAGE_ID`
- [x] Local-only aliases are removed from shared deployment examples before the next release cut.
- [x] `NOTION_TASKS_DATA_SOURCE_ID` and `NOTION_REPORTS_DATA_SOURCE_ID` are no longer required by active call sites.
- [ ] The dashboard config fallback is used only for approved local debugging, not for stable deployment.
- [x] A final smoke pass is recorded after alias removal (`python -m pytest -q tests`, `python -m compileall -q src apps scripts` on 2026-03-31).

## Release Approval Checklist

Deterministic QC is necessary but not sufficient for release approval.

- [ ] The relevant deterministic gate passes.
- [ ] The worktree is clean, or every in-progress diff has been explicitly reviewed and accepted for the release.
- [ ] Legacy compatibility warnings from settings or MCP responses have been reviewed.
- [ ] The source of truth is explicit for the feature being released:
  - Notion for curated reports
  - `pipeline_state.db` for run state and report lifecycle mirror
  - `analytics.db` for downstream delivery metrics
- [ ] Any claimed `published` state is clarified as either `notion_synced` or `external_posted`.
- [ ] Manual approval policy has been confirmed for the release window.
- [ ] External services needed for the release have been verified separately from local smoke tests.

## Follow-Up

- Recorded status on `2026-03-31`:
  - Active DailyNews scripts now read canonical `NOTION_*` variables only.
  - Legacy env aliases and Notion data source IDs are no longer read by `config.py`; warnings now point operators to the canonical names.
  - Verification recorded: `python -m pytest -q tests` -> `195 passed`, `python -m compileall -q src apps scripts` -> exit `0`.

- [ ] Re-evaluate the remaining DailyNews and GetDayTrends prompt migration scope after the legacy surface and release rules are aligned.
