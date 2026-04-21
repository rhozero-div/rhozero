# GitHub-Pages Investment Dashboard

Investment indicator dashboard with AI commentary, hosted on GitHub Pages.

## Architecture

```
Data Collection (Python) → AI Commentary (MiniMax API) → Static HTML/JS → GitHub Pages
                                    ↑
                          GitHub Actions Cron
```

## Tech Stack

- **Hosting**: GitHub Pages (free)
- **Data**: Python scripts + FRED API
- **AI Commentary**: MiniMax API
- **Charts**: Chart.js
- **Automation**: GitHub Actions (scheduled cron)
- **Design**: Dark theme, responsive

## Project Structure

```
GitHub-Pages/
├── .github/
│   └── workflows/
│       └── update-dashboard.yml   # GitHub Actions cron job
├── scripts/
│   ├── fetch_data.py              # Fetch market indicators
│   ├── generate_commentary.py     # AI commentary via MiniMax
│   └── build_html.py              # Generate static HTML
├── docs/
│   └── index.html                 # Dashboard (GitHub Pages root)
├── data/
│   └── indicators.json            # Latest data snapshot
├── SKILL.md                       # Project skill (optional)
└── README.md
```

## GitHub Pages Setup

1. Create repo on GitHub: `your-username/GitHub-Pages`
2. Push this project
3. Settings → Pages → Source: `main` / `docs` folder
4. Wait for deployment (1-2 min)

## GitHub Actions Cron

Default schedule: `0 9 * * *` (daily 9 AM UTC)

Manual trigger: GitHub Actions → "Update Dashboard" → Run workflow

## Local Development

```bash
cd ~/Hermes/projects/GitHub-Pages
pip install -r requirements.txt
python scripts/fetch_data.py
python scripts/generate_commentary.py
python scripts/build_html.py
# Open docs/index.html in browser
```

## Indicators

- SOFR (Secured Overnight Financing Rate)
- TED Spread
- DXY Index
- 10Y-2Y Treasury Yield Spread
- Net Liquidity (WALCL - RRP - TGA)
- M2 Money Supply

## Status

🚧 In Progress - 2026-04-21
