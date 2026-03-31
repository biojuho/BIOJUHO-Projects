# DailyNews — Antigravity Content Engine

AI 뉴스 자동 수집·분석·발행 플랫폼 (Notion + MCP + LLM)

Antigravity Content Engine is a Notion-native AI content platform that combines:

- an MCP server for AI agents,
- content collection and briefing pipelines,
- draft publishing workflows for X and Canva,
- operational dashboards backed by local state and Notion.

This repository keeps the original compatibility entrypoints, but the active implementation now lives under [`src/antigravity_mcp`](./src/antigravity_mcp).

## Target Audience

**Primary Persona**: "경제 인사이트 헌터" (Economic Insight Hunter)

**Profile**: 20-40대 직장인, 소상공인, 1인 창업자 who need fast, actionable economic insights for daily decision-making.

**Key Characteristics**:
- Time-constrained professionals (5-10 minutes available for morning news)
- High interest in personal finance, real estate, and stock markets
- Value practicality over academic depth
- Prefer data-driven, politically neutral content
- Primary consumption: X (Twitter) longform posts during commute (7-9 AM)

**What They Need**:
- Quick daily economic briefings with concrete numbers and facts
- Actionable insights for investment/financial decisions
- Shareable content that makes them look informed
- Mobile-optimized format (400-800 characters)

**Success Metrics**:
- X engagement rate >5% (likes + retweets + replies / views)
- Notion page views >100/day
- Average read time >2 minutes

