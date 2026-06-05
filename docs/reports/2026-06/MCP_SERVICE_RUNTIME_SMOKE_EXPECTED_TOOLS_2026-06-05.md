# MCP Service Runtime Smoke

- Status: `pass`
- Manifest generated at: `2026-06-04T21:03:00+09:00`
- Checked services: `3`
- Skipped services: `1`
- Passed services: `3`
- Failed services: `0`
- Credential-gated checked services: `1`
- Total tools listed: `39`

## Services

### dailynews-antigravity

- Status: `pass`
- Server: `Antigravity Content Engine MCP` / `1.26.0`
- Command: `C:\Users\bioju\AppData\Local\Programs\Python\Python314\python.exe -m antigravity_mcp serve`
- Tools listed: `26`
- Expected minimum tools: `26`
- Expected runtime tools: `add_task, append_block, content_generate_brief, content_invoke_skill, content_publish_report, create_page, get_token_usage, notion_append_blocks, notion_create_page, notion_create_record, notion_get_page, notion_search, ops_auto_collect_metrics, ops_check_health, ops_cleanup, ops_collect_tweet_metrics, ops_export_analytics, ops_get_content_calendar, ops_get_cost_report, ops_get_run_status, ops_get_tweet_performance, ops_list_runs, ops_refresh_dashboard, ops_run_frozen_eval, read_page, search_notion`
- Missing expected tools: `none`
- Missing env for tool calls: `none`
- Capability keys: `experimental, prompts, resources, tools`

### desci-research

- Status: `pass`
- Server: `desci-research` / `1.26.0`
- Command: `C:\Users\bioju\AppData\Local\Programs\Python\Python314\python.exe server.py`
- Tools listed: `6`
- Expected minimum tools: `6`
- Expected runtime tools: `find_related_papers, get_paper_details, get_research_trends, search_arxiv, search_grants, search_semantic_scholar`
- Missing expected tools: `none`
- Missing env for tool calls: `none`
- Capability keys: `experimental, prompts, resources, tools`

### telegram-bot

- Status: `pass`
- Server: `telegram-bot` / `1.26.0`
- Command: `C:\Users\bioju\AppData\Local\Programs\Python\Python314\python.exe server.py`
- Tools listed: `7`
- Expected minimum tools: `7`
- Expected runtime tools: `get_updates, send_alert, send_approval_request, send_cost_report, send_message, send_pipeline_report, send_trend_alert`
- Missing expected tools: `none`
- Missing env for tool calls: `TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID`
- Capability keys: `experimental, prompts, resources, tools`

## Skipped Services

- `canva-local`: `stdio_transport_not_declared`

## Errors

- none
