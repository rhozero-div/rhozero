#!/usr/bin/env python3
"""
Generate AI commentary for investment indicators.
Reads from data/indicators.json, writes commentary back.
"""
import json
import os
import requests
import subprocess
from datetime import datetime

INDICATORS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'indicators.json')
COMMENTARY_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'commentary.json')

# ── API Key (env var for CI, Keychain fallback for local) ─────────────────────
def _get_keychain_key(service: str) -> str:
    try:
        result = subprocess.run(
            ['security', 'find-generic-password', '-s', service, '-w'],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.stdout.strip() else ''
    except Exception:
        return ''

def get_minimax_key():
    """Read AI API key from env var (CI) or Keychain (local)."""
    # Env var (CI pipeline)
    api_key = os.environ.get('MINIMAX_API_KEY', '')
    if api_key:
        return api_key
    # Keychain fallback (local dev)
    return _get_keychain_key('AI Service Key')

def generate_commentary(indicators):
    """Send indicators to AI model and get commentary."""
    api_key = get_minimax_key()
    if not api_key:
        print("[ERROR] No API key configured")
        return None

    # Build prompt
    lines = ["Today's Investment Indicators:\n"]
    for name, data in indicators.items():
        if data.get('value') is not None:
            lines.append(f"- {name}: {data['value']} ({data['date']})")

    prompt = '\n'.join(lines)
    prompt += "\n\nProvide a brief (2-3 sentence) market commentary on what these indicators suggest for risk appetite and liquidity conditions."

    # API call (URL from env var)
    url = os.environ.get('AI_API_URL', 'https://api.minimaxi.com/v1/text/chatcompletion_v2')
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': 'MiniMax-M2.7',
        'messages': [
            {'role': 'user', 'content': prompt}
        ],
        'max_tokens': 2000,
        'temperature': 0.3,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        return result['choices'][0]['message'].get('content', '')
    except Exception as e:
        print(f"[ERROR] AI API call failed: {e}")
        return None

def main():
    print(f"[{datetime.now().isoformat()}] Generating AI commentary...")
    
    # Load indicators
    if not os.path.exists(INDICATORS_FILE):
        print(f"[ERROR] {INDICATORS_FILE} not found. Run fetch_data.py first.")
        return
    
    with open(INDICATORS_FILE) as f:
        data = json.load(f)
    
    indicators = data.get('indicators', {})
    
    # Generate commentary
    commentary = generate_commentary(indicators)
    
    if commentary:
        print(f"[COMMENTARY]\n{commentary}")
        
        # Save
        with open(COMMENTARY_FILE, 'w') as f:
            json.dump({
                'updated': datetime.now().isoformat(),
                'commentary': commentary,
                'source': 'AI-Text-01'
            }, f, indent=2)
        
        print(f"[DONE] Saved to {COMMENTARY_FILE}")
    else:
        print("[WARN] No commentary generated")

if __name__ == '__main__':
    main()
