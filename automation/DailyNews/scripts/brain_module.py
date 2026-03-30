"""Thin wrapper around :class:`BrainAdapter` for backward compatibility.

Legacy ``scripts/run_daily_news.py`` calls ``BrainModule().analyze_news(...)``
synchronously.  This wrapper delegates to the canonical async implementation
in ``antigravity_mcp.integrations.brain_adapter`` and bridges async->sync.
"""

import asyncio
import sys
from pathlib import Path

# Ensure the project root is importable (for both scripts/ and MCP contexts)
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_PROJECT = Path(__file__).resolve().parents[1]
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))

from antigravity_mcp.integrations.brain_adapter import BrainAdapter  # noqa: E402


class BrainModule:
    """Synchronous facade over :class:`BrainAdapter`."""

    def __init__(self):
        self._adapter = BrainAdapter()

    def analyze_news(self, category: str, articles: list, time_window: str = "", niche_trends: list = None) -> dict:
        """Synchronous bridge to ``BrainAdapter.analyze_news``."""
        if not articles:
            return None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run,
                    self._adapter.analyze_news(category, articles, time_window, niche_trends),
                ).result()
        return asyncio.run(self._adapter.analyze_news(category, articles, time_window, niche_trends))


if __name__ == "__main__":
    # Test Code
    print("Brain Module Test (Gemini)...")
    brain = BrainModule()
    test_data = [
        {
            "title": "Bitcoin surges past $100k",
            "description": "Crypto market is booming as institutional investors flock in.",
        },
        {"title": "Ethereum upgrade successful", "description": "Gas fees lowered significantly after the new patch."},
    ]
    result = brain.analyze_news("Crypto", test_data)
    if result:
        print("Summary:", result.get("summary"))
        print("Insights:", result.get("insights"))
        print("X Thread:", result.get("x_thread"))
    else:
        print("Failed to analyze news.")
