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
    # FYFENDA = Annual Federal Deficit (in millions USD, negative = deficit)
    "deficit_gdp":     ("FYFENDA",       "percent",   "Annual Federal Deficit to GDP"),
    # Interest income / total revenue — FRED: FYONET / FYFR (both in millions)
    "interest_burden": ("FYINT",         "percent",   "Federal Interest / Revenue"),
    # Layer 3: Macro
    "real_rate":       ("DFII10",        "percent",   "10-Yr Real Interest Rate"),
    "inflation_exp":   ("T10YIE",        "percent",   "10-Yr Inflation Expectation"),
    "dxy":             ("DTWEXBGS",      "index",     "Trade Weighted USD Broad"),
    "financial_cond":  ("NFCI",          "index",     "Chicago Financial Conditions"),
    "unemployment":    ("UNRATE",        "percent",   "Unemployment Rate"),
    "gold_price_fred": ("GOLDAMGBD228NLBM", "usd",    "Gold Fixing Price"),
    # PCEPI price index (base=100) — YoY computed in fetch_pce_yoy()
    "pcepi":           ("PCEPI",         "index",     "PCE Price Index"),
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


def fetch_fred_series_history(series_id: str, api_key: str, limit: int = 24) -> list:
    """Returns list of (date_str, value) sorted desc, or [] on failure."""
    if not HAS_REQUESTS:
        return []
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
        result = []
        for o in obs:
            if o["value"] not in ("", ".", None):
                result.append((o["date"], float(o["value"])))
        return result
    except Exception as e:
        print(f"    [WARN] FRED history {series_id}: {e}")
    return []


def fetch_pce_yoy(api_key: str) -> tuple:
    """
    Compute Core PCE year-over-year % change from PCEPI price index.
    Returns (pce_yoy, date_str) or (None, None).
    PCEPI is a price index (base=100, 2017=100 by default).
    """
    history = fetch_fred_series_history("PCEPI", api_key, limit=15)
    if len(history) < 2:
        return None, None
    # history is sorted desc (newest first)
    latest = history[0]
    # Find value from ~12 months ago
    import datetime as dt
    try:
        latest_date = dt.datetime.strptime(latest[0], "%Y-%m-%d")
    except:
        return None, None
    target_year = latest_date.year - 1
    target_month = latest_date.month
    # Find closest date from 12 months prior
    target_str = f"{target_year}-{latest_date.month:02d}-01"
    prior = None
    for date_str, val in history:
        if date_str.startswith(target_str[:7]):
            prior = val
            break
    if prior is None:
        # fallback: use last available from prior year
        for date_str, val in history[12:]:
            prior = val
            break
    if prior is None or prior == 0:
        return None, None
    pce_yoy = round((latest[1] / prior - 1) * 100, 2)
    return pce_yoy, latest[0]


def calc_fiscal_index(debt_gdp: float, deficit_gdp_raw: float, interest_burden_raw: float) -> dict:
    """
    Fiscal Pressure Index (0-100).
    Components (老钱原文权重):
      - debt/gdp    : weight 40   → (debt-50)/100 * 40
      - deficit/gdp : weight 25   → (deficit-1)/9 * 25
      - interest burden : weight 35 → (interest-5)/15 * 35
    All sub-indices clamped 0-100.
    """
    d1 = max(0, min(40, max(0, (debt_gdp - 50) / 100 * 40))) if debt_gdp else 0
    d2 = max(0, min(25, max(0, (deficit_gdp_raw - 1) / 9 * 25))) if deficit_gdp_raw is not None else 0
    d3 = max(0, min(35, max(0, (interest_burden_raw - 5) / 15 * 35))) if interest_burden_raw is not None else 0
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


