# Environment Mapping

Canonical variables and backward-compatible aliases:

| Canonical | Supported Alias | Notes |
| --- | --- | --- |
| `NOTION_TASKS_DATABASE_ID` | `ANTIGRAVITY_TASKS_DB_ID`, `ANTIGRAVITY_DB_ID`, `NOTION_DATABASE_ID` | Use canonical name for all new setups. |
| `NOTION_TASKS_DATA_SOURCE_ID` | None | Legacy compatibility only. Do not use it to choose the Notion query endpoint. |
| `NOTION_REPORTS_DATABASE_ID` | `ANTIGRAVITY_NEWS_DB_ID` | Report publishing target. |
| `NOTION_REPORTS_DATA_SOURCE_ID` | None | Legacy compatibility only. Database queries should use `NOTION_REPORTS_DATABASE_ID`. |
| `NOTION_DASHBOARD_PAGE_ID` | `DASHBOARD_PAGE_ID` | Dashboard auto-refresh target page. |
| `GOOGLE_API_KEY` | `GEMINI_API_KEY` | Google LLM access. |

Operational rule:

- Canonical names must be present in deployment automation and documentation.
- Alias support exists only to avoid breaking existing local environments.
- Query operations should use `/v1/databases/{id}/query`, not `/v1/data_sources/{id}/query`.
- The MCP settings resource (`config://settings`) exposes which aliases are still being used.
