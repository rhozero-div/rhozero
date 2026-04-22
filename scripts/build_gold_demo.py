#!/usr/bin/env python3
"""
Build the gold demo page: docs/demo/gold.html
Reads gold_data.json + gold_news.json → static HTML with Chart.js.
"""
import json
import os
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
GOLD_DATA_FILE = DATA_DIR / "gold_data.json"
GOLD_NEWS_FILE = DATA_DIR / "gold_news.json"
OUTPUT_FILE = SCRIPT_DIR.parent / "docs" / "demo" / "gold.html"


def calc_ma(prices, period=120):
    """Calculate 120-day moving average over price series."""
    result = []
    for i, p in enumerate(prices):
        if i < period - 1:
            result.append(None)
        else:
            window = prices[i - period + 1:i + 1]
            ma = sum(w["close"] for w in window) / period
            result.append(round(ma, 2))
    return result


def build_html(data, news, updated):
    prices = data.get("history", [])
    dates = [p["date"] for p in prices]
    closes = [p["close"] for p in prices]
    ma120 = calc_ma(prices, 120)

    # Format price history as JS array
    dates_js = json.dumps(dates)
    closes_js = json.dumps(closes)
    ma120_js = json.dumps(ma120)

    # News items
    news_items = news.get("articles", [])
    news_html = ""
    for n in news_items:
        source_tag = n["source"].upper().replace(".", "").replace("COM", "")[:10]
        news_html += f"""
        <a href="{n['url']}" target="_blank" rel="noopener" class="news-item">
          <div class="news-body">
            <div class="news-meta"><span class="news-source-tag">{source_tag}</span>{n['published'][:10]}</div>
            <div class="news-title">{n['title']}</div>
          </div>
        </a>"""

    # Current price display
    cp = data["current_price"]
    chg = data["change"]
    chg_pct = data["change_pct"]
    chg_sign = "+" if chg >= 0 else ""
    chg_color = "#4ade80" if chg >= 0 else "#f87171"

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gold Demo — RhoZero</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🥇</text></svg>">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
  <style>
    :root {{
      --bg: #0a0a0f;
      --card: #111118;
      --border: #1e1e2a;
      --text: #e0e0e0;
      --muted: #666;
      --accent: #f5c518;
      --up: #4ade80;
      --down: #f87171;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      line-height: 1.6;
      min-height: 100vh;
    }}
    a {{ color: inherit; text-decoration: none; }}

    /* ── Nav ── */
    nav {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 1rem 2rem;
      border-bottom: 1px solid var(--border);
    }}
    .nav-brand {{ font-size: 1rem; font-weight: 700; background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
    .nav-back {{ font-size: 0.8rem; color: var(--muted); }}
    .nav-back:hover {{ color: var(--accent); }}

    /* ── Hero ── */
    .hero {{
      padding: 2rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 1rem;
    }}
    .ticker-group {{}}
    .ticker-symbol {{ font-size: 1.5rem; font-weight: 700; color: var(--accent); }}
    .ticker-name {{ font-size: 0.85rem; color: var(--muted); }}
    .price-group {{ text-align: right; }}
    .price {{ font-size: 2.5rem; font-weight: 700; }}
    .change {{ font-size: 1rem; font-weight: 600; }}
    .updated {{ font-size: 0.75rem; color: var(--muted); margin-top: 0.25rem; }}

    /* ── Main layout ── */
    .layout {{
      display: grid;
      grid-template-columns: 1fr 340px;
      gap: 1px;
      background: var(--border);
      min-height: calc(100vh - 80px);
    }}
    @media (max-width: 768px) {{
      .layout {{ grid-template-columns: 1fr; }}
    }}

    /* ── Chart panel ── */
    .chart-panel {{
      background: var(--bg);
      padding: 1.5rem;
    }}
    .chart-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 1rem;
    }}
    .chart-title {{ font-size: 0.85rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }}
    .chart-legend {{
      display: flex;
      gap: 1rem;
      font-size: 0.75rem;
    }}
    .legend-item {{ display: flex; align-items: center; gap: 0.4rem; }}
    .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
    .chart-wrap {{ position: relative; height: 420px; }}

    /* ── News panel ── */
    .news-panel {{
      background: var(--card);
      padding: 1.5rem;
    }}
    .panel-title {{
      font-size: 0.85rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 1rem;
    }}
    .news-item {{
      display: flex;
      gap: 0.75rem;
      padding: 0.875rem 0;
      border-bottom: 1px solid var(--border);
      transition: border-color 0.2s;
    }}
    .news-item:last-child {{ border-bottom: none; }}
    .news-item:hover {{ border-color: var(--accent); }}
    .news-img {{
      width: 56px;
      height: 56px;
      border-radius: 6px;
      overflow: hidden;
      flex-shrink: 0;
      background: var(--border);
    }}
    .news-img img {{ width: 100%; height: 100%; object-fit: cover; }}
    .news-body {{ flex: 1; min-width: 0; }}
    .news-meta {{ font-size: 0.7rem; color: var(--muted); margin-bottom: 0.2rem; }}
    .news-title {{ font-size: 0.8rem; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}

    /* ── Footer ── */
    footer {{
      text-align: center;
      padding: 1.5rem;
      font-size: 0.7rem;
      color: #333;
      border-top: 1px solid var(--border);
    }}
    footer a {{ color: var(--muted); }}
  </style>
</head>
<body>
  <nav>
    <div class="nav-brand">RhoZero</div>
    <a href="../" class="nav-back">← Home</a>
  </nav>

  <div class="hero">
    <div class="ticker-group">
      <div class="ticker-symbol">GC=F</div>
      <div class="ticker-name">Gold Futures (USD/oz)</div>
    </div>
    <div class="price-group">
      <div class="price">${cp:,.2f}</div>
      <div class="change" style="color: {chg_color}">{chg_sign}{chg:,.2f} ({chg_sign}{chg_pct:.2f}%)</div>
      <div class="updated">Updated {updated}</div>
    </div>
  </div>

  <div class="layout">
    <div class="chart-panel">
      <div class="chart-header">
        <div class="chart-title">Daily Close · 2-Year</div>
        <div class="chart-legend">
          <div class="legend-item"><div class="legend-dot" style="background:#f5c518"></div>Gold</div>
          <div class="legend-item"><div class="legend-dot" style="background:#667eea"></div>120-Day MA</div>
        </div>
      </div>
      <div class="chart-wrap">
        <canvas id="goldChart"></canvas>
      </div>
    </div>

    <div class="news-panel">
      <div class="panel-title">Latest Gold News</div>
      {news_html if news_html else '<p style="color:var(--muted);font-size:0.8rem">No news available</p>'}
    </div>
  </div>

  <footer>
    Data via <a href="https://finance.yahoo.com" target="_blank">Yahoo Finance</a> ·
    News via <a href="https://www.gdeltproject.org" target="_blank">GDELT</a> ·
    Chart by <a href="https://www.chartjs.org" target="_blank">Chart.js</a> ·
    Updated daily by GitHub Actions
  </footer>

  <script>
    const dates = {dates_js};
    const closes = {closes_js};
    const ma120 = {ma120_js};

    const ctx = document.getElementById('goldChart').getContext('2d');

    // Gradient fill for gold line
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(245, 197, 24, 0.15)');
    gradient.addColorStop(1, 'rgba(245, 197, 24, 0)');

    new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: dates,
        datasets: [
          {{
            label: 'Gold',
            data: closes,
            borderColor: '#f5c518',
            borderWidth: 1.5,
            pointRadius: 0,
            pointHoverRadius: 5,
            pointHoverBackgroundColor: '#f5c518',
            fill: true,
            backgroundColor: gradient,
            tension: 0.1,
            order: 1
          }},
          {{
            label: '120-Day MA',
            data: ma120,
            borderColor: '#667eea',
            borderWidth: 1.5,
            pointRadius: 0,
            pointHoverRadius: 0,
            borderDash: [4, 4],
            fill: false,
            tension: 0.1,
            order: 0
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{
          mode: 'index',
          intersect: false,
        }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            backgroundColor: 'rgba(17, 17, 24, 0.95)',
            titleColor: '#e0e0e0',
            bodyColor: '#e0e0e0',
            borderColor: '#1e1e2a',
            borderWidth: 1,
            padding: 12,
            displayColors: true,
            callbacks: {{
              title: function(items) {{
                return items[0].label;
              }},
              label: function(ctx) {{
                if (ctx.datasetIndex === 0) {{
                  return 'Gold: $' + ctx.parsed.y.toLocaleString('en-US', {{minimumFractionDigits: 2}});
                }} else {{
                  return 'MA120: $' + (ctx.parsed.y != null ? ctx.parsed.y.toLocaleString('en-US', {{minimumFractionDigits: 2}}) : '—');
                }}
              }}
            }}
          }}
        }},
        scales: {{
          x: {{
            type: 'category',
            ticks: {{
              color: '#666',
              maxTicksLimit: 12,
              maxRotation: 0,
              font: {{ size: 11 }}
            }},
            grid: {{ color: '#1e1e2a' }}
          }},
          y: {{
            ticks: {{
              color: '#666',
              font: {{ size: 11 }},
              callback: val => '$' + val.toLocaleString()
            }},
            grid: {{ color: '#1e1e2a' }}
          }}
        }}
      }}
    }});
  </script>
</body>
</html>'''
    return html


def main():
    print(f"[{datetime.now().isoformat()}] Building gold demo page...")

    data = {"history": [], "current_price": 0, "change": 0, "change_pct": 0, "last_updated": "Never"}
    news = {"articles": []}
    updated = "Never"

    if GOLD_DATA_FILE.exists():
        with open(GOLD_DATA_FILE) as f:
            data = json.load(f)
            updated = data.get("last_updated", "Unknown")
            print(f"  ✓ Loaded gold_data.json: {len(data.get('history', []))} days")

    if GOLD_NEWS_FILE.exists():
        with open(GOLD_NEWS_FILE) as f:
            news = json.load(f)
            print(f"  ✓ Loaded gold_news.json: {len(news.get('articles', []))} articles")

    html = build_html(data, news, updated)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    print(f"[DONE] Written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
