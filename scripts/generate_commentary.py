#!/usr/bin/env python3
"""
Generate AI commentary for investment indicators using MiniMax API.
Reads from data/indicators.json, writes commentary back.
"""
import json
import os
import requests
import subprocess
from datetime import datetime

INDICATORS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'indicators.json')
COMMENTARY_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'commentary.json')

def get_minimax_key():
    """Read MiniMax API key from macOS Keychain."""
    try:
        result = subprocess.run(
            ['security', 'find-generic-password', '-s', 'MiniMax CN API Key', '-w'],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        print(f"[WARN] Could not read Keychain: {e}")
    return os.environ.get('MINIMAX_API_KEY', '')

def generate_commentary(indicators):
    """Send indicators to MiniMax and get AI commentary."""
    api_key = get_minimax_key()
    if not api_key:
        print("[ERROR] No MINIMAX_API_KEY")
        return None
    
    # Build prompt
    lines = ["Today's Investment Indicators:\n"]
    for name, data in indicators.items():
        if data.get('value') is not None:
            lines.append(f"- {name}: {data['value']} ({data['date']})")
    
    prompt = '\n'.join(lines)
    prompt += "\n\nProvide a brief (2-3 sentence) market commentary on what these indicators suggest for risk appetite and liquidity conditions."
    
    # MiniMax API call
    url = 'https://api.minimaxi.com/v1/text/chatcompletion_v2'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': 'MiniMax-Text-01',
        'messages': [
            {'role': 'user', 'content': prompt}
        ],
        'max_tokens': 300,
        'temperature': 0.3,
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"[ERROR] MiniMax API: {e}")
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
                'source': 'MiniMax-Text-01'
            }, f, indent=2)
        
        print(f"[DONE] Saved to {COMMENTARY_FILE}")
    else:
        print("[WARN] No commentary generated")

if __name__ == '__main__':
    main()
