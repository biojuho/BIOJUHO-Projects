# Environment Mapping

Canonical variables and migration mappings for removed legacy names:

| Canonical | Legacy Name / Alias | Notes |
| --- | --- | --- |
| `NOTION_TASKS_DATABASE_ID` | `ANTIGRAVITY_TASKS_DB_ID`, `ANTIGRAVITY_DB_ID`, `NOTION_DATABASE_ID` | Removed legacy names. Migrate any local envs to the canonical variable. |
| `NOTION_TASKS_DATABASE_ID` | `NOTION_TASKS_DATA_SOURCE_ID` | Removed legacy data source variable. Task queries use `/v1/databases/{id}/query`. |
| `NOTION_REPORTS_DATABASE_ID` | `ANTIGRAVITY_NEWS_DB_ID` | Removed legacy name. Use the canonical report database variable. |
| `NOTION_REPORTS_DATABASE_ID` | `NOTION_REPORTS_DATA_SOURCE_ID` | Removed legacy data source variable. Report queries use `/v1/databases/{id}/query`. |
| `NOTION_DASHBOARD_PAGE_ID` | `DASHBOARD_PAGE_ID` | Removed legacy name. Falls back to `config/dashboard_config.json` only when the canonical env is empty. |
| `GOOGLE_API_KEY` | `GEMINI_API_KEY` | Still supported alias for Google LLM access. |

Operational rule:

- Canonical names must be present in deployment automation and documentation.
- Removed legacy Notion names are kept here only to help migrate old local environments.
- Query operations should use `/v1/databases/{id}/query`, not `/v1/data_sources/{id}/query`.
- Shared deployment examples intentionally omit deprecated alias variables.
- The MCP settings resource (`config://settings`) exposes which removed legacy names are still present in the environment.
- Do not introduce new scripts, tests, or runbooks that depend on alias names.

Related:

- See [`gray-zone-closure-checklist.md`](./gray-zone-closure-checklist.md) for the current alias retirement plan and release sign-off rules.
