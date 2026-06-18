"""
BioLinker - Search Service
Web Search Capability for Agentic AI
"""

import random
import time

try:
    from duckduckgo_search import DDGS

    DDG_AVAILABLE = True
except ImportError:
    DDG_AVAILABLE = False
    print("[SearchService] duckduckgo-search not found.")


class SearchService:
    """
    Service for performing web searches.
    Wraps duckduckgo-search and provides a consistent API.
    """

    def __init__(self):
        self.ddgs = DDGS() if DDG_AVAILABLE else None

    def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        """
        Perform a text search.

        Args:
            query: Search query string
            max_results: Number of results to return

        Returns:
            List of dictionaries containing 'title', 'href', 'body'
        """
        if not self.ddgs:
            return [{"title": "Error", "href": "#", "body": "Search service not available."}]

        try:
            # Random delay to be polite
            time.sleep(random.uniform(0.5, 1.5))

            results = list(self.ddgs.text(query, max_results=max_results))
            return results
        except Exception as e:
            print(f"[SearchService] Search failed: {e}")
            return [{"title": "Error", "href": "#", "body": f"Search failed: {str(e)}"}]


# Singleton
_search_service = None


def get_search_service():
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
