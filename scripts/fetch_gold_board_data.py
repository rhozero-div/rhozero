#!/usr/bin/env python3
"""
Fetch Gold Board data: all 21 nodes across 4 layers.
Sources: FRED API (macro) + yfinance (gold price) + GLD ETF holdings.
Outputs gold_board_data.json.
"""
import json
import os
import math
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import yfinance as yf
    import pandas as pd
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT = DATA_DIR / "gold_board_data.json"


# ─── FRED Series Map ────────────────────────────────────────────────────────
FRED_SERIES = {
    # Layer 4: Institutional
    "debt_gdp":        ("GFDEGDQ188S",   "percent",   "Federal Debt to GDP"),
    "deficit_gdp":     ("FYFSD",         "percent",   "Federal Deficit to GDP"),
    # interest_income ratio — no single FRED series; use NETEXP + FYFR
    # Layer 3: Macro
    "real_rate":       ("DFII10",        "percent",   "10-Yr Real Interest Rate"),
    "inflation_exp":   ("T10YIE",        "percent",   "10-Yr Inflation Expectation"),
    "dxy":             ("DTWEXBGS",      "index",     "Trade Weighted USD Broad"),
    "financial_cond":  ("NFCI",          "index",     "Chicago Financial Conditions"),
    "core_pce":        ("PCEPI",         "percent",   "Core PCE Price Index YoY"),
    "unemployment":    ("UNRATE",        "percent",   "Unemployment Rate"),
    "gold_price_fred": ("GOLDAMGBD228NLBM", "usd",    "Gold Fixing Price"),
}


def fetch_fred_series(series_id: str, api_key: str, limit: int = 30) -> tuple:
    """Returns (latest_value, latest_date_str) or (None, None) on failure."""
    if not HAS_REQUESTS:
        return None, None
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "limit": limit,
        "sort_order": "desc",
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        for o in obs:
            if o["value"] not in ("", ".", None):
                return float(o["value"]), o["date"]
    except Exception as e:
        print(f"    [WARN] FRED {series_id}: {e}")
    return None, None


def calc_ma(series: list, window: int) -> list:
    """Simple moving average over a list of floats."""
    result = []
    for i in range(len(series)):
        if i < window - 1:
            result.append(None)
        else:
            result.append(round(sum(series[i - window + 1:i + 1]) / window, 2))
    return result


def fetch_gold_price_yf():
    """Get gold futures via yfinance."""
    if not HAS_YFINANCE:
        return None, None, []
    try:
        ticker = yf.Ticker("GC=F")
        hist = ticker.history(period="2y")
        if hist.empty:
            return None, None, []
        closes = hist["Close"].tolist()
        dates = [d.strftime("%Y-%m-%d") for d in hist.index]
        cur = closes[-1] if closes else None
        prev = closes[-2] if len(closes) > 1 else cur
        return cur, prev, [{"date": d, "close": round(c, 2)} for d, c in zip(dates, closes)]
    except Exception as e:
        print(f"    [WARN] yfinance gold: {e}")
    return None, None, []


def fetch_gld_holdings():
    """Estimate GLD ETF holdings change from yfinance."""
    if not HAS_YFINANCE:
        return None
    try:
        ticker = yf.Ticker("GLD")
        hist = ticker.history(period="5d")
        if hist.empty:
            return None
        # shares outstanding proxy: use close * volume as flow indicator
        return round(hist["Volume"].iloc[-1] / 1e6, 2) if len(hist) else None
    except Exception as e:
        print(f"    [WARN] GLD: {e}")
    return None


