#!/usr/bin/env python3
"""
Fetch investment indicators from FRED API.
Saves to data/indicators.json
"""
import json
import os
import requests
from datetime import datetime

# FRED API series codes
SERIES = {
    'SOFR': 'SOFR',           # Secured Overnight Financing Rate
    'TED': 'TEDRATE',         # TED Spread (will calculate as FRB spread)
    'DXY': 'DTWEXBGS',        # Trade Weighted USD Index
    'T10Y2Y': 'T10Y2Y',       # 10Y-2Y Treasury Yield Spread
    'WALCL': 'WALCL',         # Fed Total Assets (Weekly)
    'RRP': 'RRPONTSYD',       # Overnight Reverse Repo
    'TGA': 'WTREGEN',         # Treasury General Account
    'M2': 'M2SL',             # M2 Money Supply
}

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'indicators.json')

def get_fred_key():
    """Read FRED API key from env var (GitHub Actions) or macOS Keychain."""
    # Check env first (GitHub Actions)
    key = os.environ.get('FRED_API_KEY', '')
    if key:
        return key
    # Fallback to Keychain
    try:
        result = subprocess.run(
            ['security', 'find-generic-password', '-s', 'FRED API Key', '-w'],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    return ''

def get_fred_data(series_id):
    api_key = get_fred_key()
    if not api_key:
        print(f"[WARN] No FRED_API_KEY for {series_id}")
        return None
    
    url = f'https://api.stlouisfed.org/fred/series/observations'
    params = {
        'series_id': series_id,
        'api_key': api_key,
        'file_type': 'json',
        'limit': 1,  # Most recent only
        'sort_order': 'desc',
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        observations = data.get('observations', [])
        if observations:
            obs = observations[0]
            return {
                'date': obs['date'],
                'value': float(obs['value']) if obs['value'] != '.' else None
            }
    except Exception as e:
        print(f"[ERROR] {series_id}: {e}")
    return None

def main():
    print(f"[{datetime.now().isoformat()}] Fetching FRED data...")
    
    results = {}
    for name, series_id in SERIES.items():
        data = get_fred_data(series_id)
        if data:
            results[name] = data
            print(f"  {name}: {data['value']} ({data['date']})")
        else:
            print(f"  {name}: FAILED")
    
    # Calculate derived indicators
    # Net Liquidity = WALCL - RRP - TGA
    try:
        walcl = results.get('WALCL', {}).get('value')
        rrp = results.get('RRP', {}).get('value')
        tga = results.get('TGA', {}).get('value')
        if all(v is not None for v in [walcl, rrp, tga]):
            results['NetLiquidity'] = {
                'date': results['WALCL']['date'],
                'value': walcl - rrp - tga
            }
            print(f"  NetLiquidity: {results['NetLiquidity']['value']:.0f}")
    except Exception as e:
        print(f"[WARN] Could not calculate NetLiquidity: {e}")
    
    # Save
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump({
            'updated': datetime.now().isoformat(),
            'indicators': results
        }, f, indent=2)
    
    print(f"[DONE] Saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
