"""Market data adapter — real-time price snapshots from yfinance."""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
from typing import Any

logger = logging.getLogger(__name__)

# Handle Unicode path issue with certifi on Windows
try:
    import certifi

    cert_path = certifi.where()
    try:
        cert_path.encode("ascii")
    except UnicodeEncodeError:
        _fd, _tmp = tempfile.mkstemp(suffix=".pem")
        os.close(_fd)
        shutil.copyfile(cert_path, _tmp)
        os.environ.setdefault("CURL_CA_BUNDLE", _tmp)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", _tmp)
        os.environ.setdefault("SSL_CERT_FILE", _tmp)
except Exception:
    pass

try:
    import yfinance as yf
except ImportError:
    yf = None

# Korean/English keyword → ticker map
ASSET_MAP: dict[str, str] = {
    # Crypto
    "비트코인": "BTC-USD", "BTC": "BTC-USD", "Bitcoin": "BTC-USD",
    "이더리움": "ETH-USD", "ETH": "ETH-USD", "Ethereum": "ETH-USD",
    "솔라나": "SOL-USD", "SOL": "SOL-USD",
    "리플": "XRP-USD", "XRP": "XRP-USD",
    # Indices
    "나스닥": "^IXIC", "Nasdaq": "^IXIC",
    "S&P500": "^GSPC", "S&P": "^GSPC",
    "다우": "^DJI", "Dow": "^DJI",
    "코스피": "^KS11", "KOSPI": "^KS11",
    # Big Tech
    "엔비디아": "NVDA", "Nvidia": "NVDA", "NVDA": "NVDA",
    "테슬라": "TSLA", "Tesla": "TSLA", "TSLA": "TSLA",
    "애플": "AAPL", "Apple": "AAPL",
    "삼성전자": "005930.KS", "삼성": "005930.KS",
}


class MarketAdapter:
    """Provides real-time market price snapshots relevant to article content."""

    def is_available(self) -> bool:
        return yf is not None

    def get_market_snapshot(self, text: str) -> str | None:
        """Scan *text* for asset keywords and return a formatted price line.

        Returns ``None`` if no relevant assets are detected or yfinance is missing.
        """
        if not self.is_available():
            return None

        text_lower = text.lower()
        found_tickers: set[str] = set()
        for keyword, ticker in ASSET_MAP.items():
            if keyword.lower() in text_lower:
                found_tickers.add(ticker)
        if not found_tickers:
            return None

        target_tickers = list(found_tickers)[:5]
        try:
            data = yf.Tickers(" ".join(target_tickers))
            results: list[str] = []
            for ticker in target_tickers:
                try:
                    info = data.tickers[ticker].fast_info
                    price = info.last_price
                    prev_close = info.previous_close
                    if price is None or prev_close is None:
                        continue
                    change_pct = ((price - prev_close) / prev_close) * 100
                    price_str = f"{price:,.0f}" if price > 500 else f"{price:,.2f}"
                    currency = "₩" if ticker.endswith(".KS") else "$"
                    sign = "+" if change_pct >= 0 else ""
                    display = ticker.replace("-USD", "")
                    results.append(f"{display} {currency}{price_str} ({sign}{change_pct:.1f}%)")
                except Exception:
                    continue
            if not results:
                return None
            return "💰 Market Snapshot: " + " | ".join(results)
        except Exception as exc:
            logger.warning("Market snapshot fetch failed: %s", exc)
            return None
