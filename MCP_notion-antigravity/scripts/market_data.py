

import os
import shutil
import certifi
import tempfile
import atexit
import sys
import io

# Force UTF-8 for Windows Console
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

# [Fix] Workaround for curl_cffi/yfinance failing with Unicode paths (e.g., "AI 프로젝트")
# We copy the cert file to a temporary ASCII-safe path and point environment variables to it.
try:
    cert_path = certifi.where()
    # Check if path has non-ascii characters
    try:
        cert_path.encode('ascii')
    except UnicodeEncodeError:
        # Create a temp file for the cert
        temp_cert_fd, temp_cert_path = tempfile.mkstemp(suffix='.pem')
        os.close(temp_cert_fd)
        
        # Copy original cert content to temp file
        shutil.copyfile(cert_path, temp_cert_path)
        
        # Set environment variables for curl and requests
        os.environ['CURL_CA_BUNDLE'] = temp_cert_path
        os.environ['REQUESTS_CA_BUNDLE'] = temp_cert_path
        os.environ['SSL_CERT_FILE'] = temp_cert_path
        
        print(f"[System] Unicode path detected. Using temp cert at: {temp_cert_path}")
        
        # Cleanup on exit
        def cleanup_cert():
            try:
                if os.path.exists(temp_cert_path):
                    os.remove(temp_cert_path)
            except:
                pass
        atexit.register(cleanup_cert)
except Exception as e:
    print(f"[System Warning] Failed to setup cert workaround: {e}")

import yfinance as yf
import re

# Key Asset Map (Korean/English keywords -> Ticker)
# Priorities: Crypto > Major Indices > Big Tech
ASSET_MAP = {
    # Crypto
    "비트코인": "BTC-USD", "비트": "BTC-USD", "BTC": "BTC-USD", "Bitcoin": "BTC-USD",
    "이더리움": "ETH-USD", "이더": "ETH-USD", "ETH": "ETH-USD", "Ethereum": "ETH-USD",
    "솔라나": "SOL-USD", "SOL": "SOL-USD",
    "리플": "XRP-USD", "XRP": "XRP-USD",
    "도지": "DOGE-USD", "DOGE": "DOGE-USD",

    # Indices
    "나스닥": "^IXIC", "Nasdaq": "^IXIC",
    "S&P500": "^GSPC", "S&P": "^GSPC",
    "다우": "^DJI", "Dow": "^DJI",
    "코스피": "^KS11", "KOSPI": "^KS11",

    # Big Tech & Chips
    "엔비디아": "NVDA", "Nvidia": "NVDA", "NVDA": "NVDA",
    "테슬라": "TSLA", "Tesla": "TSLA", "TSLA": "TSLA",
    "애플": "AAPL", "Apple": "AAPL", "AAPL": "AAPL",
    "마이크로소프트": "MSFT", "Microsoft": "MSFT", "MSFT": "MSFT",
    "구글": "GOOGL", "Google": "GOOGL", "알파벳": "GOOGL",
    "아마존": "AMZN", "Amazon": "AMZN",
    "메타": "META", "Meta": "META",
    "삼성전자": "005930.KS", "삼성": "005930.KS",
    "SK하이닉스": "000660.KS", "하이닉스": "000660.KS"
}

def get_market_summary(text: str) -> str:
    """
    Scans text for keywords and returns a formatted string with real-time prices.
    Returns None if no relevant assets found.
    Format: "💰 Market: BTC $95,000 (+1.2%) | NVDA $135 (-0.5%)"
    """
    found_tickers = set()
    
    # 1. Detect keywords
    # Normalize text for simple matching
    text_lower = text.lower()
    
    # Pre-scan to avoid calling API for unrelated texts
    # (Checking against keys is fast enough for ~50 keys)
    for keyword, ticker in ASSET_MAP.items():
        if keyword.lower() in text_lower:
            found_tickers.add(ticker)
    
    # Always include BTC and Nasdaq if 'market' or 'crypto' generic terms are mostly used, 
    # but for now let's stick to detected ones to keep it relevant.
    # Exception: If specific categories (e.g. Crypto) are passed, we might force some.
    # But this function only sees text.
    
    if not found_tickers:
        return None

    # Limit to top 5 detected to avoid clutter
    target_tickers = list(found_tickers)[:5]
    
    # 2. Fetch Data
    try:
        # yfinance allows fetching multiple tickers at once: "BTC-USD NVDA"
        tickers_str = " ".join(target_tickers)
        data = yf.Tickers(tickers_str)
        
        results = []
        
        for ticker in target_tickers:
            try:
                info = data.tickers[ticker].fast_info
                # fast_info provides 'last_price' and 'previous_close'
                # Note: fast_info is generally faster/more reliable for price than .info
                
                price = info.last_price
                prev_close = info.previous_close
                
                if price is None or prev_close is None:
                    continue

                change_pct = ((price - prev_close) / prev_close) * 100
                
                # Format
                # Crypto: integer if > 100 (e.g. 96500), else 2 decimals
                # Stocks: 2 decimals
                if price > 500: # Like BTC, KOSPI
                    price_str = f"{price:,.0f}"
                else:
                    price_str = f"{price:,.2f}"
                
                # Add Currency symbol rough logic
                currency = "$" 
                if ticker.endswith(".KS"): currency = "₩"
                
                # Sign icon
                sign = "+" if change_pct >= 0 else ""
                
                # Ticker Short Name (remove -USD for crypto display)
                display_name = ticker.replace("-USD", "")
                
                results.append(f"{display_name} {currency}{price_str} ({sign}{change_pct:.1f}%)")
                
            except Exception as e:
                print(f"[Market Data Fail] {ticker}: {e}")
                continue
                
        if not results:
            return None
            
        return "💰 Market Snapshot: " + " | ".join(results)

    except Exception as e:
        print(f"[Market Data Error] {e}")
        return None

if __name__ == "__main__":
    # Test
    test_text = "비트코인이 급등하고 엔비디아도 상승세입니다."
    print(get_market_summary(test_text))
