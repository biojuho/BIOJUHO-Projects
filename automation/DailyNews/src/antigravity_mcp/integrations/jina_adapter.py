import logging
import httpx
import asyncio

logger = logging.getLogger(__name__)

class JinaAdapter:
    """Fetches deep context from external URLs using jina.ai Reader API."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    async def fetch_deep_context(self, url: str) -> str:
        """Fetches the main content of an article via Jina AI API."""
        import os
        if not url or not url.startswith("http"):
            return ""

        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            "User-Agent": "Antigravity/DeepResearch",
            "X-Target-URI": url
        }
        
        jina_api_key = os.getenv("JINA_API_KEY")
        if jina_api_key:
            headers["Authorization"] = f"Bearer {jina_api_key}"
            
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(jina_url, headers=headers)
                resp.raise_for_status()
                # Return up to the first 4000 characters to prevent overwhelming context
                return resp.text[:4000]
        except Exception as exc:
            logger.debug(f"Failed to fetch deep context via Jina.ai for {url}: {exc}")
            return ""

    async def fetch_contexts_for_urls(self, urls: list[str]) -> dict[str, str]:
        """Concurrently fetch multiple URLs."""
        # Filter valid URLs
        valid_urls = [u for u in urls if u and u.startswith("http")]
        if not valid_urls:
            return {}

        results = {}
        # Fetch concurrently
        tasks = [self.fetch_deep_context(u) for u in valid_urls]
        contents = await asyncio.gather(*tasks, return_exceptions=True)
        
        for url, content in zip(valid_urls, contents):
            if isinstance(content, str) and content:
                results[url] = content
                
        return results

    async def search_topic(self, query: str, limit: int = 3, max_length: int = 4000) -> str:
        """Searches Jina AI for a topic and returns a text summary containing top results."""
        import os
        if not query:
            return ""

        # Using s.jina.ai with query
        jina_url = f"https://s.jina.ai/{query}"
        headers = {
            "User-Agent": "Antigravity/DeepResearch",
            "X-Retain-Images": "none",
        }
        
        jina_api_key = os.getenv("JINA_API_KEY")
        if jina_api_key:
            headers["Authorization"] = f"Bearer {jina_api_key}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(jina_url, headers=headers)
                resp.raise_for_status()
                # Return up to the max_length to prevent overwhelming context
                return resp.text[:max_length]
        except Exception as exc:
            logger.debug(f"Failed to search topic via Jina.ai for '{query}': {exc}")
            return ""

