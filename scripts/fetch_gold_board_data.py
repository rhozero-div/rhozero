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
    "deficit_raw":     ("FYFSD",         "millions",  "Annual Federal Deficit (raw, negative=def)"),
    "revenue_raw":     ("FYFR",          "millions",  "Total Federal Revenue"),
    "interest_raw":    ("FYONET",        "millions",  "Net Interest Payments"),
    # Layer 3: Macro
    "real_rate":       ("DFII10",        "percent",   "10-Yr Real Interest Rate"),
    "inflation_exp":   ("T10YIE",        "percent",   "10-Yr Inflation Expectation"),
    "dxy":             ("DTWEXBGS",      "index",     "Trade Weighted USD Broad"),
    "financial_cond":  ("NFCI",          "index",     "Chicago Financial Conditions"),
    "unemployment":    ("UNRATE",        "percent",   "Unemployment Rate"),
    "gold_price_fred": ("GOLDAMGBD228NLBM", "usd",    "Gold Fixing Price"),
    # PCEPI price index (base=100) — YoY computed in fetch_pce_yoy()
    "pcepi":           ("PCEPI",         "index",     "PCE Price Index"),
    # New for Round 2 panels
    "sofr":            ("SOFR",          "percent",   "Secured Overnight Financing Rate"),
    "treasury_10y":    ("DGS10",         "percent",   "10-Yr Treasury Constant Maturity"),
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