def fetch_sge_premium() -> dict:
    """
    Fetch Shanghai Gold Exchange Au9999 price and compute premium over COMEX.
    Returns {premium_pct, sge_cny, come_usd, fx_rate}.
    Uses AKShare as data source (fallback to None if unavailable).
    """
    try:
        import akshare as ak
        # SGE Au9999 price in CNY/gram
        sge = ak.sge_price()
        sge_gram = float(sge.iloc[0]['price'])  # CNY/gram
        # Convert to CNY/troy oz: 1 troy oz = 31.1035g
        sge_cny = round(sge_gram * 31.1035, 2)
        # Get USD/CNY rate
        usd_cny = ak.currency_usd_cny()
        fx = float(usd_cny.iloc[-1]['close'])
        # COMEX gold price from yfinance
        if HAS_YFINANCE:
            ticker = yf.Ticker("GC=F")
            hist = ticker.history(period="1d")
            if not hist.empty:
                come_usd = round(hist["Close"].iloc[-1], 2)
                # Premium = (SGE_CNY - COME_USD * FX) / (COME_USD * FX) * 100
                come_cny = come_usd * fx
                premium = round((sge_cny - come_cny) / come_cny * 100, 2)
                return {"premium_pct": premium, "sge_cny": sge_cny, "come_usd": come_usd, "fx_rate": fx}
    except Exception as e:
        print(f"    [WARN] SGE premium: {e}")
    return None


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
        # For annual series (FYFENDA, FYINT, GFDEGDQ188S), 30 obs ≈ 30 years back
        # For quarterly, 30 obs ≈ 7.5 years; for monthly, ≈ 2.5 years
        annual_limit = 30
        for key, (series_id, unit, name) in FRED_SERIES.items():
            val, date = fetch_fred_series(series_id, api_key, limit=annual_limit)
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
    # Fetch interest burden
    interest_burden_val = fred_data.get("interest_burden", {}).get("value")

    result["layers"] = {
        "4_institutional": {
            "debt_gdp":      fred_data.get("debt_gdp", {}).get("value"),
            "deficit_gdp":   fred_data.get("deficit_gdp", {}).get("value"),
            "debt_date":     fred_data.get("debt_gdp", {}).get("date"),
            "deficit_date":  fred_data.get("deficit_gdp", {}).get("date"),
            "interest_burden": interest_burden_val,
        },
        "3_macro": {
            "real_rate":       fred_data.get("real_rate", {}).get("value"),
            "inflation_exp":    fred_data.get("inflation_exp", {}).get("value"),
            "dxy":             fred_data.get("dxy", {}).get("value"),
            "financial_cond":  fred_data.get("financial_cond", {}).get("value"),
            "core_pce":        None,  # filled below via PCE YoY
            "unemployment":    fred_data.get("unemployment", {}).get("value"),
        },
        "2_market": {
            "gld_etf_flow": fetch_gld_holdings(),
        },
    }

    # ── PCE YoY (fix: PCEPI is price index, not %) ─────────────────────────
    if api_key:
        pce_yoy, pce_date = fetch_pce_yoy(api_key)
        if pce_yoy is not None:
            result["layers"]["3_macro"]["core_pce"] = pce_yoy
            print(f"    core_pce_yoy: {pce_yoy}% ({pce_date})")

    # ── Fiscal Pressure Index ───────────────────────────────────────────────
    debt_gdp = fred_data.get("debt_gdp", {}).get("value")
    deficit_gdp_raw = fred_data.get("deficit_gdp", {}).get("value")
    result["fiscal_index"] = calc_fiscal_index(debt_gdp, deficit_gdp_raw, interest_burden_val)
    result["fiscal_index"]["debt_gdp_raw"] = debt_gdp
    result["fiscal_index"]["deficit_gdp_raw"] = deficit_gdp_raw
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

    result["sge_premium"] = fetch_sge_premium()
    if result["sge_premium"]:
        print(f"    SGE premium: {result['sge_premium']['premium_pct']}% (SGE CNY={result['sge_premium']['sge_cny']})")

    # ── Write output ───────────────────────────────────────────────────────
    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[DONE] Gold board data → {OUTPUT}")


if __name__ == "__main__":
    main()
