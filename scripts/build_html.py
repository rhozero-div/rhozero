#!/usr/bin/env python3
"""
Build static HTML dashboard from indicators + commentary.
Outputs to docs/index.html
"""
import json
import os
from datetime import datetime

INDICATORS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'indicators.json')
COMMENTARY_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'commentary.json')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'docs', 'index.html')

def load_data():
    indicators = {}
    commentary = None
    updated = None
    
    if os.path.exists(INDICATORS_FILE):
        with open(INDICATORS_FILE) as f:
            data = json.load(f)
            indicators = data.get('indicators', {})
            updated = data.get('updated')
    
    if os.path.exists(COMMENTARY_FILE):
        with open(COMMENTARY_FILE) as f:
            data = json.load(f)
            commentary = data.get('commentary')
    
    return indicators, commentary, updated

def build_html(indicators, commentary, updated):
    # Format indicator rows
    rows = []
    for name, data in indicators.items():
        value = data.get('value')
        date = data.get('date', 'N/A')
        if value is not None:
            if name in ['WALCL', 'TGA', 'NetLiquidity']:
                # Fed balance sheet items in billions
                display = f"${value/1000:.1f}B"
            elif name == 'RRP':
                # RRP in billions (FRED already in B)
                display = f"${value:.1f}B"
            elif name == 'M2':
                display = f"${value/1000:.1f}T"
            elif name in ['SOFR', 'T10Y2Y']:
                # Percent, show as bp for small values
                display = f"{value:.2f}% ({value*100:.0f}bp)"
            elif name == 'TED':
                # TED spread in bp (FRED TEDRATE is already in %, multiply by 100)
                display = f"{value:.2f}% ({value*100:.0f}bp)"
            else:
                display = f"{value:.2f}"
            rows.append(f"<tr><td>{name}</td><td>{display}</td><td>{date}</td></tr>")
    
    rows_html = '\n'.join(rows) if rows else '<tr><td colspan="3">No data</td></tr>'
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Investment Indicators Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg: #0d1117;
      --card: #161b22;
      --border: #30363d;
      --text: #e6edf3;
      --text-muted: #8b949e;
      --accent: #58a6ff;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
    .container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
    header {{ margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem; }}
    h1 {{ color: var(--accent); }}
    .updated {{ color: var(--text-muted); font-size: 0.875rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; }}
    h2 {{ font-size: 1rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1rem; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 0.75rem 0; border-bottom: 1px solid var(--border); }}
    th {{ color: var(--text-muted); font-weight: 500; }}
    .commentary {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; }}
    .commentary p {{ font-size: 1.1rem; }}
    .chart-container {{ height: 300px; }}
    footer {{ margin-top: 2rem; text-align: center; color: var(--text-muted); font-size: 0.75rem; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Investment Indicators</h1>
      <p class="updated">Last updated: {updated or 'Never'}</p>
    </header>
    
    <div class="grid">
      <div class="card">
        <h2>Current Values</h2>
        <table>
          <thead><tr><th>Indicator</th><th>Value</th><th>Date</th></tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>
      
      <div class="card">
        <h2>Charts</h2>
        <div class="chart-container">
          <canvas id="mainChart"></canvas>
        </div>
      </div>
    </div>
    
    <div class="commentary">
      <h2>AI Commentary</h2>
      <p>{commentary or 'Commentary generation failed. Check data.'}</p>
    </div>
    
    <footer>
      <p>Data sourced from FRED (Federal Reserve Economic Data) | AI commentary generated daily</p>
    </footer>
  </div>
  
  <script>
    // Placeholder chart - expand with historical data
    const ctx = document.getElementById('mainChart').getContext('2d');
    new Chart(ctx, {{
      type: 'line',
      data: {{ labels: [], datasets: [] }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ display: true, position: 'top' }} }},
        scales: {{ y: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#30363d' }} }}, x: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#30363d' }} }} }}
      }}
    }});
  </script>
</body>
</html>'''
    return html

def main():
    print(f"[{datetime.now().isoformat()}] Building HTML dashboard...")
    
    indicators, commentary, updated = load_data()
    
    if not indicators:
        print("[WARN] No indicators data found")
    
    html = build_html(indicators, commentary, updated)
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        f.write(html)
    
    print(f"[DONE] Written to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
