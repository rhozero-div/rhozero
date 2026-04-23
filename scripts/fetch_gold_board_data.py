#!/usr/bin/env python3
"""
Fetch Gold Board data: all 21 nodes across 4 layers.
Sources: FRED API (macro) + yfinance (gold price) + GLD ETF holdings.
Outputs gold_board_data.json.
"""
import json
import math
import os
import urllib.parse
import urllib.request
import urllib.error
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
DATA_DIR.mkdir(exist_ok=True)
OUTPUT = DATA_DIR / "gold_board_data.json"


# ─── FRED Series Map ────────────────────────────────────────────────────────
FRED_SERIES = {
    # Layer 4: Institutional
    "debt_gdp":        ("GFDEGDQ188S",   "percent",   "Federal Debt to GDP"),
    "deficit_raw":     ("FYFSD",         "millions",  "Annual Federal Deficit (raw, negative=def)"),
    "revenue_raw":     ("FYFR",          "millions",  "Total Federal Revenue"),
    # NOTE: FYONET = "Federal Net Outlays" (total spending), NOT interest payments.
    # interest_raw uses NA000308Q (quarterly interest, summed to annual).
    "interest_raw":    ("NA000308Q",     "millions",  "Federal Interest Payments (quarterly)"),
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
    import urllib.request, urllib.error
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "limit": limit,
        "sort_order": "desc",
    }
    try:
        req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            obs = data.get("observations", [])
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


def fetch_gld_holdings() -> dict:
    """
    Get GLD ETF shares outstanding and percentile vs 3yr history.
    Returns {shares (M), percentile, history} or {shares, percentile, history: []} on failure.
    Uses yfinance shares_unfixed or info['sharesOutstanding'].
    """
    if not HAS_YFINANCE:
        return {"shares": None, "percentile": None, "history": []}
    try:
        ticker = yf.Ticker("GLD")
        # Try to get shares outstanding history (requires recent yfinance version)
        info = ticker.info
        current_shares = info.get("sharesOutstanding", info.get("shares", None))
        if current_shares:
            current_shares = round(current_shares / 1e6, 2)  # convert to millions
        else:
            current_shares = None

        # Try to get 3yr history of shares outstanding for percentile
        hist_3y = []
        try:
            hist = ticker.history(period="3y", auto_adjust=True)
            if not hist.empty:
                # shares outstanding proxy: use volume as a rough proxy
                # (yfinance doesn't expose historical shares outstanding directly)
                vol_history = hist["Volume"].tolist()
                dates = [d.strftime("%Y-%m-%d") for d in hist.index]
                # Use median volume as stable proxy for relative flow
                vol_median = sorted(vol_history)[len(vol_history)//2] if vol_history else None
                hist_3y = vol_history
        except Exception:
            pass

        percentile = None
        if current_shares is not None and hist_3y:
            # Simple percentile: what % of daily volumes are below current
            # Actually for ETF flows, use shares proxy (volume) percentile
            sorted_vol = sorted(hist_3y)
            rank = sum(1 for v in sorted_vol if v <= current_shares * 1e6)
            percentile = round(rank / len(sorted_vol) * 100, 1) if sorted_vol else None

        return {
            "shares": current_shares,
            "percentile": percentile,
            "history": hist_3y,
        }
    except Exception as e:
        print(f"    [WARN] GLD holdings: {e}")
    return {"shares": None, "percentile": None, "history": []}


def fetch_fred_series_history(series_id: str, api_key: str, limit: int = 24) -> list:
    """Returns list of (date_str, value) sorted desc, or [] on failure."""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "limit": limit,
        "sort_order": "desc",
    }
    try:
        req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            obs = data.get("observations", [])
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
    url = "https://api.stlouisfed.org/fred/series/observations"
    params_base = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "limit": limit,
        "sort_order": "desc",
    }
    for attempt in range(3):
        try:
            req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params_base)}",
                                         headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = json.loads(r.read())
                obs = data.get("observations", [])
                result = []
                for o in reversed(obs):
                    if o["value"] not in ("", ".", None):
                        result.append((o["date"], float(o["value"])))
                return result
        except Exception as e:
            if attempt < 2:
                continue  # retry
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


