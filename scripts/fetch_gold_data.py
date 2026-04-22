#!/usr/bin/env python3
"""
Fetch gold futures (GC=F) data via yfinance.
Outputs gold_data.json with current price + 2-year daily history.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yfinance as yf
    import pandas as pd
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = DATA_DIR / "gold_data.json"


def fetch_gold_data():
    if not HAS_YFINANCE:
        print("[WARN] yfinance not installed, using fallback mock data")
        return mock_gold_data()

    ticker = yf.Ticker("GC=F")

    # 2 years of daily data for Chart.js MA
    hist = ticker.history(period="2y")
    if hist.empty:
        print("[WARN] yfinance returned empty, using fallback")
        return mock_gold_data()

    # Build price series
    prices = []
    for date, row in hist.iterrows():
        prices.append({
            "date": date.strftime("%Y-%m-%d"),
            "close": round(row["Close"], 2),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0
        })

    # Current info
    info = ticker.fast_info
    current_price = hist["Close"].iloc[-1]
    prev_price = hist["Close"].iloc[-2] if len(hist) > 1 else current_price
    change = current_price - prev_price
    change_pct = (change / prev_price * 100) if prev_price else 0

    result = {
        "ticker": "GC=F",
        "name": "Gold Futures",
        "current_price": round(current_price, 2),
        "prev_close": round(prev_price, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "currency": "USD",
        "unit": "oz",
        "last_updated": datetime.now().astimezone().isoformat(),
        "history": prices
    }

    print(f"  ✓ Gold: ${current_price:.2f} ({change_pct:+.2f}%) | {len(prices)} days")
    return result


def mock_gold_data():
    """Fallback when yfinance unavailable (local dev without pip install)."""
    from math import sin, cos
    base = 2000.0
    today = datetime.now()
    prices = []
    for i in range(730):
        d = today - timedelta(days=730 - i)
        noise = 50 * sin(i * 0.05) + 30 * cos(i * 0.02) + (i % 60) * 0.3
        close = round(base + noise, 2)
        prices.append({
            "date": d.strftime("%Y-%m-%d"),
            "close": close,
            "open": round(close * 0.999, 2),
            "high": round(close * 1.005, 2),
            "low": round(close * 0.995, 2),
            "volume": 200000
        })
    return {
        "ticker": "GC=F",
        "name": "Gold Futures (mock)",
        "current_price": prices[-1]["close"],
        "prev_close": prices[-2]["close"],
        "change": round(prices[-1]["close"] - prices[-2]["close"], 2),
        "change_pct": round((prices[-1]["close"] - prices[-2]["close"]) / prices[-2]["close"] * 100, 2),
        "currency": "USD",
        "unit": "oz",
        "last_updated": datetime.now().astimezone().isoformat(),
        "history": prices
    }


if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching gold data...")
    data = fetch_gold_data()
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[DONE] Written to {OUTPUT_FILE}")
