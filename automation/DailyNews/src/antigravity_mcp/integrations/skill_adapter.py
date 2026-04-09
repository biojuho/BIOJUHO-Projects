"""Skill Integrator — migrated and extended from legacy news_bot.py.

Provides a registry of named pipeline skills that can be invoked by name
via the ``content_invoke_skill`` MCP tool.

Built-in skills:
  - ``summarize_category``    collect + analyze for a single category
  - ``market_snapshot``       call MarketAdapter for ticker prices
  - ``proofread``             run ProofreaderAdapter on arbitrary text
  - ``brain_analysis``        cross-article BrainAdapter analysis
  - ``sentiment_classify``    classify text sentiment via SentimentAdapter

Custom skills can be registered at runtime via :meth:`SkillAdapter.register`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for async skill functions
SkillFn = Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]


class SkillAdapter:
    """Registry of named pipeline skills."""

    def __init__(
        self,
        *,
        state_store: Any | None = None,
        llm_adapter: Any | None = None,
    ) -> None:
        self._state_store = state_store
        self._llm_adapter = llm_adapter
        self._registry: dict[str, SkillFn] = {}
        self._register_builtins()

    # ── Registry ──────────────────────────────────────────────────────────

    def register(self, name: str, fn: SkillFn) -> None:
        """Register a custom async skill function under *name*."""
        self._registry[name] = fn
        logger.debug("Registered skill: %s", name)

    def list_skills(self) -> list[str]:
        return sorted(self._registry.keys())

    async def invoke(self, skill_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Invoke a named skill with *params*. Returns a result dict."""
        fn = self._registry.get(skill_name)
        if fn is None:
            available = ", ".join(self.list_skills()) or "(none)"
            return {
                "status": "error",
                "skill": skill_name,
                "message": f"Unknown skill '{skill_name}'. Available: {available}",
            }
        try:
            result = await fn(params)
            return {"status": "ok", "skill": skill_name, "result": result}
        except Exception as exc:
            logger.error("Skill '%s' raised %s: %s", skill_name, type(exc).__name__, exc)
            return {
                "status": "error",
                "skill": skill_name,
                "message": f"{type(exc).__name__}: {exc}",
            }

    # ── Built-in skills ───────────────────────────────────────────────────

    def _register_builtins(self) -> None:
        self.register("summarize_category", self._skill_summarize_category)
        self.register("market_snapshot", self._skill_market_snapshot)
        self.register("proofread", self._skill_proofread)
        self.register("brain_analysis", self._skill_brain_analysis)
        self.register("sentiment_classify", self._skill_sentiment_classify)

    async def _skill_summarize_category(self, params: dict[str, Any]) -> dict[str, Any]:
        """collect + analyze for a single category. Params: category, window (optional)."""
        from antigravity_mcp.pipelines.analyze import generate_briefs
        from antigravity_mcp.pipelines.collect import collect_content_items, get_window
        from antigravity_mcp.state.store import PipelineStateStore

        category = params.get("category")
        if not category:
            raise ValueError("'category' param is required.")
        window = params.get("window", "manual")
        max_items = int(params.get("max_items", 5))
        store = self._state_store or PipelineStateStore()
        owns_store = self._state_store is None
        try:
            items, collect_warnings = await collect_content_items(
                categories=[category],
                window_name=window,
                max_items=max_items,
                state_store=store,
            )
            if not items:
                return {"items": [], "reports": [], "warnings": collect_warnings}

            window_start, window_end = get_window(window)
            _, reports, llm_warnings, _ = await generate_briefs(
                items=items,
                window_name=window,
                window_start=window_start.isoformat(),
                window_end=window_end.isoformat(),
                state_store=store,
                llm_adapter=self._llm_adapter,
            )
            return {
                "items_collected": len(items),
                "reports": [r.to_dict() for r in reports],
                "warnings": collect_warnings + llm_warnings,
            }
        finally:
            if owns_store:
                store.close()

    async def _skill_market_snapshot(self, params: dict[str, Any]) -> dict[str, Any]:
        """Get market price snapshots. Params: tickers (list[str]) or keywords (list[str])."""
        try:
            from antigravity_mcp.integrations.market_adapter import MarketAdapter  # type: ignore
        except ImportError:
            raise RuntimeError("market_adapter not available; install yfinance: pip install yfinance")

        tickers = params.get("tickers", [])
        keywords = params.get("keywords", [])
        adapter = MarketAdapter()
        results: dict[str, Any] = {}
        for ticker in tickers:
            results[ticker] = adapter.get_snapshot(ticker)
        for kw in keywords:
            results[kw] = adapter.get_snapshot_by_keyword(kw)
        return {"snapshots": results}

    async def _skill_proofread(self, params: dict[str, Any]) -> dict[str, Any]:
        """Korean text proofreading. Params: text (str)."""
        try:
            from antigravity_mcp.integrations.proofreader_adapter import ProofreaderAdapter  # type: ignore
        except ImportError:
            raise RuntimeError("proofreader_adapter not available.")

        text = params.get("text", "")
        if not text:
            raise ValueError("'text' param is required.")
        adapter = ProofreaderAdapter()
        corrected = await adapter.proofread(text)
        return {"original": text, "corrected": corrected}

    async def _skill_brain_analysis(self, params: dict[str, Any]) -> dict[str, Any]:
        """Cross-article BrainAdapter analysis. Params: category, articles (list[dict])."""
        try:
            from antigravity_mcp.integrations.brain_adapter import BrainAdapter  # type: ignore
        except ImportError:
            raise RuntimeError("brain_adapter not available.")

        category = str(params.get("category", "")).strip()
        articles = params.get("articles", [])
        time_window = str(params.get("time_window", "") or "")
        niche_trends = params.get("niche_trends")
        if not category:
            raise ValueError("'category' param is required.")
        if not articles:
            raise ValueError("'articles' param (list of dicts with title/summary) is required.")
        adapter = BrainAdapter()
        result = await adapter.analyze_news(
            category,
            articles,
            time_window=time_window,
            niche_trends=niche_trends,
        )
        return result

    async def _skill_sentiment_classify(self, params: dict[str, Any]) -> dict[str, Any]:
        """Classify text sentiment. Params: text (str)."""
        try:
            from antigravity_mcp.integrations.sentiment_adapter import SentimentAdapter  # type: ignore
        except ImportError:
            raise RuntimeError("sentiment_adapter not available.")

        text = params.get("text", "")
        if not text:
            raise ValueError("'text' param is required.")
        adapter = SentimentAdapter()
        results = await adapter.analyze([text])
        if results:
            r = results[0]
            return r.to_dict() if hasattr(r, "to_dict") else {"sentiment": r.sentiment, "topics": r.topics}
        return {"sentiment": "NEUTRAL", "topics": []}
