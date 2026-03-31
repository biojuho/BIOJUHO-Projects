# DailyNews (Antigravity Content Engine)

## Quick ref
- `pip install -e .` then `python -m pytest tests/ -q`
- Config: `src/antigravity_mcp/config.py` → `get_settings()` (lru_cached, clear in tests)
- State: `PipelineStateStore` — SQLite with 9 mixins, schema version 2
- LLM: shared.llm → Gemini → Claude → GPT fallback chain
- `LLMUnavailableError` blocks auto-publish when all providers fail

## Gotchas
- `test_qc_pipeline_fix.py` reads live `data/pipeline_state.db` — flaky by design
- Use `state_store` fixture from conftest.py for isolated DB tests
- `_SECTION_PATTERNS` uses pre-compiled regex; don't pass raw strings
- `pyproject.toml` is the dep source of truth; `requirements.txt` mirrors it