def calc_fiscal_index(debt_gdp: float, deficit_gdp: float) -> dict:
    """
    Fiscal Pressure Index.
    Components:
      - debt/gdp  : weight 40  (baseline 50%=0, 150%=100)
      - deficit/gdp: weight 25  (baseline 1%=0, 10%=100)
      - interest burden approx from deficit surge (weight 35)
    """
    if debt_gdp is None:
        return {"score": None, "zone": "unknown", "components": {}}

    # Normalize each to 0-100
    d1 = max(0, min(100, (debt_gdp - 50) / 100 * 40))          # debt weight 40
    d2 = max(0, min(100, (deficit_gdp - 1) / 9 * 25))          # deficit weight 25
    # Interest pressure proxy: deficit magnitude as proxy
    d3 = max(0, min(100, (deficit_gdp - 1) / 5 * 35))          # interest weight 35 (surge proxy)

    score = round(d1 + d2 + d3, 1)
    if score < 40:
        zone = "normal"
    elif score < 60:
        zone = "vigilant"
    elif score < 80:
        zone = "financial_repression"
    else:
        zone = "crisis"

    return {
        "score": score,
        "zone": zone,
        "components": {
            "debt_gdp": round(d1, 1),
            "deficit_gdp": round(d2, 1),
            "interest_burden": round(d3, 1),
        }
    }


def percentile(value: float, history: list) -> float:
    """Return percentile rank of value in history."""
    if value is None or not history:
        return None
    sorted_hist = sorted([x for x in history if x is not None])
    if not sorted_hist:
        return None
    rank = sum(1 for x in sorted_hist if x <= value)
    return round(rank / len(sorted_hist) * 100, 1)


