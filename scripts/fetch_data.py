#!/usr/bin/env python3
"""
Fetch FRED data for Dollar Liquidity weekly report.
Writes full time-series to data/liquidity_history.csv
"""
import os
import json
import time
import csv
import requests
from datetime import datetime, timedelta
from pathlib import Path

# ── FRED API Key ──────────────────────────────────────────────────────────────
def get_fred_key():
    key = os.environ.get('FRED_API_KEY', '')
    if key:
        return key
    try:
        import subprocess
        r = subprocess.run(
            ['security', 'find-generic-password', '-s', 'FRED API Key', '-w'],
            capture_output=True, text=True, timeout=5
        )
        if r.stdout.strip():
            return r.stdout.strip()
    except:
        pass
    return ''

FRED_KEY = get_fred_key()
BASE_URL = "https://api.stlouisfed.org/fred"

# ── FRED series codes ────────────────────────────────────────────────────────
PRIMARY = {
    "SOFR":      "SOFR",       #担保隔夜融资利率（日度）
    "TEDRATE":   "TEDRATE",    #TED利差（已停用，以SOFR-DFF替代）
    "RRPONTTLD": "RRPONTTLD", #隔夜逆回购余额（日度）
    "WTREGEN":   "WTREGEN",   #财政部一般账户TGA（周度）
    "WALCL":     "WALCL",     #美联储总资产（周度）
    "FEDFUNDS":  "FEDFUNDS",  #联邦基金利率（月度参考）
    "DFF":       "DFF",       #有效联邦基金利率（日度）
}
SECONDARY = {
    "T10Y2Y":    "T10Y2Y",    #10年-2年国债利差
    "DTWEXBGS":  "DTWEXBGS",  #贸易加权美元指数Broad
    "M2SL":      "M2SL",     #M2货币供应量（月度）
}
ALL_SERIES = {**PRIMARY, **SECONDARY}

SCRIPT_DIR = Path(__file__).parent
DATA_DIR   = SCRIPT_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def fred_get_series(series_id: str, obs_start: str = None) -> list:
    """Fetch series from FRED, return [(date, value)]"""
    url = f"{BASE_URL}/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_KEY,
        "file_type": "json",
        "observation_start": obs_start or (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d"),
        "units": "lin",
    }
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            observations = data.get("observations", [])
            return [(obs["date"], float(obs["value"]))
                    for obs in observations if obs["value"] != "."]
        except Exception as e:
            print(f"  [{series_id}] failed ({attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return []

def fetch_all():
    import concurrent.futures
    start = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fred_get_series, code, start): code
                   for code in ALL_SERIES}
        for future in concurrent.futures.as_completed(futures):
            code = futures[future]
            try:
                data = future.result()
                results[code] = data
                print(f"  ✓ {code}: {len(data)} obs")
            except Exception as e:
                print(f"  ✗ {code}: {e}")
                results[code] = []
    return results

def latest_value(series: list):
    for date, val in reversed(series):
        if val is not None:
            return date, val
    return None, None

def get_value_on_date(series: list, target_date: str) -> float:
    td = datetime.strptime(target_date, "%Y-%m-%d")
    for i in range(8):
        check = (td - timedelta(days=i)).strftime("%Y-%m-%d")
        for d, v in series:
            if d == check:
                return v
    return None

def compute_sofr_spread(sofr: list, fedfunds: list) -> list:
    dates_vals = {}
    for d, v in sofr:
        dates_vals.setdefault(d, {})["SOFR"] = v
    for d, v in fedfunds:
        dates_vals.setdefault(d, {})["DFF"] = v
    result = []
    for date in sorted(dates_vals.keys()):
        vals = dates_vals[date]
        if "SOFR" in vals and "DFF" in vals:
            spread = vals["SOFR"] - vals["DFF"]
            result.append((date, spread))
    return result

def compute_net_liquidity(walcl: list, tga: list, rrp: list) -> list:
    dates_vals = {}
    for d, v in walcl:
        dates_vals.setdefault(d, {})["WALCL"] = v
    for d, v in tga:
        dates_vals.setdefault(d, {})["TGA"] = v
    for d, v in rrp:
        dates_vals.setdefault(d, {})["RRP"] = v
    result = []
    for date in sorted(dates_vals.keys()):
        vals = dates_vals[date]
        if all(k in vals for k in ("WALCL", "TGA", "RRP")):
            net = vals["WALCL"] - vals["TGA"] - vals["RRP"]
            result.append((date, net))
    return result

def compute_m2_yoy(m2_series: list) -> list:
    if not m2_series:
        return []
    by_month = {}
    for d, v in m2_series:
        mo = d[:7]
        by_month[mo] = v
    yoy = []
    sorted_months = sorted(by_month.keys())
    for i, mo in enumerate(sorted_months):
        if i < 12:
            continue
        prev_mo = sorted_months[i - 12]
        curr = by_month[mo]
        prev = by_month[prev_mo]
        if prev and prev != 0:
            pct = (curr - prev) / prev * 100
            yoy.append((mo + "-28", pct))
    return yoy

def compute_walcl_yoy(walcl_series: list) -> list:
    if not walcl_series:
        return []
    by_week = {}
    for d, v in walcl_series:
        dt = datetime.strptime(d, "%Y-%m-%d")
        wk = dt.strftime("%Y-W%W")
        by_week[wk] = (d, v)
    sorted_weeks = sorted(by_week.keys())
    yoy = []
    for i, wk in enumerate(sorted_weeks):
        if i < 52:
            continue
        prev_wk = sorted_weeks[i - 52]
        curr_date, curr = by_week[wk]
        prev_date, prev = by_week[prev_wk]
        if prev and prev != 0:
            pct = (curr - prev) / prev * 100
            yoy.append((curr_date, pct))
    return yoy

def save_csv(series_dict: dict, path: Path):
    all_dates = set()
    for s in series_dict.values():
        for d, _ in s:
            all_dates.add(d)
    all_dates = sorted(all_dates)

    sofr_spread = compute_sofr_spread(series_dict.get("SOFR", []),
                                       series_dict.get("FEDFUNDS", []))
    net_liq     = compute_net_liquidity(
        series_dict.get("WALCL", []),
        series_dict.get("WTREGEN", []),
        series_dict.get("RRPONTTLD", [])
    )
    m2_yoy      = compute_m2_yoy(series_dict.get("M2SL", []))
    walcl_yoy   = compute_walcl_yoy(series_dict.get("WALCL", []))

    derived = {
        "SOFR_Spread": sofr_spread,
        "Net_Liquidity": net_liq,
        "M2_YoY": m2_yoy,
        "WALCL_YoY": walcl_yoy,
    }

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        headers = ["date"] + list(ALL_SERIES.keys()) + list(derived.keys())
        writer.writerow(headers)
        for date in all_dates:
            row = [date]
            for code in ALL_SERIES:
                v = get_value_on_date(series_dict.get(code, []), date)
                row.append(f"{v:.4f}" if v is not None else "")
            for name in derived:
                v = get_value_on_date(derived[name], date)
                row.append(f"{v:.4f}" if v is not None else "")
            writer.writerow(row)
    print(f"  CSV saved: {path}")

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] FRED fetch start...")
    data = fetch_all()
    save_csv(data, DATA_DIR / "liquidity_history.csv")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Done.")
