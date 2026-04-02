from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace


def _load_market_adapter(fake_yfinance):
    sys.modules["yfinance"] = fake_yfinance
    sys.modules.pop("antigravity_mcp.integrations.market_adapter", None)
    return importlib.import_module("antigravity_mcp.integrations.market_adapter")


class TestMarketAdapter:
    def test_lookup_and_snapshot_paths(self, monkeypatch):
        class FakeTicker:
            def __init__(self, ticker: str):
                self.ticker = ticker
                self.fast_info = SimpleNamespace(last_price=950.0, previous_close=900.0)

        module = _load_market_adapter(SimpleNamespace(Ticker=FakeTicker))
        adapter = module.MarketAdapter()

        assert adapter.is_available() is True
        assert adapter._lookup_ticker("Nvidia") == "NVDA"
        assert adapter._lookup_ticker("unknown") is None

        nvda = adapter.get_snapshot("NVDA")
        samsung = adapter.get_snapshot("Samsung")
        by_keyword = adapter.get_snapshot_by_keyword("Bitcoin")

        assert nvda["ticker"] == "NVDA"
        assert round(nvda["change_pct"], 2) == round((950.0 - 900.0) / 900.0 * 100, 2)
        assert samsung["currency"] == "KRW"
        assert by_keyword["ticker"] == "BTC-USD"

    def test_market_snapshot_text_and_error_handling(self):
        class FakeTicker:
            def __init__(self, ticker: str):
                if ticker == "BAD":
                    raise RuntimeError("boom")
                self.fast_info = SimpleNamespace(last_price=120.0, previous_close=100.0)

        module = _load_market_adapter(SimpleNamespace(Ticker=FakeTicker))
        adapter = module.MarketAdapter()

        text = adapter.get_market_snapshot("Bitcoin and Nvidia both moved today.")
        assert text is not None
        assert "BTC" in text
        assert "NVDA" in text

        module.ASSET_MAP["Broken"] = "BAD"
        assert adapter.get_snapshot_by_keyword("Broken") is None

        adapter._fetch_snapshot = lambda ticker: None
        assert adapter.get_market_snapshot("Bitcoin") is None

    def test_unavailable_returns_none(self):
        module = _load_market_adapter(SimpleNamespace(Ticker=lambda ticker: None))
        module.yf = None
        adapter = module.MarketAdapter()

        assert adapter.is_available() is False
        assert adapter.get_snapshot("NVDA") is None
        assert adapter.get_snapshot_by_keyword("Nvidia") is None
        assert adapter.get_market_snapshot("Bitcoin") is None