For detailed audience analysis, see [workspace-audience-profiles.md](../../.claude/skills/audience-first/references/workspace-audience-profiles.md#1-dailynews--antigravity-content-engine).



## Product Scope

The platform is optimized for internal content operations:

- collect curated sources from RSS and market feeds,
- summarize and package them into report drafts,
- store report state locally and sync approved outputs to Notion,
- expose search, authoring, and operational status through MCP tools,
- monitor run health and report readiness in Streamlit and Notion dashboards.

## Canonical Operating Rules

- Treat [`src/antigravity_mcp`](./src/antigravity_mcp) as the only active implementation path for new code changes.
- Do not add new call sites to compatibility entrypoints such as `server.py`, `admin_dashboard.py`, `run_server.bat`, or legacy MCP tool names.
- Use the canonical Notion database IDs for queries and writes. Data source IDs remain compatibility-only inputs.
- Treat `.env` as the deployment source of truth. `config/dashboard_config.json` is a local fallback, not a stable deployment contract.
- Keep external delivery status separate from approval mode and separate from local report storage status.

## Report Lifecycle Terms

Use the following vocabulary in tickets, runbooks, and handoffs.

| Term | Meaning in the current implementation | Source of truth |
| --- | --- | --- |
| `draft` | A report exists locally but does not yet have a Notion page ID. | `data/pipeline_state.db` |
| `published` | Current stored shorthand meaning the report has been synced to Notion. Do not use this word as proof of external posting. | Local mirror plus `notion_page_id` |
| `notion_synced` | Preferred operational label when a report has a non-empty `notion_page_id`. | Notion record plus local mirror |
| `external_posted` | Preferred operational label when a channel adapter actually posts to an external destination such as X. | Channel adapter result and analytics |
| `approval_mode` | Review policy (`manual` or `auto`). This is not a delivery state. | Report metadata |

Team rule:

- In docs and reviews, prefer `notion_synced` and `external_posted` over the generic word `published`.

## Source Of Truth Hierarchy

- Notion reports database: curated report output for approved briefs.
- `data/pipeline_state.db`: local run tracking, deduplication, approval metadata, and report lifecycle mirror.
- `data/analytics.db`: downstream channel delivery and metrics history.
- `.env`: canonical deployment configuration for Notion targets and external integrations.
- `config/dashboard_config.json`: temporary local fallback only when the env value is intentionally absent.

## Project Layout

```text
src/antigravity_mcp/
  config.py
  server.py
  tooling/
  domain/
  integrations/
  pipelines/
  state/
apps/
  streamlit_dashboard.py
config/
  news_sources.json
  channels.json
docs/
  product/
  runbooks/
```

## Canonical Environment Variables

Use the canonical names below for all new deployments.

Required for active Notion reads and writes:

- `NOTION_API_KEY`
- `NOTION_TASKS_DATABASE_ID`
- `NOTION_REPORTS_DATABASE_ID`
- `NOTION_DASHBOARD_PAGE_ID`
- `GOOGLE_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `CANVA_CLIENT_ID`
- `CANVA_CLIENT_SECRET`
- `CANVA_REFRESH_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `PIPELINE_MAX_CONCURRENCY`
- `PIPELINE_HTTP_TIMEOUT_SEC`
- `PIPELINE_MAX_RETRIES`
- `CONTENT_APPROVAL_MODE`

DailyNews now queries Notion with the standard database endpoint:

- `/v1/databases/{id}/query`

For new setups, always provide the database IDs above. Legacy names such as `ANTIGRAVITY_DB_ID`, `ANTIGRAVITY_TASKS_DB_ID`, `ANTIGRAVITY_NEWS_DB_ID`, `DASHBOARD_PAGE_ID`, `NOTION_TASKS_DATA_SOURCE_ID`, and `NOTION_REPORTS_DATA_SOURCE_ID` are no longer read and will surface warnings until local environments are updated.

If `NOTION_DASHBOARD_PAGE_ID` is temporarily missing, the runtime can fall back to `config/dashboard_config.json`, but `.env` remains the source of truth for stable deployments.

For the current retirement plan and release criteria, see [`docs/runbooks/gray-zone-closure-checklist.md`](./docs/runbooks/gray-zone-closure-checklist.md).

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

If you prefer a runtime-only installation:

```bash
pip install -e .
```

Optional extras:

```bash
pip install -e .[dashboard]
pip install -e .[viz]
pip install -e .[market]
pip install -e .[social]
```

The runtime will auto-discover the workspace-level `shared.llm` package when this repository is used inside the
`AI 프로젝트` monorepo. Outside the monorepo, make sure `shared` is installed or exposed on `PYTHONPATH`.

## Commands

Run the MCP server:

```bash
python -m antigravity_mcp serve
```

Windows without editable install:

```bat
run_cli.bat serve
```

Generate briefs:

```bash
python -m antigravity_mcp jobs generate-brief --window morning --max-items 5
```

Windows without editable install:

```bat
run_cli.bat jobs generate-brief --window morning --max-items 5
```

Publish a stored report draft:

```bash
python -m antigravity_mcp jobs publish-report --report-id report-tech-20260302T010000Z
```

Refresh the dashboard:

```bash
python -m antigravity_mcp ops refresh-dashboard
```

Replay a supported run:

```bash
python -m antigravity_mcp ops replay-run --run-id generate_brief-20260302T010000Z
```

Compatibility entrypoints still exist:

- `python server.py`
- `python admin_dashboard.py`
- `run_server.bat`
- `run_server.sh`

## MCP Tooling

Canonical MCP tools:

- `notion_search`
- `notion_get_page`
- `notion_create_page`
- `notion_append_blocks`
- `notion_create_record`
- `content_generate_brief`
- `content_publish_report`
- `ops_get_run_status`
- `ops_list_runs`
- `ops_refresh_dashboard`

Legacy MCP tools are still available with deprecation warnings:

- `search_notion`
- `read_page`
- `add_task`
- `create_page`
- `append_block`

All canonical tools now return a structured response envelope:

```json
{
  "status": "ok",
  "data": {},
  "meta": {
    "warnings": []
  },
  "error": null
}
```

## Testing

```bash
python -m pytest -q
```

## Notes

- Notion remains the system of record for curated report output.
- Local SQLite state in `data/pipeline_state.db` is used for run tracking, deduplication, and report lifecycle management.
- External publishing stays in manual approval mode by default.
- Release approval is stricter than deterministic QC. See [`../../docs/QUALITY_GATE.md`](../../docs/QUALITY_GATE.md).