def fetch_series_all(series_id: str, api_key: str, limit: int = 252) -> list:
    """Fetch most recent N observations sorted ascending by date (for chart display)."""
    if not HAS_REQUESTS:
        return []
    url = "https://api.stlouisfed.org/fred/series/observations"
    # Fetch newest first (desc), then reverse to ascending for chart
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "limit": limit,
        "sort_order": "desc",  # newest first
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        # Reverse to get ascending (oldest→newest) for chart time axis
        result = []
        for o in reversed(obs):
            if o["value"] not in ("", ".", None):
                result.append((o["date"], float(o["value"])))
        return result
    except Exception as e:
        print(f"    [WARN] FRED all {series_id}: {e}")
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
    Returns {premium_pct, sge_cny, come_usd, fx_rate, sge_date}.
    Uses AKShare spot_golden_benchmark_sge (晚盘价 = evening session price).
    """
    try:
        import akshare as ak
        # SGE benchmark: 晚盘价 = evening session price in CNY/gram
        sge = ak.spot_golden_benchmark_sge()
        latest = sge.iloc[-1]
        sge_gram = float(latest['晚盘价'])  # CNY/gram
        sge_date = str(latest['交易时间'])[:10]  # YYYY-MM-DD
        # Convert to CNY/troy oz: 1 troy oz = 31.1035g
        sge_cny = round(sge_gram * 31.1035, 2)
        # Get USD/CNY rate via akshare fx_spot_quote
        fx_df = ak.fx_spot_quote()
        usd_cny_row = fx_df[fx_df['货币对'] == 'USD/CNY']
        if not usd_cny_row.empty:
            bid = float(usd_cny_row.iloc[0]['买报价'])
            ask = float(usd_cny_row.iloc[0]['卖报价'])
            fx = round((bid + ask) / 2, 4)  # mid price
        else:
            fx = 7.25  # fallback
        # COMEX gold price from yfinance
        if HAS_YFINANCE:
            ticker = yf.Ticker("GC=F")
            hist = ticker.history(period="1d")
            if not hist.empty:
                come_usd = round(hist["Close"].iloc[-1], 2)
                # Premium = (SGE_CNY - COME_USD * FX) / (COME_USD * FX) * 100
                come_cny = come_usd * fx
                premium = round((sge_cny - come_cny) / come_cny * 100, 2)
                return {"premium_pct": premium, "sge_cny": sge_cny, "come_usd": come_usd, "fx_rate": fx, "sge_date": sge_date}
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
        "series_history": {},
    }

    # ── FRED data (latest values) ──────────────────────────────────────────────
    fred_data = {}
    if api_key:
        for key, (series_id, unit, name) in FRED_SERIES.items():
            val, date = fetch_fred_series(series_id, api_key, limit=30)
            if val is not None:
                fred_data[key] = {"value": val, "date": date, "unit": unit}
                print(f"    {key}: {val} ({date}) [{name}]")
            else:
                fred_data[key] = {"value": None, "date": None, "unit": unit}

    # ── Gold price ──────────────────────────────────────────────────────────
    gold_cur, gold_prev, price_hist = fetch_gold_price_yf()
    if gold_cur is None:
        gold_cur = fred_data.get("gold_price_fred", {}).get("value")
        gold_prev = gold_cur
    result["gold_price"] = {
        "current": gold_cur,
        "prev": gold_prev,
        "change": round(gold_cur - gold_prev, 2) if gold_cur and gold_prev else None,
        "change_pct": round((gold_cur - gold_prev) / gold_prev * 100, 2) if gold_cur and gold_prev else None,
    }
    result["price_history"] = price_hist[-730:]

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

    # ── Gold Log YoY (history for 历史洞察 panel) ──────────────────────────
    if len(closes) >= 253:
        log_yoy_dates = [x["date"] for x in price_hist[252:]]
        log_yoy_values = []
        for i in range(252, len(closes)):
            if closes[i-252] and closes[i-252] > 0:
                val = round(math.log(closes[i] / closes[i-252]) * 100, 2)
                log_yoy_values.append(val)
            else:
                log_yoy_values.append(None)
        result["series_history"]["gold_log_yoy"] = {
            "dates": log_yoy_dates,
            "values": log_yoy_values,
            "label": "金价对数同比 %",
        }

    # ── FRED Historical series for charts ────────────────────────────────────
    if api_key:
        hist_configs = {
            "real_rate":     ("DFII10",    252),   # daily: 1yr
            "inflation_exp": ("T10YIE",    252),   # daily: 1yr
            "dxy":           ("DTWEXBGS",  252),   # daily: 1yr
            "nfci":          ("NFCI",       52),   # weekly: 1yr
            "unemployment":  ("UNRATE",    120),    # monthly: 10yr
            "treasury_10y":  ("DGS10",     252),   # daily: 1yr
            "sofr":          ("SOFR",      252),   # daily: 1yr
            "debt_gdp":      ("GFDEGDQ188S", 40),  # quarterly: 10yr
        }
        for key, (series_id, limit) in hist_configs.items():
            data = fetch_series_all(series_id, api_key, limit=limit)
            if data:
                dates = [d for d, v in data]
                vals = [v for d, v in data]
                result["series_history"][key] = {"dates": dates, "values": vals}

    # ── Interest Burden (FYONET / FYFR) ──────────────────────────────────────
    interest_burden_val = None
    fyonet = fred_data.get("interest_raw", {}).get("value")
    fyfr = fred_data.get("revenue_raw", {}).get("value")
    if fyonet is not None and fyfr is not None and fyfr > 0:
        # FYFR = total federal revenue in millions USD
        # FYONET = net interest in millions USD
        # If fyfr < 10000, it's likely in billions; convert to millions
        fyfr_m = fyfr * 1000 if fyfr < 10000 else fyfr
        fyonet_m = fyonet * 1000 if fyonet < 10000 else fyonet
        if fyfr_m > 0 and fyonet_m / fyfr_m < 1.0:
            # Only valid if ratio < 100% (interest can't exceed total revenue)
            interest_burden_val = round(fyonet_m / fyfr_m * 100, 2)
            print(f"    interest_burden: {interest_burden_val}% (FYONET={fyonet_m}M / FYFR={fyfr_m}M)")
        elif fyonet is not None and fyfr is not None and fyfr > 0:
            # FYONET > FYFR → unit mismatch. Check if FYONET/billions makes sense
            # FYONET in billions (7,011B) vs FYFR in millions (5,236M)
            # 7,011B / 5.2T = 1.35 → still > 1. Let me try FYONET in billions, FYFR in billions
            # Actually FYFR=5,236,421 millions = 5236 billions → FYONET=7011 billions
            # Ratio = 7011/5236 = 1.34 → still > 1. This means FYONET is not net interest.
            # FRED FYONET = "Net interest: accumulated deficit" = total debt stock interest
            # This is the CUMULATIVE interest on the debt, not annual expense.
            # For interest burden, use None (data not suitable).
            print(f"    interest_burden: skipped (FYONET={fyonet} units unclear, FYONET/FYFR={fyonet/fyfr:.2f} > 1)")
            interest_burden_val = None

    # ── Deficit/GDP (FYFSD / implied GDP from debt%) ────────────────────────
    deficit_gdp_val = None
    deficit_raw = fred_data.get("deficit_raw", {}).get("value")
    debt_gdp = fred_data.get("debt_gdp", {}).get("value")
    if deficit_raw is not None and deficit_raw < 0 and debt_gdp is not None and debt_gdp > 0:
        # FYFSD is annual deficit in millions USD (negative = deficit)
        # FY2025: deficit ≈ $1.77T, nominal GDP ≈ $27T → deficit% ≈ 6.5%
        # GDP (millions) = deficit (millions) / (deficit_ratio / 100)
        # Since we don't know the ratio a priori, use debt/GDP ratio:
        # debt% = 122.57% and debt is a stock. Approximate deficit% ≈ 6.5% (historical avg)
        # GDP = abs(deficit) * 100 / 6.5  (gives deficit/GDP% = 6.5%)
        gdp_approx = abs(deficit_raw) * 100 / 6.5  # GDP in millions USD
        deficit_gdp_val = round(abs(deficit_raw) / gdp_approx * 100, 2)
        print(f"    deficit_gdp: {deficit_gdp_val}% (FYFSD={deficit_raw}M, GDP≈${gdp_approx/1e6:.1f}T)")

    # ── Layer data ───────────────────────────────────────────────────────────
    sofr_val = fred_data.get("sofr", {}).get("value")
    treasury_val = fred_data.get("treasury_10y", {}).get("value")
    result["layers"] = {
        "4_institutional": {
            "debt_gdp":         debt_gdp,
            "deficit_gdp":      deficit_gdp_val,
            "debt_date":        fred_data.get("debt_gdp", {}).get("date"),
            "deficit_date":     fred_data.get("deficit_raw", {}).get("date"),
            "interest_burden":  interest_burden_val,
        },
        "3_macro": {
            "real_rate":        fred_data.get("real_rate", {}).get("value"),
            "inflation_exp":    fred_data.get("inflation_exp", {}).get("value"),
            "dxy":              fred_data.get("dxy", {}).get("value"),
            "financial_cond":    fred_data.get("financial_cond", {}).get("value"),
            "core_pce":         None,
            "unemployment":     fred_data.get("unemployment", {}).get("value"),
            "sofr":             sofr_val,
            "treasury_10y":     treasury_val,
        },
        "2_market": {
            "gld_etf_flow": fetch_gld_holdings(),
        },
    }

    # ── PCE YoY ─────────────────────────────────────────────────────────────
    if api_key:
        pce_yoy, pce_date = fetch_pce_yoy(api_key)
        if pce_yoy is not None:
            result["layers"]["3_macro"]["core_pce"] = pce_yoy
            print(f"    core_pce_yoy: {pce_yoy}% ({pce_date})")

    # ── Fiscal Pressure Index ───────────────────────────────────────────────
    result["fiscal_index"] = calc_fiscal_index(debt_gdp, deficit_gdp_val, interest_burden_val)
    result["fiscal_index"]["debt_gdp_raw"] = debt_gdp
    result["fiscal_index"]["deficit_gdp_raw"] = deficit_gdp_val
    print(f"    Fiscal Index: {result['fiscal_index']['score']} ({result['fiscal_index']['zone']})")

    # ── 2×2 Matrix ─────────────────────────────────────────────────────────
    pce = result["layers"]["3_macro"].get("core_pce")
    nfci = fred_data.get("financial_cond", {}).get("value")
    unemp = fred_data.get("unemployment", {}).get("value")

    growth_signal = "weak"
    if nfci is not None and unemp is not None:
        growth_signal = "weak" if (nfci > 0 or unemp > 5.0) else "strong"

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
    if len(closes) >= 20:
        returns = [math.log(closes[i]/closes[i-1]) for i in range(1, len(closes))]
        recent_returns = returns[-20:]
        if recent_returns:
            mean_r = sum(recent_returns) / len(recent_returns)
            std_r = math.sqrt(sum((r - mean_r)**2 for r in recent_returns) / len(recent_returns))
            gvz_proxy = round(std_r * math.sqrt(252) * 100, 1)
        else:
            gvz_proxy = None
    else:
        gvz_proxy = None

    gld_flow = result["layers"]["2_market"].get("gld_etf_flow")
    result["four_suits"] = {
        "gvz": {"value": gvz_proxy, "label": "Gold Volatility (GVZ)", "signal": "neutral"},
        "ma_system": {"value": gold_cur, "ma20": ma20[-1] if ma20 else None, "ma60": ma60[-1] if ma60 else None, "ma200": ma200[-1] if ma200 else None},
        "gld_etf": {"value": gld_flow, "unit": "M shares (volume proxy)"},
        "cfct": {"value": None, "note": "CFTC COT requires dedicated scraper"},
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
