# GitHub-Pages Investment Dashboard

Investment indicator dashboard + automated weekly report, hosted on GitHub Pages.

**Live**: https://rhozero-div.github.io/rhozero/

## Architecture

```
Daily:  FRED API → fetch_data.py → generate_commentary.py (AI) → build_html.py → GitHub Pages
Weekly: FRED API → fetch_data.py → run_weekly_github.py (full report, no AI) → GitHub Pages
                                          ↑
                              GitHub Actions Cron (both workflows)
```

**关键决策：无 AI 版周报可完全在 GitHub Actions 跑通，不依赖本地。**

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Hosting | GitHub Pages (free) | 静态托管，无成本 |
| Daily AI | AI API (env var configured in GitHub Secrets) | 免费额度，GitHub Secrets 存储 |
| Weekly AI | 无（规则模板） | 无需实时解读，硬编码评级足够 |
| Charts | matplotlib (服务器端 PNG) | 不依赖前端 JS，SEO 友好 |
| Automation | GitHub Actions cron | 免费、免维护、可手动触发 |

## Project Structure

```
GitHub-Pages/
├── .github/
│   └── workflows/
│       ├── update-dashboard.yml    # Daily cron: fetch + AI commentary + dashboard
│       └── weekly-report.yml       # Weekly cron: fetch + full report (Mon 10 AM UTC)
├── scripts/
│   ├── fetch_data.py               # FRED 730-day history → liquidity_history.csv
│   ├── generate_commentary.py     # Daily AI commentary
│   ├── build_html.py               # Daily dashboard HTML (Chart.js)
│   └── run_weekly_github.py         # Weekly report: ratings + charts + HTML + appendix
├── docs/
│   ├── index.html                  # Landing page (Under Construction → links to sub-pages)
│   ├── implementation/
│   │   └── index.html             # Daily dashboard (Chart.js + AI commentary)
│   └── dollar-liquidity-weekly-report/
│       ├── index.html              # Weekly report listing
│       ├── 20260421.html           # Individual report
│       └── charts/                 # Shared chart PNGs (regenerated weekly)
└── data/
    └── liquidity_history.csv       # 730-day FRED data (git-tracked)
```

## Lessons Learned (经验总结)

### 1. 数据层分离
- `fetch_data.py` 负责从 FRED 拉数据写 CSV（730 天历史，供周报用）
- 日报只拉最新值（limit=1），周报用完整历史
- CSV 必须 git-tracked，否则 GitHub Actions 无法访问历史

### 2. 路径设计
- **输出路径**：所有产出直接写到 `docs/`，GitHub Pages 自动托管
- **图表路径**：`charts/` 放共享目录，每次覆盖；不要按日期分目录（增加引用复杂度）
- **子目录命名**：用 kebab-case（`dollar-liquidity-weekly-report`），URL 友好

### 3. 无 AI 周报全自动化
```
原 run_weekly_report.py（dollar-liquidity-theory）
  → 依赖 STHeiti 字体（macOS）、Keychain、FRED key 本地读取 → 无法在 GitHub Actions 跑

解决方案：重写 run_weekly_github.py
  → 去掉：STHeiti / Keychain / PDF 生成 / macOS 依赖
  → 保留：评级函数 + 图表生成 + content.json → HTML
  → 路径：env var 取 FRED key → data/liquidity_history.csv → 输出到 docs/
```

### 4. AI 走云端还是本地
- 日报 AI：在 GitHub Actions 里调用 API 生成英文点评，写入 `commentary.json`，`build_html.py` 读取
- 周报无 AI：纯规则模板，完全批处理，最稳定
- **判断标准**：是否需要实时/个性化解读？周报是结构化报告，规则足够

### 5. API Key 管理
- API keys 存 GitHub Secrets → Actions 里通过环境变量注入，脚本不直接读取
- API keys 同理
- 本地跑时：环境变量优先，回退 Keychain（`os.environ.get()` → `security find-generic-password`）

### 6. L_NAMES 前缀重复 bug
- 症状：`L_NAMES = {1: "L1 充裕", ...}` → 代码拼了 `L{r}` → 显示 `L1 L1 充裕`
- 修复：`L_NAMES = {1: "充裕", ...}` 前缀由调用方统一加

## GitHub Pages Setup

```bash
# 1. Create repo
gh repo create rhozero-div/rhozero --public --source=. --push

# 2. Settings → Pages → Source: main / docs
#    → URL: https://rhozero-div.github.io/rhozero/

# 3. Add secrets
gh secret set FRED_API_KEY   # FRED API key
gh secret set MINIMAX_API_KEY  # MiniMax API key (optional, for daily AI)
```

## Local Development

```bash
cd ~/Hermes/projects/GitHub-Pages
pip install -r requirements.txt   # pandas matplotlib requests

# Daily dashboard
FRED_API_KEY=xxx MINIMAX_API_KEY=xxx python scripts/fetch_data.py
python scripts/generate_commentary.py
python scripts/build_html.py

# Weekly report (no API keys needed if using env vars)
FRED_API_KEY=xxx python scripts/fetch_data.py
python scripts/run_weekly_github.py
```

## Automation Schedule

| Workflow | Trigger | 职责 |
|----------|---------|------|
| `update-dashboard.yml` | 每日 9 AM UTC | fetch → AI commentary → rebuild dashboard |
| `weekly-report.yml` | 每周一 10 AM UTC | fetch → generate full report → push |

## Indicators

| Indicator | FRED Code | Frequency | Use |
|-----------|-----------|-----------|-----|
| SOFR | SOFR | Daily | Primary |
| SOFR-DFF spread | SOFR - DFF | Daily | Primary |
| TED spread | TEDRATE | Daily | Primary (LIBOR deprecated) |
| Net Liquidity | WALCL-WTREGEN-RRPONTTLD | Weekly | Primary |
| RRP | RRPONTTLD | Daily | Secondary |
| M2 YoY | M2SL | Monthly | Secondary |
| WALCL YoY | WALCL | Weekly | Secondary |
| T10Y2Y | T10Y2Y | Daily | Secondary |
| DXY | DTWEXBGS | Daily | Secondary |

## Status

✅ 2026-04-22: Daily dashboard (with AI) + Weekly report (rule-based) fully automated on GitHub Pages
