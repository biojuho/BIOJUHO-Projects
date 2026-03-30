"""Market data adapter with structured snapshots from yfinance."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from typing import Any

logger = logging.getLogger(__name__)

# Handle Unicode path issues with certifi on Windows.
try:
    import certifi

    cert_path = certifi.where()
    try:
        cert_path.encode("ascii")
    except UnicodeEncodeError:
        fd, tmp_path = tempfile.mkstemp(suffix=".pem")
        os.close(fd)
        shutil.copyfile(cert_path, tmp_path)
        os.environ.setdefault("CURL_CA_BUNDLE", tmp_path)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", tmp_path)
        os.environ.setdefault("SSL_CERT_FILE", tmp_path)
except Exception:
    pass

try:
    import yfinance as yf
except ImportError:
    yf = None

ASSET_MAP: dict[str, str] = {
    "BTC": "BTC-USD",
    "Bitcoin": "BTC-USD",
    "ETH": "ETH-USD",
    "Ethereum": "ETH-USD",
    "SOL": "SOL-USD",
    "XRP": "XRP-USD",
    "Nasdaq": "^IXIC",
    "S&P": "^GSPC",
    "S&P500": "^GSPC",
    "Dow": "^DJI",
    "KOSPI": "^KS11",
    "NVDA": "NVDA",
    "Nvidia": "NVDA",
    "TSLA": "TSLA",
    "Tesla": "TSLA",
    "AAPL": "AAPL",
    "Apple": "AAPL",
    "005930": "005930.KS",
    "Samsung": "005930.KS",
}


class MarketAdapter:
    """Provides real-time market price snapshots relevant to article content."""

    def is_available(self) -> bool:
        return yf is not None

    def _lookup_ticker(self, keyword: str) -> str | None:
        if not keyword:
            return None

        normalized = keyword.strip()
        direct = normalized.upper()
        if direct in ASSET_MAP:
            return ASSET_MAP[direct]

        lowered = normalized.lower()
        for alias, ticker in ASSET_MAP.items():
            if alias.lower() == lowered:
                return ticker
        return None

    def _fetch_snapshot(self, ticker: str) -> dict[str, Any] | None:
        if not self.is_available():
            return None

        try:
            asset = yf.Ticker(ticker)
            info = asset.fast_info
            price = info.last_price
            prev_close = info.previous_close
            if price is None or prev_close is None:
                return None

            change_pct = ((price - prev_close) / prev_close) * 100
            return {
                "ticker": ticker,
                "price": float(price),
                "previous_close": float(prev_close),
                "change_pct": float(change_pct),
                "currency": "KRW" if ticker.endswith(".KS") else "USD",
            }
        except Exception as exc:
            logger.warning("Market snapshot fetch failed for %s: %s", ticker, exc)
            return None

    def get_snapshot(self, ticker: str) -> dict[str, Any] | None:
        """Return a structured market snapshot for a concrete ticker."""
        resolved = self._lookup_ticker(ticker) or ticker
        return self._fetch_snapshot(resolved)

    def get_snapshot_by_keyword(self, keyword: str) -> dict[str, Any] | None:
        """Resolve a keyword to a ticker and return a structured snapshot."""
        ticker = self._lookup_ticker(keyword)
        if not ticker:
            return None
        return self._fetch_snapshot(ticker)

    def get_market_snapshot(self, text: str) -> str | None:
        """Return a formatted snapshot string for the assets mentioned in text."""
        if not self.is_available():
            return None

        text_lower = text.lower()
        found_tickers: set[str] = set()
        for keyword, ticker in ASSET_MAP.items():
            if keyword.lower() in text_lower:
                found_tickers.add(ticker)
        if not found_tickers:
            return None

        results: list[str] = []
        for ticker in list(found_tickers)[:5]:
            snapshot = self._fetch_snapshot(ticker)
            if not snapshot:
                continue

            price = snapshot["price"]
            change_pct = snapshot["change_pct"]
            currency_symbol = "KRW " if ticker.endswith(".KS") else "$"
            price_str = f"{price:,.0f}" if price > 500 else f"{price:,.2f}"
            sign = "+" if change_pct >= 0 else ""
            display = ticker.replace("-USD", "")
            results.append(f"{display} {currency_symbol}{price_str} ({sign}{change_pct:.1f}%)")

        if not results:
            return None
        return "Market Snapshot: " + " | ".join(results)
