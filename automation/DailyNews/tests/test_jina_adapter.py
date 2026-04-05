import pytest
from unittest.mock import AsyncMock, patch

from antigravity_mcp.integrations.jina_adapter import JinaAdapter

@pytest.mark.asyncio
async def test_jina_adapter_fetch_success():
    adapter = JinaAdapter()
    
    mock_response = AsyncMock()
    mock_response.text = "This is a long deep text context" * 200
    mock_response.raise_for_status.return_value = None
    
    with patch("httpx.AsyncClient.get", return_value=mock_response):
        ctx = await adapter.fetch_deep_context("https://example.com")
        assert "This is a long deep text context" in ctx
        assert len(ctx) <= 4000

@pytest.mark.asyncio
async def test_jina_adapter_fetch_invalid_url():
    adapter = JinaAdapter()
    ctx = await adapter.fetch_deep_context("invalid-url")
    assert ctx == ""

@pytest.mark.asyncio
async def test_jina_adapter_fetch_concurrent():
    adapter = JinaAdapter()
    
    async def mock_get(url, **kwargs):
        resp = AsyncMock()
        resp.text = f"Content for {url}"
        return resp
        
    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        urls = ["https://a.com", "invalid", "https://b.com"]
        res = await adapter.fetch_contexts_for_urls(urls)
        
        assert len(res) == 2
        assert res["https://a.com"] == "Content for https://r.jina.ai/https://a.com"
        assert res["https://b.com"] == "Content for https://r.jina.ai/https://b.com"
