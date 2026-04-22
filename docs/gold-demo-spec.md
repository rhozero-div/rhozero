# Gold Demo Page — Implementation Spec

> Status: ✅ Live at https://rhozero-div.github.io/rhozero/demo/gold.html

## Architecture

```
GitHub Actions (daily 9 AM UTC)
├── fetch_gold_data.py   → yfinance GC=F → data/gold_data.json
├── fetch_gold_news.py    → RSS (Gold Eagle + Mining.com) → data/gold_news.json
└── build_gold_demo.py    → docs/demo/gold.html (Chart.js + news)
                              ↓
                     GitHub Pages (auto-deploy)
                              ↓
                     Browser (pure static, no JS polling)
```

## Data Sources

### Price Data
- **Source**: Yahoo Finance via `yfinance` (Python)
- **Ticker**: GC=F (Gold Futures, USD/oz)
- **History**: 2 years daily OHLCV
- **Note**: 15-20 min delay (free tier), not real-time

### News
- **Source**: RSS feeds (Gold Eagle + Mining.com)
- **Filter**: Strict gold keywords (gold, precious metal, gold mining...) + exclude (oil, copper, lithium...)
- **Count**: Top 5 articles sorted by date
- **Fallback**: Hardcoded articles if all feeds fail

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Price data | yfinance (Python) | Free, no API key, 2y history |
| News | feedparser + requests | RSS, no API key |
| Charts | Chart.js 4.4 (CDN) | Interactive tooltips, no build step |
| Styling | Vanilla CSS (CSS vars) | No framework, dark/light theme via vars |
| Hosting | GitHub Pages | Free, auto-deploy from `docs/` |

## Design

- **Theme**: Warm cream (`#f5f0e8`) — not dark
- **Chart**: Gold line + 120-day MA dashed line, hover tooltip with date/price/MA
- **News**: Left gold border on hover, source tag badge, no thumbnails
- **Color palette**:
  - `--accent`: `#c4922a` (gold)
  - `--up`: `#2d8a4e` (green)
  - `--down`: `#c0392b` (red)

## File Structure

```
GitHub-Pages/
├── scripts/
│   ├── fetch_gold_data.py    # yfinance → gold_data.json
│   ├── fetch_gold_news.py    # RSS → gold_news.json
│   └── build_gold_demo.py    # JSON → gold.html
├── docs/
│   ├── index.html            # Homepage with demo link
│   └── demo/
│       └── gold.html         # The demo page (generated)
├── data/                     # GitHub Actions output (git-ignored)
│   ├── gold_data.json
│   └── gold_news.json
└── .github/workflows/
    └── update-dashboard.yml  # Daily cron: fetch → build → push
```

## Limitations

1. **No real-time price** — GitHub Pages is pure static, cannot poll APIs from browser
2. **Price delay** — Yahoo Finance futures data ~15-20 min delayed (free tier)
3. **News delay** — Updated daily only (GitHub Actions cron minimum = 1 min, but wasteful)
4. **AI commentary** — Not included (requires Cloudflare Worker or HF Spaces)

## For New Assets

To add a new asset (e.g., Bitcoin, SPY):

1. Copy `fetch_gold_data.py` → `fetch_btc_data.py`, change ticker to `BTC-USD`
2. Copy `fetch_gold_news.py` → `fetch_btc_news.py`, update RSS URLs and keywords
3. Copy `build_gold_demo.py` → `build_btc_demo.py`, update data file paths
4. Add to `update-dashboard.yml` workflow
5. Add link to `docs/index.html`

## RSS Feeds Tested

| Feed | URL | Status |
|------|-----|--------|
| Gold Eagle | https://www.gold-eagle.com/rss.xml | ✅ Works |
| Mining.com | https://www.mining.com/feed/ | ✅ Works |
| Bloomberg | https://feeds.bloomberg.com/markets/news.rss | ✅ Works (strict filter needed) |
| Kitco | https://www.kitco.com/news/rss/ | ❌ 0 entries |
| GDELT | api.gdeltproject.org | ❌ Timeout / bad URLs |
| Reuters | feeds.reuters.com | ❌ SSL error |