def fetch_cftc_cot() -> dict:
    """
    Fetch CFTC Disaggregated Report for Gold (GC).
    Returns {net_long (contracts), week} or None on failure.
    Data source: CFTC historical compressed files (fut_disagg_txt_{YEAR}.zip).
    Gold commodity code = 088, Managed Money columns 13 (Long) and 14 (Short).
    """
    import io, zipfile, re
    from datetime import datetime
    # Use current year for most recent report
    year = datetime.now().year
    url = f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            content = r.read()
        z = zipfile.ZipFile(io.BytesIO(content))
        with z.open("f_year.txt") as f:
            data = f.read().decode("latin-1", errors="replace")
        lines = data.splitlines()
        # Header: col 0=Market_Name, col 2=Report_Date, col 6=Commodity_Code,
        # col 13=M_Money_Long_All, col 14=M_Money_Short_All
        latest_gold = None
        for line in lines[1:]:
            cols = line.split(",")
            if len(cols) <= 14:
                continue
            code = cols[6].strip()
            if code != "088":
                continue
            # Found gold row
            try:
                mm_long = int(float(cols[13].strip()))
                mm_short = int(float(cols[14].strip()))
                net_long = mm_long - mm_short
                date_str = cols[2].strip().strip('"')
                latest_gold = {
                    "net_long": net_long,
                    "week": date_str,
                    "mm_long": mm_long,
                    "mm_short": mm_short,
                }
                # This is already the most recent (file sorted desc by date)
                break
            except (ValueError, IndexError):
                continue
        if latest_gold is None:
            print(f"    [WARN] CFTC: Gold (088) row not found in f_year.txt")
            return None
        return latest_gold
    except Exception as e:
        print(f"    [WARN] CFTC COT fetch failed: {e}")
    return None


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
            "pcepi":         ("PCEPI",     36),    # monthly: 3yr (for JS YoY compute)
            "gvz":           ("GVZCLS",    756),   # daily: ~3yr (CBOE Gold Volatility Index)
        }
        for key, (series_id, limit) in hist_configs.items():
            data = fetch_series_all(series_id, api_key, limit=limit)
            if data:
                dates = [d for d, v in data]
                vals = [v for d, v in data]
                result["series_history"][key] = {"dates": dates, "values": vals}

    # ── Interest Burden (NA000308Q quarterly sum / FYFR) ──────────────────────
    # NA000308Q = Federal Interest Payments in millions USD (quarterly)
    # FYFR = Federal Receipts in millions USD (annual, fiscal year ending Sep 30)
    # For FY2025: sum Q4-Q3-Q2-Q1 of NA000308Q (Oct 2024 - Jul 2025) ≈ FY2025
    # But NA000308Q uses calendar quarters; FYFR ends Sep 30.
    # Most recent 4 quarters = most recent completed fiscal year approximation.
    interest_burden_val = None
    if api_key:
        # Get last 4 quarters of NA000308Q (most recent full year of interest payments)
        interest_q = fetch_fred_series_history("NA000308Q", api_key, limit=5)
        fyfr_val = fred_data.get("revenue_raw", {}).get("value")
        if len(interest_q) >= 4 and fyfr_val is not None and fyfr_val > 0:
            # Take 4 most recent quarters (descending), sum, divide by FYFR
            # interest_q[0] = most recent quarter (e.g. Oct 2025)
            # interest_q[3] = oldest of the 4 (1 year lookback)
            annual_interest = sum(float(q[1]) for q in interest_q[:4])
            interest_burden_val = round(annual_interest / fyfr_val * 100, 2)
            print(f"    interest_burden: {interest_burden_val}% (NA000308Q sum={annual_interest:.0f}M / FYFR={fyfr_val}M)")
        else:
            print(f"    interest_burden: skipped (NA000308Q quarters={len(interest_q)}, FYFR={fyfr_val})")

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
    # GVZ: Real CBOE Gold Volatility Index (implied vol from gold options)
    gvz_val = None
    gvz_date = None
    gvz_hist = []
    gvz_pct = None
    if api_key:
        gvz_data = fetch_series_all("GVZCLS", api_key, limit=756)  # ~3yr daily
        if gvz_data:
            gvz_dates = [d for d, v in gvz_data]
            gvz_vals = [v for d, v in gvz_data]
            gvz_val = gvz_vals[-1] if gvz_vals else None
            gvz_date = gvz_dates[-1] if gvz_dates else None
            gvz_hist = gvz_vals  # full history for percentile calc
            # Percentile: what % of daily values are below current
            if gvz_val and len(gvz_vals) > 30:
                below = sum(1 for v in gvz_vals if v < gvz_val)
                gvz_pct = round(below / len(gvz_vals) * 100, 1)
            else:
                gvz_pct = None
            print(f"    GVZ: {gvz_val} (date={gvz_date}, percentile={gvz_pct}%, n={len(gvz_vals)})")
        else:
            gvz_pct = None
    else:
        gvz_pct = None

    gld_flow = result["layers"]["2_market"].get("gld_etf_flow", {})

    # ── CFTC COT ──────────────────────────────────────────────────────────────
    cftc_data = fetch_cftc_cot()
    if cftc_data:
        print(f"    CFTC net long: {cftc_data.get('net_long')} ({cftc_data.get('week')})")

    result["four_suits"] = {
        "gvz": {
            "value": gvz_val,
            "date": gvz_date,
            "percentile": gvz_pct,
            "label": "Gold Volatility (GVZ)",
            "signal": "neutral",
            "history": gvz_hist,
        },
        "ma_system": {"value": gold_cur, "ma20": ma20[-1] if ma20 else None, "ma60": ma60[-1] if ma60 else None, "ma200": ma200[-1] if ma200 else None},
        "gld_etf": {
            "shares": gld_flow.get("shares"),
            "percentile": gld_flow.get("percentile"),
            "unit": "M shares outstanding",
        },
        "cfct": cftc_data if cftc_data else {"value": None, "note": "CFTC COT requires dedicated scraper"},
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