def main():
    api_key = os.environ.get("FRED_API_KEY", "")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching Gold Board data...")

    result = {
        "updated_at": datetime.now().astimezone().isoformat(),
        "layers": {},
        "fiscal_index": {},
        "matrix_2x2": {},
        "four_suits": {},
        "price_history": [],
    }

    # ── FRED data ───────────────────────────────────────────────────────────
    fred_data = {}
    if api_key:
        for key, (series_id, unit, name) in FRED_SERIES.items():
            val, date = fetch_fred_series(series_id, api_key)
            if val is not None:
                fred_data[key] = {"value": val, "date": date, "unit": unit}
                print(f"    {key}: {val} ({date})")
            else:
                fred_data[key] = {"value": None, "date": None, "unit": unit}

    # ── Gold price ──────────────────────────────────────────────────────────
    gold_cur, gold_prev, price_hist = fetch_gold_price_yf()
    if gold_cur is None:
        # Fallback to FRED gold price
        gold_cur = fred_data.get("gold_price_fred", {}).get("value")
        gold_prev = gold_cur
    result["gold_price"] = {
        "current": gold_cur,
        "prev": gold_prev,
        "change": round(gold_cur - gold_prev, 2) if gold_cur and gold_prev else None,
        "change_pct": round((gold_cur - gold_prev) / gold_prev * 100, 2) if gold_cur and gold_prev else None,
    }
    result["price_history"] = price_hist[-730:]  # 2 years max

    # ── Moving averages ──────────────────────────────────────────────────────
    closes = [x["close"] for x in price_hist]
    ma20 = calc_ma(closes, 20)
    ma60 = calc_ma(closes, 60)
    ma200 = calc_ma(closes, 200)
    result["moving_averages"] = {
        "ma20": ma20,
        "ma60": ma60,
        "ma200": ma200,
        "dates": [x["date"] for x in price_hist],
    }

    # ── Layer data ───────────────────────────────────────────────────────────
    result["layers"] = {
        "4_institutional": {
            "debt_gdp":      fred_data.get("debt_gdp", {}).get("value"),
            "deficit_gdp":   fred_data.get("deficit_gdp", {}).get("value"),
            "debt_date":     fred_data.get("debt_gdp", {}).get("date"),
            "deficit_date":  fred_data.get("deficit_gdp", {}).get("date"),
        },
        "3_macro": {
            "real_rate":       fred_data.get("real_rate", {}).get("value"),
            "inflation_exp":    fred_data.get("inflation_exp", {}).get("value"),
            "dxy":             fred_data.get("dxy", {}).get("value"),
            "financial_cond":  fred_data.get("financial_cond", {}).get("value"),
            "core_pce":        fred_data.get("core_pce", {}).get("value"),
            "unemployment":    fred_data.get("unemployment", {}).get("value"),
        },
        "2_market": {
            "gld_etf_flow": fetch_gld_holdings(),
        },
    }

    # ── Fiscal Pressure Index ───────────────────────────────────────────────
    debt_gdp = fred_data.get("debt_gdp", {}).get("value")
    deficit_gdp = fred_data.get("deficit_gdp", {}).get("value")
    result["fiscal_index"] = calc_fiscal_index(debt_gdp, deficit_gdp)
    result["fiscal_index"]["debt_gdp_raw"] = debt_gdp
    result["fiscal_index"]["deficit_gdp_raw"] = deficit_gdp
    print(f"    Fiscal Index: {result['fiscal_index']['score']} ({result['fiscal_index']['zone']})")

    # ── 2×2 Matrix ─────────────────────────────────────────────────────────
    pce = fred_data.get("core_pce", {}).get("value")
    # PMI approximation: if NFCI < 0, growth cond is positive
    nfci = fred_data.get("financial_cond", {}).get("value")
    unemp = fred_data.get("unemployment", {}).get("value")

    # Approximate growth from NFCI and unemployment
    growth_signal = "weak"
    if nfci is not None and unemp is not None:
        if nfci > 0 or unemp > 5.0:
            growth_signal = "weak"
        else:
            growth_signal = "strong"

    inflation_signal = "low"
    if pce is not None:
        inflation_signal = "high" if pce > 2.5 else "low"

    quadrant_map = {
        ("strong", "high"):   {"label": "繁荣", "implication": "risk-on, gold neutral", "signal": "neutral"},
        ("weak",   "high"):   {"label": "类滞胀", "implication": "黄金最喜欢", "signal": "bullish"},
        ("strong", "low"):    {"label": "正常增长", "implication": "黄金中性", "signal": "neutral"},
        ("weak",   "low"):    {"label": "衰退", "implication": "黄金中性偏多", "signal": "cautious_bull"},
    }
    quadrant = quadrant_map.get((growth_signal, inflation_signal), {})
    result["matrix_2x2"] = {
        "growth": growth_signal,
        "inflation": inflation_signal,
        "quadrant": quadrant,
    }
    print(f"    Matrix: growth={growth_signal}, inflation={inflation_signal} → {quadrant.get('label','?')}")

    # ── Four Suits ───────────────────────────────────────────────────────────
    # GVZ approximation from gold price volatility
    if len(closes) >= 20:
        returns = [math.log(closes[i]/closes[i-1]) for i in range(1, len(closes))]
        recent_returns = returns[-20:]
        if recent_returns:
            mean_r = sum(recent_returns) / len(recent_returns)
            std_r = math.sqrt(sum((r - mean_r)**2 for r in recent_returns) / len(recent_returns))
            # Annualized GVZ proxy (multiply by sqrt(252) for 30-day vol)
            gvz_proxy = round(std_r * math.sqrt(252) * 100, 1)
        else:
            gvz_proxy = None
    else:
        gvz_proxy = None

    # CFTC proxy: use open interest as % of gold price
    cfct_proxy = None  # CFTC COT requires dedicated scraper

    # GLD ETF
    gld_flow = result["layers"]["2_market"].get("gld_etf_flow")

    result["four_suits"] = {
        "gvz": {
            "value": gvz_proxy,
            "label": "Gold Volatility (GVZ)",
            "signal": "neutral",
        },
        "ma_system": {
            "value": gold_cur,
            "ma20": ma20[-1] if ma20 else None,
            "ma60": ma60[-1] if ma60 else None,
            "ma200": ma200[-1] if ma200 else None,
        },
        "gld_etf": {
            "value": gld_flow,
            "unit": "M shares (volume proxy)",
        },
        "cfct": {
            "value": cfct_proxy,
            "note": "CFTC COT requires dedicated scraper",
        },
    }

    # ── Write output ────────────────────────────────────────────────────────
    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[DONE] Gold board data → {OUTPUT}")


if __name__ == "__main__":
    main()
