from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DAILYNEWS_SRC = PROJECT_ROOT / "automation" / "DailyNews" / "src"
if str(DAILYNEWS_SRC) not in sys.path:
    sys.path.insert(0, str(DAILYNEWS_SRC))


class _Budget:
    def can_afford(self, _tokens: int) -> bool:
        return True

    def record(self, **_kwargs) -> None:
        return None

    def get_detail_level(self):
        return SimpleNamespace(value="standard")


@pytest.mark.asyncio
async def test_llm_client_wrapper_emits_workspace_smoke_usage_sidecar(monkeypatch, tmp_path):
    from antigravity_mcp.integrations.llm import client_wrapper

    client_wrapper._L1_CACHE.clear()
    usage_path = tmp_path / "usage.json"
    monkeypatch.setenv("WORKSPACE_SMOKE_USAGE_OUT", str(usage_path))

    async def fake_shared_llm(*, prompt, max_tokens, meta, warnings):
        meta["provider"] = "shared.llm"
        meta["model_name"] = "test-model"
        meta["input_tokens"] = 10
        meta["output_tokens"] = 5
        return "Fresh generated brief\nwith enough lines\nfor validation"

    async def fail_fallback(*_args, **_kwargs):
        pytest.fail("fallback providers should not be used")

    wrapper = client_wrapper.LLMClientWrapper(state_store=None, token_budget=_Budget())
    monkeypatch.setattr(wrapper, "_try_shared_llm", fake_shared_llm)
    monkeypatch.setattr(wrapper, "_try_fallback_providers", fail_fallback)

    text, meta, warnings = await wrapper._complete_text(
        prompt=("system", "user prompt"),
        max_tokens=100,
        cache_scope="unit-sidecar",
    )

    assert text == "Fresh generated brief\nwith enough lines\nfor validation"
    assert meta["provider"] == "shared.llm"
    assert warnings == []
    assert json.loads(usage_path.read_text(encoding="utf-8")) == {
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        "provider": "shared.llm",
        "model_name": "test-model",
        "cache_scope": "unit-sidecar",
    }
