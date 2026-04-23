#!/usr/bin/env python3
"""
Build Gold Board HTML page from gold_board_data.json + templates.
Outputs docs/gold-board/index.html.
"""
import json
import os
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
HTML_OUT = SCRIPT_DIR.parent / "docs" / "gold-board" / "index.html"

HTML_OUT.parent.mkdir(parents=True, exist_ok=True)

ZONE_LABELS = {
    "normal": "正常",
    "vigilant": "警惕",
    "financial_repression": "金融抑制",
    "crisis": "危机",
}

ZONE_COLORS = {
    "normal": "#3fb950",
    "vigilant": "#d29922",
    "financial_repression": "#f0883e",
    "crisis": "#f85149",
}

QUADRANT_LABELS = {
    ("strong", "high"): "🥊 繁荣",
    ("weak", "high"): "📈 类滞胀",
    ("strong", "low"): "➡️ 正常增长",
    ("weak", "low"): "📉 衰退",
}

QUADRANT_COLORS = {
    ("strong", "high"): "#e8f5e9",
    ("weak", "high"): "#fff3e0",
    ("strong", "low"): "#e3f2fd",
    ("weak", "low"): "#fce4ec",
}

MA_COLOR = {
    "up": "#2d8a4e",
    "down": "#c0392b",
    "neutral": "#8a7d72",
}


def fmt(v, unit="", decimals=2):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{decimals}f}{unit}"
    return f"{v}{unit}"


def build_html(data: dict) -> str:
    # ── Extract data ────────────────────────────────────────────────────────
    fi = data.get("fiscal_index", {})
    zone = fi.get("zone", "unknown")
    m2x2 = data.get("matrix_2x2", {})
    fs = data.get("four_suits", {})
    layers = data.get("layers", {})
    price = data.get("gold_price", {})
    ma_data = data.get("moving_averages", {})
    updated = data.get("updated_at", "")[:16]

    gold_cur = price.get("current")
    gold_change = price.get("change")
    gold_chg_pct = price.get("change_pct")

    # ── Fiscal index gauge ──────────────────────────────────────────────────
    fi_score = fi.get("score") or 0
    fi_zone_label = ZONE_LABELS.get(zone, zone)
    fi_zone_color = ZONE_COLORS.get(zone, "#8a7d72")
    fi_gauge_pct = min(100, max(0, fi_score))

    # ── Four suits signals ──────────────────────────────────────────────────
    gvz_obj = fs.get("gvz", {})
    gvz = gvz_obj.get("value")
    gvz_date = gvz_obj.get("date")
    gvz_pct = gvz_obj.get("percentile")
    ma_sys = fs.get("ma_system", {})
    ma20 = ma_sys.get("ma20")
    ma60 = ma_sys.get("ma60")
    ma200 = ma_sys.get("ma200")

    # MA signal
    if gold_cur and ma200:
        ratio = gold_cur / ma200
        if ratio > 1.15:
            ma_signal = "📈 强势偏离"
            ma_color = MA_COLOR["up"]
        elif ratio > 1.0:
            ma_signal = "↗️ 偏强"
            ma_color = MA_COLOR["up"]
        elif ratio < 0.9:
            ma_signal = "📉 弱势偏离"
            ma_color = MA_COLOR["down"]
        else:
            ma_signal = "↔️ 震荡区间"
            ma_color = MA_COLOR["neutral"]
    else:
        ma_signal = "—"
        ma_color = MA_COLOR["neutral"]

    # GVZ signal
    if gvz:
        if gvz > 25:
            gvz_signal = "⚠️ 高波动预警"
            gvz_color = MA_COLOR["down"]
        elif gvz > 18:
            gvz_signal = "谨慎"
            gvz_color = "#d29922"
        elif gvz < 12:
            gvz_signal = "🥱 低波动（过度乐观）"
            gvz_color = MA_COLOR["neutral"]
        else:
            gvz_signal = "中性"
            gvz_color = MA_COLOR["neutral"]
    else:
        gvz_signal = "—"
        gvz_color = MA_COLOR["neutral"]

    # ── 2×2 Matrix ──────────────────────────────────────────────────────────
    growth = m2x2.get("growth", "unknown")
    inflation = m2x2.get("inflation", "unknown")
    quad = m2x2.get("quadrant", {})
    quad_label = quad.get("label", "—")
    quad_signal = quad.get("signal", "neutral")
    quad_color = QUADRANT_COLORS.get((growth, inflation), "#f5f0e8")

    # ── SGE Premium ─────────────────────────────────────────────────────────
    sge = data.get("sge_premium") or {}
    sge_premium = sge.get("premium_pct")
    sge_cny = sge.get("sge_cny")
    come_usd = sge.get("come_usd")
    fx = sge.get("fx_rate")

    # ── Layer 3 macro values ────────────────────────────────────────────────
    macro = layers.get("3_macro", {})
    inst = layers.get("4_institutional", {})

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gold Board — RhoZero</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🥇</text></svg>">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/d3@7.8.5/dist/d3.min.js"></script>
  <style>
    :root {{
      --bg: #f5f0e8; --card: #faf7f2; --border: #e0d8cc;
      --text: #2a2520; --muted: #8a7d72; --accent: #8B5A2B;
      --up: #2d8a4e; --down: #c0392b; --warn: #d29922;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg); color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      line-height: 1.6; min-height: 100vh;
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    /* ── Nav ── */
    nav {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 1rem 2rem; border-bottom: 1px solid var(--border);
      background: var(--card);
    }}
    .nav-brand {{
      font-size: 1rem; font-weight: 700;
      background: linear-gradient(135deg, #667eea, #764ba2);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .nav-links {{ display: flex; gap: 1.5rem; font-size: 0.85rem; }}
    .nav-links a {{ color: var(--muted); }}
    .nav-links a:hover {{ color: var(--accent); text-decoration: none; }}
    .nav-back {{ font-size: 0.8rem; color: var(--muted); }}

    /* ── Hero ── */
    .hero {{
      padding: 1.5rem 2rem; border-bottom: 1px solid var(--border);
      display: flex; align-items: flex-end; justify-content: space-between;
      flex-wrap: wrap; gap: 1rem;
    }}
    .hero-left {{}}
    .hero-ticker {{ font-size: 1.6rem; font-weight: 700; color: var(--accent); }}
    .hero-name {{ font-size: 0.8rem; color: var(--muted); }}
    .hero-right {{ text-align: right; }}
    .hero-price {{ font-size: 2.5rem; font-weight: 700; }}
    .hero-change {{ font-size: 1rem; font-weight: 600; }}
    .hero-updated {{ font-size: 0.75rem; color: var(--muted); margin-top: 0.25rem; }}

    /* ── Section headers ── */
    .section-header {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.75rem 2rem; border-bottom: 1px solid var(--border);
      background: var(--card);
    }}
    .section-title {{
      font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em;
      color: var(--muted); font-weight: 600;
    }}
    .section-badge {{
      font-size: 0.65rem; background: var(--accent); color: #fff;
      padding: 2px 8px; border-radius: 10px;
    }}

    /* ── Grid layouts ── */
    .grid-4 {{
      display: grid; grid-template-columns: repeat(4, 1fr);
      gap: 1px; background: var(--border);
    }}
    @media (max-width: 900px) {{ .grid-4 {{ grid-template-columns: repeat(2, 1fr); }} }}
    @media (max-width: 500px) {{ .grid-4 {{ grid-template-columns: 1fr; }} }}

    .grid-3 {{
      display: grid; grid-template-columns: 2fr 1fr 1fr;
      gap: 1px; background: var(--border);
    }}
    @media (max-width: 800px) {{ .grid-3 {{ grid-template-columns: 1fr; }} }}

    .grid-2 {{
      display: grid; grid-template-columns: 1fr 1fr;
      gap: 1px; background: var(--border);
    }}
    @media (max-width: 600px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}

    /* ── Cards ── */
    .card {{
      background: var(--card); padding: 1.25rem 1.5rem;
      display: flex; flex-direction: column; gap: 0.5rem;
    }}
    .card-label {{
      font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em;
      color: var(--muted);
    }}
    .card-value {{
      font-size: 1.5rem; font-weight: 700; color: var(--text); line-height: 1.2;
    }}
    .card-sub {{
      font-size: 0.75rem; color: var(--muted);
    }}
    .card-signal {{
      font-size: 0.8rem; font-weight: 600; margin-top: 0.25rem;
    }}

    /* ── Fiscal Index Gauge ── */
    .gauge-wrap {{
      background: var(--card); padding: 1.5rem; border-bottom: 1px solid var(--border);
    }}
    .gauge-inner {{
      max-width: 500px; margin: 0 auto; text-align: center;
    }}
    .gauge-title {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 1rem; }}
    .gauge-bar-bg {{
      height: 16px; border-radius: 8px; background: var(--border);
      overflow: hidden; position: relative;
    }}
    .gauge-bar-fill {{
      height: 100%; border-radius: 8px;
      background: linear-gradient(90deg, #3fb950, #d29922, #f0883e, #f85149);
      transition: width 0.6s ease;
    }}
    .gauge-bar-needle {{
      position: absolute; top: -4px; width: 3px; height: 24px;
      background: var(--text); border-radius: 2px;
      left: {fi_gauge_pct}%;
      transform: translateX(-50%);
    }}
    .gauge-score {{
      font-size: 2.5rem; font-weight: 700; margin-top: 0.75rem;
      color: {fi_zone_color};
    }}
    .gauge-zone {{
      font-size: 1rem; font-weight: 600; color: {fi_zone_color};
      text-transform: uppercase; letter-spacing: 0.05em;
    }}
    .gauge-range {{
      display: flex; justify-content: space-between;
      font-size: 0.65rem; color: var(--muted); margin-top: 0.25rem;
    }}

    /* ── Matrix 2×2 ── */
    .matrix-wrap {{ background: var(--card); padding: 1.5rem; border-bottom: 1px solid var(--border); }}
    .matrix-grid {{
      display: grid; grid-template-columns: 1fr 1fr;
      gap: 0.75rem; max-width: 480px; margin: 0 auto;
    }}
    .matrix-cell {{
      padding: 0.875rem; border-radius: 6px; border: 1px solid var(--border);
      font-size: 0.8rem;
    }}
    .matrix-cell.active {{ border-color: var(--accent); border-width: 2px; }}
    .matrix-cell-label {{ font-weight: 700; font-size: 0.9rem; margin-bottom: 0.25rem; }}
    .matrix-cell-desc {{ color: var(--muted); font-size: 0.7rem; }}
    .matrix-axis {{
      display: flex; justify-content: space-between; align-items: center;
      max-width: 480px; margin: 0 auto;
    }}
    .matrix-axis-label {{ font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }}
    .matrix-center {{ text-align: center; font-size: 0.65rem; color: var(--muted); max-width: 480px; margin: 0.5rem auto 0; }}

    /* ── Topology ── */
    .topo-wrap {{
      background: var(--card); padding: 1.5rem; border-bottom: 1px solid var(--border);
      min-height: 400px; position: relative;
    }}
    #topo-svg {{ width: 100%; height: 380px; }}
    .topo-instruction {{ text-align: center; font-size: 0.7rem; color: var(--muted); margin-top: 0.5rem; }}
    .topo-panel {{
      position: absolute; top: 1rem; right: 1rem; width: 240px;
      background: var(--bg); border: 1px solid var(--border);
      border-radius: 8px; padding: 1rem; font-size: 0.8rem;
      display: none;
    }}
    .topo-panel.show {{ display: block; }}
    .topo-panel-title {{ font-weight: 700; margin-bottom: 0.5rem; color: var(--accent); font-size: 0.85rem; }}
    .topo-panel-value {{ font-size: 1.3rem; font-weight: 700; }}
    .topo-panel-date {{ font-size: 0.7rem; color: var(--muted); }}
    .topo-panel-signal {{ margin-top: 0.5rem; font-size: 0.75rem; font-weight: 600; }}
    .topo-panel-desc {{ font-size: 0.7rem; color: var(--muted); margin-top: 0.25rem; line-height: 1.4; }}
    .topo-close {{
      position: absolute; top: 0.5rem; right: 0.75rem;
      font-size: 1rem; cursor: pointer; color: var(--muted);
    }}
    .topo-close:hover {{ color: var(--text); }}

    /* ── Four suits ── */
    .suits-wrap {{
      display: grid; grid-template-columns: repeat(2, 1fr);
      gap: 1px; background: var(--border);
    }}
    @media (max-width: 600px) {{ .suits-wrap {{ grid-template-columns: 1fr; }} }}
    .suit-card {{
      background: var(--card); padding: 1.25rem 1.5rem;
    }}
    .suit-name {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); margin-bottom: 0.5rem; }}
    .suit-value {{ font-size: 1.4rem; font-weight: 700; }}
    .suit-sub {{ font-size: 0.75rem; color: var(--muted); margin-top: 0.25rem; }}
    .suit-signal {{ font-size: 0.8rem; font-weight: 600; margin-top: 0.5rem; }}

    /* ── Chart ── */
    .chart-wrap {{
      background: var(--card); padding: 1.5rem; border-bottom: 1px solid var(--border);
    }}
    .chart-header {{
      display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;
    }}
    .chart-title {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }}
    .chart-legend {{ display: flex; gap: 1rem; font-size: 0.7rem; }}
    .legend-item {{ display: flex; align-items: center; gap: 0.4rem; }}
    .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
    #gold-chart {{ height: 280px; }}
    .chart-canvas-wrap {{ position: relative; height: 280px; }}

    /* ── Footer ── */
    footer {{
      text-align: center; padding: 1.5rem; font-size: 0.7rem;
      color: var(--muted); border-top: 1px solid var(--border);
    }}
    footer a {{ color: var(--muted); }}
    footer a:hover {{ color: var(--accent); }}
  </style>
</head>
<body>

<nav>
  <div>
    <div class="nav-brand">RhoZero</div>
    <div style="font-size:0.7rem;color:var(--muted)">Gold Board · 老钱黄金看板复刻</div>
  </div>
  <div class="nav-links">
    <a href="/docs/demo/gold.html">金价图表</a>
    <a href="/docs/dollar-liquidity-weekly-report/">流动性周报</a>
  </div>
  <a href="/docs/" class="nav-back">← Home</a>
</nav>

    <!-- ── Hero ── -->
<div class="hero">
  <div class="hero-left">
    <div class="hero-ticker">GC=F · Gold Futures</div>
    <div class="hero-name">USD / troy ounce · 日更</div>
  </div>
  <div class="hero-right">
    <div class="hero-price">${fmt(gold_cur, '', 2) if gold_cur else '—'}</div>
    <div class="hero-change" style="color: {'var(--up)' if gold_change and gold_change >= 0 else 'var(--down)'}">
      {'+' if gold_change and gold_change >= 0 else ''}{fmt(gold_change, '', 2)} ({'+' if gold_chg_pct and gold_chg_pct >= 0 else ''}{fmt(gold_chg_pct, '%', 2)}%)
    </div>
    <div class="hero-updated">Updated {updated} · GitHub Actions 日更</div>
  </div>
</div>

  <!-- ── Section: 全球地上存量 ── -->
<div class="section-header">
  <div class="section-title">全球地上黄金存量</div>
  <div class="section-badge">制度层</div>
</div>
<div style="background:var(--card);padding:1.25rem 2rem;border-bottom:1px solid var(--border);display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:1rem;text-align:center">
  <div style="display:flex;flex-direction:column;align-items:center;justify-content:center">
    <div style="font-size:2rem;font-weight:700;color:var(--accent)">224,266</div>
    <div style="font-size:0.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:0.05em">吨 · 全球地上存量</div>
  </div>
  <div>
    <div style="font-size:1.5rem;font-weight:700;color:#d4af37">44%</div>
    <div style="font-size:0.7rem;color:var(--muted)">金饰 · 98,677 吨</div>
  </div>
  <div>
    <div style="font-size:1.5rem;font-weight:700;color:#d4af37">23%</div>
    <div style="font-size:0.7rem;color:var(--muted)">投资 · 51,581 吨</div>
  </div>
  <div>
    <div style="font-size:1.5rem;font-weight:700;color:#d4af37">18%</div>
    <div style="font-size:0.7rem;color:var(--muted)">央行 · 40,368 吨</div>
  </div>
</div>

<!-- ── Section: 财政压力指数 ── -->
<div class="section-header">
  <div class="section-title">财政压力指数 · Fiscal Pressure Index</div>
  <div class="section-badge">制度层</div>
</div>
<div class="gauge-wrap">
  <div class="gauge-inner">
    <div class="gauge-title">当前评分 {fmt(fi_score, '/100', 1)}</div>
    <div class="gauge-bar-bg">
      <div class="gauge-bar-fill" style="width:{fi_gauge_pct}%"></div>
      <div class="gauge-bar-needle"></div>
    </div>
    <div class="gauge-range">
      <span>Normal</span><span>Vigilant</span><span>金融抑制</span><span>Crisis</span>
    </div>
    <div class="gauge-zone">{fi_zone_label}</div>
    <div style="margin-top:0.75rem;display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;text-align:center;font-size:0.75rem;color:var(--muted)">
      <div>
        <div style="font-size:1rem;font-weight:700;color:var(--text)">{fmt(inst.get('debt_gdp'),'%',1) if inst.get('debt_gdp') else '—'}</div>
        <div>债务 / GDP</div>
      </div>
      <div>
        <div style="font-size:1rem;font-weight:700;color:var(--text)">{fmt(inst.get('deficit_gdp'),'%',1) if inst.get('deficit_gdp') else '—'}</div>
        <div>赤字 / GDP</div>
      </div>
      <div>
        <div style="font-size:1rem;font-weight:700;color:var(--text)">{fmt(data.get('interest_burden'),'%',1) if data.get('interest_burden') else '—'}</div>
        <div>利息/收入占比</div>
      </div>
    </div>
  </div>
</div>

<!-- ── Section: 通胀×增长矩阵 ── -->
<div class="section-header">
  <div class="section-title">通胀 × 增长 2×2 矩阵</div>
  <div class="section-badge">宏观层</div>
</div>
<div class="matrix-wrap">
  <div class="matrix-axis">
    <span class="matrix-axis-label">← 增长弱</span>
    <span class="matrix-axis-label">增长强 →</span>
  </div>
  <div style="display:flex;align-items:center;gap:0.5rem;max-width:480px;margin:0 auto">
    <span class="matrix-axis-label" style="writing-mode:vertical-rl;transform:rotate(180deg)">通胀高 ↑</span>
    <div class="matrix-grid">
      <div class="matrix-cell {'active' if (growth,inflation)==('strong','high') else ''}" style="background:{QUADRANT_COLORS.get(('strong','high'),'#f5f0e8')}">
        <div class="matrix-cell-label">🥊 繁荣</div>
        <div class="matrix-cell-desc">风险资产受追捧，黄金中性</div>
      </div>
      <div class="matrix-cell {'active' if (growth,inflation)==('weak','high') else ''}" style="background:{QUADRANT_COLORS.get(('weak','high'),'#f5f0e8')}">
        <div class="matrix-cell-label">📈 类滞胀</div>
        <div class="matrix-cell-desc">黄金历史上最喜欢的剧本</div>
      </div>
      <div class="matrix-cell {'active' if (growth,inflation)==('strong','low') else ''}" style="background:{QUADRANT_COLORS.get(('strong','low'),'#f5f0e8')}">
        <div class="matrix-cell-label">➡️ 正常增长</div>
        <div class="matrix-cell-desc">黄金中性偏弱</div>
      </div>
      <div class="matrix-cell {'active' if (growth,inflation)==('weak','low') else ''}" style="background:{QUADRANT_COLORS.get(('weak','low'),'#f5f0e8')}">
        <div class="matrix-cell-label">📉 衰退</div>
        <div class="matrix-cell-desc">央行宽松，黄金中性偏多</div>
      </div>
    </div>
    <span class="matrix-axis-label" style="writing-mode:vertical-rl">通胀低 ↓</span>
  </div>
  <div class="matrix-center">
    当前: <strong>{QUADRANT_LABELS.get((growth, inflation), '—')}</strong>
    &nbsp;·&nbsp; 信号: <strong>{quad_signal}</strong>
    &nbsp;·&nbsp; PCE={fmt(macro.get('core_pce'),'%',1)} · NFCI={fmt(macro.get('financial_cond'),'',2)} · UNRATE={fmt(macro.get('unemployment'),'%',1)}
  </div>
</div>

<!-- ── Section: 拓扑图 ── -->
<div class="section-header">
  <div class="section-title">黄金定价拓扑网 · 4层 × 21节点</div>
  <div class="section-badge">系统全景</div>
</div>
<div class="topo-wrap">
  <svg id="topo-svg"></svg>
  <div class="topo-instruction">点击节点查看详情 · 拖拽可移动</div>
  <div class="topo-panel" id="topo-panel">
    <div class="topo-close" onclick="closePanel()">×</div>
    <div class="topo-panel-title" id="panel-title">—</div>
    <div class="topo-panel-value" id="panel-value">—</div>
    <div class="topo-panel-date" id="panel-date"></div>
    <div class="topo-panel-signal" id="panel-signal"></div>
    <div class="topo-panel-desc" id="panel-desc"></div>
  </div>
</div>

<!-- ── Section: 上海金溢价 ── -->
<div class="section-header">
  <div class="section-title">上海金 vs 国际金价 · 中国需求代理</div>
  <div class="section-badge">市场层</div>
</div>
<div style="background:var(--card);padding:1.25rem 2rem;border-bottom:1px solid var(--border);display:grid;grid-template-columns:1fr 1fr 1fr;gap:2rem;text-align:center">
  <div>
    <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);margin-bottom:0.25rem">当前溢价</div>
    <div style="font-size:2rem;font-weight:700;color:{'var(--up)' if sge_premium and sge_premium > 0 else 'var(--down)'}">{f'{sge_premium:+.1f}%' if sge_premium else '—'}</div>
    <div style="font-size:0.7rem;color:var(--muted)">正值=中国买家溢价买入</div>
  </div>
  <div>
    <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);margin-bottom:0.25rem">上海金 SGE Au9999</div>
    <div style="font-size:1.5rem;font-weight:700;color:var(--accent)">{f'¥{sge_cny:,.0f}/oz' if sge_cny else '—'}</div>
    <div style="font-size:0.7rem;color:var(--muted)">CNY/troy oz</div>
  </div>
  <div>
    <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);margin-bottom:0.25rem">国际金 COMEX</div>
    <div style="font-size:1.5rem;font-weight:700">{f'${come_usd:,.0f}/oz' if come_usd else '—'}</div>
    <div style="font-size:0.7rem;color:var(--muted)">USD/troy oz · 汇率 {f'{fx:.2f}' if fx else '—'}</div>
  </div>
</div>

<!-- ── Section: 四件套 ── -->
<div class="section-header">
  <div class="section-title">短期信号四件套</div>
  <div class="section-badge">市场层</div>
</div>
<div class="suits-wrap">
  <div class="suit-card">
    <div class="suit-name">① GVZ 波动率指数</div>
    <div class="suit-value">{fmt(gvz, '', 1) if gvz else '—'}</div>
    <div class="suit-sub">CBOE黄金期权隐含波动率{gvz_date and ' · ' + gvz_date or ''}</div>
    <div class="suit-sub" style="color:#888">{gvz_pct and '历史分位: ' + str(gvz_pct) + '%' or '历史分位: 计算中...'}</div>
    <div class="suit-signal" style="color:{gvz_color}">{gvz_signal}</div>
  </div>
  <div class="suit-card">
    <div class="suit-name">② 均线系统</div>
    <div class="suit-value">${fmt(gold_cur, '', 0) if gold_cur else '—'}</div>
    <div class="suit-sub">MA20={fmt(ma20,'$',0)} · MA60={fmt(ma60,'$',0)} · MA200={fmt(ma200,'$',0)}</div>
    <div class="suit-signal" style="color:{ma_color}">{ma_signal}</div>
  </div>
  <div class="suit-card">
    <div class="suit-name">③ GLD ETF 持仓</div>
    <div class="suit-value">{fmt(fs.get('gld_etf',{}).get('shares'),'M',1) if fs.get('gld_etf',{}).get('shares') else '—'}</div>
    <div class="suit-sub">{fs.get('gld_etf',{}).get('unit','')}{f" · {fs.get('gld_etf',{}).get('percentile'):.0f}分位" if fs.get('gld_etf',{}).get('percentile') else ''}</div>
    <div class="suit-signal" style="color:var(--muted)">持仓量历史分位</div>
  </div>
  <div class="suit-card">
    <div class="suit-name">④ CFTC 净多头</div>
    <div class="suit-value">{f"{fs.get('cfct',{}).get('net_long'):,.0f}" if fs.get('cfct',{}).get('net_long') is not None else '—'}</div>
    <div class="suit-sub">COT 周度持仓报告{ f" · {fs.get('cfct',{}).get('week','')}" if fs.get('cfct',{}).get('week') else ''}</div>
    <div class="suit-signal" style="color:var(--muted)">{fs.get('cfct',{}).get('note','') if not fs.get('cfct',{}).get('net_long') else 'Managed Money净多头'}</div>
  </div>
</div>

<!-- ── Section: 金价走势图 ── -->
<div class="section-header">
  <div class="section-title">金价走势 · 2年</div>
  <div class="section-badge">结果层</div>
</div>
<div class="chart-wrap">
  <div class="chart-header">
    <div class="chart-title">Gold Futures (GC=F) · Daily Close</div>
    <div class="chart-legend">
      <div class="legend-item"><div class="legend-dot" style="background:#f5c518"></div>Gold</div>
      <div class="legend-item"><div class="legend-dot" style="background:#667eea"></div>MA60</div>
      <div class="legend-item"><div class="legend-dot" style="background:#c0392b;opacity:0.5"></div>MA200</div>
    </div>
  </div>
  <div class="chart-canvas-wrap">
    <canvas id="gold-chart"></canvas>
  </div>
</div>

<!-- ── Section: 历史洞察 · 对数同比 ── -->
<div class="section-header">
  <div class="section-title">历史洞察 · 金价对数同比</div>
  <div class="section-badge">分析层</div>
</div>
<div class="chart-wrap">
  <div class="chart-header">
    <div class="chart-title">ln(Pt) - ln(Pt-252) · 交易日同比 %</div>
    <div class="chart-legend">
      <div class="legend-item"><div class="legend-dot" style="background:#f5c518"></div>对数同比</div>
      <div class="legend-item"><div class="legend-dot" style="background:#27ae60"></div>零线</div>
    </div>
  </div>
  <div class="chart-canvas-wrap">
    <canvas id="log-yoy-chart"></canvas>
  </div>
</div>

<!-- ── Section: 机会成本 ── -->
<div class="section-header">
  <div class="section-title">机会成本 · 实际利率 vs 通胀预期 vs 美元</div>
  <div class="section-badge">宏观层</div>
</div>
<div class="chart-wrap">
  <div class="chart-header">
    <div class="chart-title">DFII10 (实际利率) · T10YIE (通胀预期) · DXY指数 · 日频</div>
    <div class="chart-legend">
      <div class="legend-item"><div class="legend-dot" style="background:#2ecc71"></div>实际利率</div>
      <div class="legend-item"><div class="legend-dot" style="background:#e74c3c"></div>通胀预期</div>
      <div class="legend-item"><div class="legend-dot" style="background:#9b59b6"></div>DXY (右轴)</div>
    </div>
  </div>
  <div class="chart-canvas-wrap">
    <canvas id="opp-cost-chart"></canvas>
  </div>
</div>

<!-- ── Section: 美元与流动性 ── -->
<div class="section-header">
  <div class="section-title">美元与流动性 · DXY · NFCI · SOFR</div>
  <div class="section-badge">宏观层</div>
</div>
<div class="chart-wrap">
  <div class="chart-header">
    <div class="chart-title">DTWEXBGS (DXY) · NFCI (金融条件) · SOFR (联邦基金利率) · 日频</div>
    <div class="chart-legend">
      <div class="legend-item"><div class="legend-dot" style="background:#9b59b6"></div>DXY</div>
      <div class="legend-item"><div class="legend-dot" style="background:#3498db"></div>NFCI</div>
      <div class="legend-item"><div class="legend-dot" style="background:#e67e22"></div>SOFR (右轴)</div>
    </div>
  </div>
  <div class="chart-canvas-wrap">
    <canvas id="usd-liab-chart"></canvas>
  </div>
</div>

<!-- ── Section: 通胀与增长 ── -->
<div class="section-header">
  <div class="section-title">通胀与增长 · PCE同比 · 失业率</div>
  <div class="section-badge">宏观层</div>
</div>
<div class="chart-wrap">
  <div class="chart-header">
    <div class="chart-title">PCEPI YoY (%) · UNRATE (%) · 月频</div>
    <div class="chart-legend">
      <div class="legend-item"><div class="legend-dot" style="background:#e74c3c"></div>PCE同比</div>
      <div class="legend-item"><div class="legend-dot" style="background:#3498db"></div>失业率</div>
    </div>
  </div>
  <div class="chart-canvas-wrap">
    <canvas id="infl-growth-chart"></canvas>
  </div>
</div>

<!-- ── Section: 财政与信用 ── -->
<div class="section-header">
  <div class="section-title">财政与信用 · 债务 & 赤字趋势</div>
  <div class="section-badge">制度层</div>
</div>
<div class="chart-wrap">
  <div class="chart-header">
    <div class="chart-title">GFDEGDQ188S (债务/GDP) · FYFSD (赤字/GDP估算) · 季度</div>
    <div class="chart-legend">
      <div class="legend-item"><div class="legend-dot" style="background:#c0392b"></div>债务/GDP</div>
      <div class="legend-item"><div class="legend-dot" style="background:#e67e22"></div>赤字/GDP估算</div>
    </div>
  </div>
  <div class="chart-canvas-wrap">
    <canvas id="fiscal-chart"></canvas>
  </div>
</div>

<!-- ── Macro indicators ── -->
<div class="section-header">
  <div class="section-title">宏观指标一览</div>
  <div class="section-badge">宏观层</div>
</div>
<div class="grid-4">
  <div class="card">
    <div class="card-label">实际利率</div>
    <div class="card-value" style="{'color:var(--up)' if macro.get('real_rate',0) and macro.get('real_rate') < 0 else 'color:var(--down)'}">{fmt(macro.get('real_rate'),'%',2) if macro.get('real_rate') is not None else '—'}</div>
    <div class="card-sub">DFII10 · 10年期通胀调整国债</div>
  </div>
  <div class="card">
    <div class="card-label">通胀预期</div>
    <div class="card-value">{fmt(macro.get('inflation_exp'),'%',2) if macro.get('inflation_exp') is not None else '—'}</div>
    <div class="card-sub">T10YIE · 10年盈亏平衡通胀率</div>
  </div>
  <div class="card">
    <div class="card-label">美元指数</div>
    <div class="card-value">{fmt(macro.get('dxy'),'',1) if macro.get('dxy') is not None else '—'}</div>
    <div class="card-sub">DTWEXBGS · 贸易加权美元</div>
  </div>
  <div class="card">
    <div class="card-label">金融条件指数</div>
    <div class="card-value" style="{'color:var(--up)' if macro.get('financial_cond',0) and macro.get('financial_cond') < 0 else 'color:var(--down)'}">{fmt(macro.get('financial_cond'),'',2) if macro.get('financial_cond') is not None else '—'}</div>
    <div class="card-sub">NFCI · 芝加哥金融条件</div>
  </div>
  <div class="card">
    <div class="card-label">核心PCE</div>
    <div class="card-value">{fmt(macro.get('core_pce'),'%',1) if macro.get('core_pce') is not None else '—'}</div>
    <div class="card-sub">PCEPI · 同比 · 美联储通胀目标</div>
  </div>
  <div class="card">
    <div class="card-label">失业率</div>
    <div class="card-value" style="{'color:var(--down)' if macro.get('unemployment',0) and macro.get('unemployment') > 5 else 'color:var(--up)'}">{fmt(macro.get('unemployment'),'%',1) if macro.get('unemployment') is not None else '—'}</div>
    <div class="card-sub">UNRATE · 贝弗里奇曲线</div>
  </div>
  <div class="card">
    <div class="card-label">债务 / GDP</div>
    <div class="card-value">{fmt(inst.get('debt_gdp'),'%',1) if inst.get('debt_gdp') else '—'}</div>
    <div class="card-sub">GFDEGDQ188S</div>
  </div>
  <div class="card">
    <div class="card-label">赤字 / GDP</div>
    <div class="card-value" style="{'color:var(--down)' if inst.get('deficit_gdp') and inst.get('deficit_gdp') > 5 else 'color:var(--warn)'}">{fmt(inst.get('deficit_gdp'),'%',1) if inst.get('deficit_gdp') else '—'}</div>
    <div class="card-sub">FYFSD · 年度财政赤字</div>
  </div>
  <div class="card">
    <div class="card-label">SOFR</div>
    <div class="card-value">{fmt(macro.get('sofr'),'%',2) if macro.get('sofr') is not None else '—'}</div>
    <div class="card-sub">担保隔夜融资利率</div>
  </div>
  <div class="card">
    <div class="card-label">10Y 国债</div>
    <div class="card-value">{fmt(macro.get('treasury_10y'),'%',2) if macro.get('treasury_10y') is not None else '—'}</div>
    <div class="card-sub">DGS10 · 名义收益率</div>
  </div>
</div>

<!-- ── Institutional: 央行净购金 & 美元储备 ── -->
<div class="section-header">
  <div class="section-title">制度层 · 央行 &amp; 储备货币</div>
  <div class="section-badge">制度层</div>
</div>
<div style="background:var(--card);padding:1.25rem 2rem;border-bottom:1px solid var(--border);display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--border)">
  <div class="card">
    <div class="card-label">央行季度净购金</div>
    <div class="card-value" style="color:var(--accent)">~1,000</div>
    <div class="card-sub">吨 / 季度 · WGC</div>
    <div class="card-signal" style="color:var(--up)">结构性买盘</div>
    <div style="font-size:0.7rem;color:var(--muted);margin-top:0.25rem">2022年后年化千吨级别，与利率/金价脱敏</div>
  </div>
  <div class="card">
    <div class="card-label">美元储备占比</div>
    <div class="card-value" style="color:var(--accent)">57.8%</div>
    <div class="card-sub">IMF COFER · 季度</div>
    <div class="card-signal" style="color:var(--muted)">趋势下行</div>
    <div style="font-size:0.7rem;color:var(--muted);margin-top:0.25rem">2000年高点72% → 当前57.8%</div>
  </div>
</div>

<footer>
  Gold Board · 基于老钱黄金看板框架复刻 · 纯静态 GitHub Pages
  <br>
  数据来源: FRED · Yahoo Finance · WGC · IMF COFER
  · 框架参考: <a href="https://gold-board.betalpha.com/" target="_blank">gold-board.betalpha.com</a>
</footer>

<script>
// ─── Gold Chart ──────────────────────────────────────────────────────────────
(function() {{
  const rawData = {json.dumps(data, ensure_ascii=False)};

  const hist = rawData.price_history || [];
  const maData = rawData.moving_averages || {{}};
  const dates = hist.map(d => d.date);
  const closes = hist.map(d => d.close);
  const ma60_vals = (maData.ma60 || []).map(v => v ?? null);
  const ma200_vals = (maData.ma200 || []).map(v => v ?? null);

  const ctx = document.getElementById('gold-chart').getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 280);
  gradient.addColorStop(0, 'rgba(245,197,24,0.15)');
  gradient.addColorStop(1, 'rgba(245,197,24,0)');

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
          pointHoverRadius: 4,
          fill: true,
          backgroundColor: gradient,
          tension: 0.1,
        }},
        {{
          label: 'MA60',
          data: ma60_vals,
          borderColor: '#667eea',
          borderWidth: 1.2,
          pointRadius: 0,
          borderDash: [4, 4],
          fill: false,
          tension: 0.1,
        }},
        {{
          label: 'MA200',
          data: ma200_vals,
          borderColor: 'rgba(192,57,43,0.5)',
          borderWidth: 1.2,
          pointRadius: 0,
          fill: false,
          tension: 0.1,
        }},
      ]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          backgroundColor: 'rgba(17,17,24,0.95)',
          titleColor: '#e0e0e0',
          bodyColor: '#e0e0e0',
          borderColor: '#1e1e2a',
          borderWidth: 1,
          padding: 12,
          callbacks: {{
            label: ctx2 => {{
              const v = ctx2.parsed.y;
              return ctx2.datasetIndex === 0
                ? 'Gold: $' + v.toLocaleString('en-US', {{minimumFractionDigits: 2}})
                : ctx2.dataset.label + ': $' + (v != null ? v.toLocaleString('en-US', {{minimumFractionDigits: 2}}) : '—');
            }}
          }}
        }}
      }},
      scales: {{
        x: {{
          type: 'category',
          ticks: {{ color: '#666', maxTicksLimit: 10, maxRotation: 0, font: {{ size: 11 }} }},
          grid: {{ color: '#d5cdc2' }}
        }},
        y: {{
          ticks: {{ color: '#666', font: {{ size: 11 }}, callback: v => '$' + v.toLocaleString() }},
          grid: {{ color: '#d5cdc2' }}
        }}
      }}
    }}
  }});
}})();

// ─── Panel 1: Log YoY Chart ────────────────────────────────────────────────────
(function() {{
  const sh = rawData.series_history || {{}};
  const logYoy = sh.gold_log_yoy || {{}};
  const logDates = logYoy.dates || [];
  const logVals = (logYoy.values || []).map(v => v ?? null);

  if (logDates.length > 0) {{
    const ctx = document.getElementById('log-yoy-chart').getContext('2d');
    // Color each point green/red based on sign
    const colors = logVals.map(v => v == null ? 'transparent' : v >= 0 ? '#27ae60' : '#e74c3c');
    new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: logDates,
        datasets: [
          {{
            label: '对数同比 %',
            data: logVals,
            borderColor: '#f5c518',
            backgroundColor: logVals.map(v => v == null ? 'transparent' : v >= 0 ? 'rgba(39,174,96,0.15)' : 'rgba(231,76,60,0.15)'),
            borderWidth: 1.5,
            pointRadius: 0,
            fill: true,
            tension: 0.1,
            segment: {{
              borderColor: ctx => {{
                const idx = ctx.p0DataIndex;
                return logVals[idx] >= 0 ? '#27ae60' : '#e74c3c';
              }}
            }}
          }},
          {{
            label: '零线',
            data: logDates.map(() => 0),
            borderColor: 'rgba(100,100,100,0.3)',
            borderWidth: 1,
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false,
          }}
        ]
      }},
      options: {{
        responsive: true, maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            backgroundColor: 'rgba(17,17,24,0.95)', titleColor: '#e0e0e0', bodyColor: '#e0e0e0',
            borderColor: '#1e1e2a', borderWidth: 1, padding: 12,
            callbacks: {{
              label: ctx2 => {{
                const v = ctx2.parsed.y;
                return v != null ? (v >= 0 ? '↑ ' : '↓ ') + Math.abs(v).toFixed(1) + '%' : '—';
              }}
            }}
          }}
        }},
        scales: {{
          x: {{ type: 'category', ticks: {{ color: '#666', maxTicksLimit: 10, maxRotation: 0, font: {{ size: 11 }} }}, grid: {{ color: '#d5cdc2' }} }},
          y: {{ ticks: {{ color: '#666', font: {{ size: 11 }}, callback: v => v + '%' }}, grid: {{ color: '#d5cdc2' }} }}
        }}
      }}
    }});
  }}
}})();

// ─── Panel 2: Opportunity Cost Chart ──────────────────────────────────────────
(function() {{
  const sh = rawData.series_history || {{}};
  const rr = sh.real_rate || {{}};
  const ie = sh.inflation_exp || {{}};
  const dxy = sh.dxy || {{}};

  if (rr.dates && rr.dates.length > 0) {{
    const ctx = document.getElementById('opp-cost-chart').getContext('2d');
    const dates = rr.dates; // use real_rate dates as master

    // Align series to real_rate dates
    const rrVals = rr.values || [];
    const ieMap = {{}};
    if (ie.dates) {{ ie.dates.forEach((d,i) => ieMap[d] = ie.values[i]); }}
    const dxyMap = {{}};
    if (dxy.dates) {{ dxy.dates.forEach((d,i) => dxyMap[d] = dxy.values[i]); }}

    const ieVals = dates.map(d => ieMap[d] ?? null);
    const dxyVals = dates.map(d => dxyMap[d] ?? null);

    new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: dates,
        datasets: [
          {{
            label: '实际利率 %',
            data: rrVals.map(v => v ?? null),
            borderColor: '#2ecc71', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1, yAxisID: 'y',
          }},
          {{
            label: '通胀预期 %',
            data: ieVals,
            borderColor: '#e74c3c', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1, yAxisID: 'y',
          }},
          {{
            label: 'DXY',
            data: dxyVals,
            borderColor: '#9b59b6', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1,
            borderDash: [4, 4], yAxisID: 'y2',
          }}
        ]
      }},
      options: {{
        responsive: true, maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            backgroundColor: 'rgba(17,17,24,0.95)', titleColor: '#e0e0e0', bodyColor: '#e0e0e0',
            borderColor: '#1e1e2a', borderWidth: 1, padding: 12,
          }}
        }},
        scales: {{
          x: {{ type: 'category', ticks: {{ color: '#666', maxTicksLimit: 10, maxRotation: 0, font: {{ size: 11 }} }}, grid: {{ color: '#d5cdc2' }} }},
          y: {{ position: 'left', ticks: {{ color: '#2ecc71', font: {{ size: 11 }}, callback: v => v + '%' }}, grid: {{ color: '#d5cdc2' }} }},
          y2: {{ position: 'right', ticks: {{ color: '#9b59b6', font: {{ size: 11 }} }}, grid: {{ drawOnChartArea: false }} }}
        }}
      }}
    }});
  }}
}})();

// ─── Panel 3: USD & Liquidity Chart ───────────────────────────────────────────
(function() {{
  const sh = rawData.series_history || {{}};
  const dxy = sh.dxy || {{}};
  const nfci = sh.nfci || {{}};
  const sofr = sh.sofr || {{}};

  if (dxy.dates && dxy.dates.length > 0) {{
    const ctx = document.getElementById('usd-liab-chart').getContext('2d');
    const dates = dxy.dates;

    const nfciMap = {{}};
    if (nfci.dates) {{ nfci.dates.forEach((d,i) => nfciMap[d] = nfci.values[i]); }}
    const sofrMap = {{}};
    if (sofr.dates) {{ sofr.dates.forEach((d,i) => sofrMap[d] = sofr.values[i]); }}

    const nfciVals = dates.map(d => nfciMap[d] ?? null);
    const sofrVals = dates.map(d => sofrMap[d] ?? null);

    new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: dates,
        datasets: [
          {{
            label: 'DXY',
            data: (dxy.values || []).map(v => v ?? null),
            borderColor: '#9b59b6', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1, yAxisID: 'y',
          }},
          {{
            label: 'NFCI',
            data: nfciVals,
            borderColor: '#3498db', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1, yAxisID: 'y',
          }},
          {{
            label: 'SOFR %',
            data: sofrVals,
            borderColor: '#e67e22', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1,
            borderDash: [4, 4], yAxisID: 'y2',
          }}
        ]
      }},
      options: {{
        responsive: true, maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            backgroundColor: 'rgba(17,17,24,0.95)', titleColor: '#e0e0e0', bodyColor: '#e0e0e0',
            borderColor: '#1e1e2a', borderWidth: 1, padding: 12,
          }}
        }},
        scales: {{
          x: {{ type: 'category', ticks: {{ color: '#666', maxTicksLimit: 10, maxRotation: 0, font: {{ size: 11 }} }}, grid: {{ color: '#d5cdc2' }} }},
          y: {{ position: 'left', ticks: {{ color: '#9b59b6', font: {{ size: 11 }} }}, grid: {{ color: '#d5cdc2' }} }},
          y2: {{ position: 'right', ticks: {{ color: '#e67e22', font: {{ size: 11 }}, callback: v => v + '%' }}, grid: {{ drawOnChartArea: false }} }}
        }}
      }}
    }});
  }}
}})();

// ─── Panel 4: Inflation & Growth Chart ────────────────────────────────────────
(function() {{
  const sh = rawData.series_history || {{}};
  const unemp = sh.unemployment || {{}};
  const pcepi = sh.pcepi || {{}};

  // Compute PCE YoY from stored PCEPI monthly history
  // PCEPI dates are YYYY-MM-DD monthly; YoY = (current/prior_year - 1) * 100
  function computePceYoy(pcepiVals, pcepiDates) {{
    if (!pcepiVals || pcepiVals.length < 13) return [];
    const result = [];
    for (let i = 12; i < pcepiVals.length; i++) {{
      const curr = pcepiVals[i];
      const prior = pcepiVals[i - 12];
      if (curr != null && prior != null && prior > 0) {{
        result.push({{ date: pcepiDates[i], yoy: Math.round((curr / prior - 1) * 10000) / 100 }});
      }}
    }}
    return result;
  }}

  const pceYoyData = computePceYoy(pcepi.values, pcepi.dates);

  if (pcepi.dates && pcepi.dates.length > 0) {{
    const ctx = document.getElementById('infl-growth-chart').getContext('2d');

    // PCE YoY time series (available)
    const pceDates = pceYoyData.map(d => d.date);
    const pceVals = pceYoyData.map(d => d.yoy);

    // For unemployment, use its own monthly dates
    const unempDates = unemp.dates || [];
    const unempVals = (unemp.values || []).map(v => v ?? null);

    // Merge dates: use whichever series is available at each date
    const allDates = [...new Set([...pceDates, ...unempDates])].sort();

    const pceMap = {{}};
    pceYoyData.forEach(d => pceMap[d.date] = d.yoy);
    const unempMap = {{}};
    if (unemp.dates) {{ unemp.dates.forEach((d,i) => unempMap[d] = unemp.values[i]); }}

    const mergedPceVals = allDates.map(d => pceMap[d] ?? null);
    const mergedUnempVals = allDates.map(d => unempMap[d] ?? null);

    new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: allDates,
        datasets: [
          {{
            label: 'PCE同比 %',
            data: mergedPceVals,
            borderColor: '#e74c3c', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1,
          }},
          {{
            label: '失业率 %',
            data: mergedUnempVals,
            borderColor: '#3498db', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0.1,
          }}
        ]
      }},
      options: {{
        responsive: true, maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            backgroundColor: 'rgba(17,17,24,0.95)', titleColor: '#e0e0e0', bodyColor: '#e0e0e0',
            borderColor: '#1e1e2a', borderWidth: 1, padding: 12,
            callbacks: {{
              label: ctx2 => {{
                const v = ctx2.parsed.y;
                return v != null ? ctx2.dataset.label.split(' ')[0] + ': ' + v.toFixed(1) + '%' : '';
              }}
            }}
          }}
        }},
        scales: {{
          x: {{ type: 'category', ticks: {{ color: '#666', maxTicksLimit: 10, maxRotation: 0, font: {{ size: 11 }} }}, grid: {{ color: '#d5cdc2' }} }},
          y: {{ ticks: {{ color: '#666', font: {{ size: 11 }}, callback: v => v + '%' }}, grid: {{ color: '#d5cdc2' }} }}
        }}
      }}
    }});
  }}
}})();

// ─── Panel 5: Fiscal Trends Chart ─────────────────────────────────────────────
(function() {{
  const sh = rawData.series_history || {{}};
  const debt = sh.debt_gdp || {{}};
  const fiscal = rawData.fiscal_index || {{}};
  const deficitRaw = fiscal.deficit_gdp_raw;

  if (debt.dates && debt.dates.length > 0) {{
    const ctx = document.getElementById('fiscal-chart').getContext('2d');
    const dates = debt.dates;
    const debtVals = (debt.values || []).map(v => v ?? null);
    // deficit_gdp is a single current value — show as dashed reference line
    const deficitVals = dates.map((_, i) => i === dates.length - 1 && deficitRaw != null ? deficitRaw : null);

    new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: dates,
        datasets: [
          {{
            label: '债务/GDP %',
            data: debtVals,
            borderColor: '#c0392b', borderWidth: 2, pointRadius: 2, fill: false, tension: 0.1,
          }},
          {{
            label: '赤字/GDP估算 %',
            data: deficitVals,
            borderColor: '#e67e22', borderWidth: 2, pointRadius: 4, fill: false,
            showLine: false,
          }}
        ]
      }},
      options: {{
        responsive: true, maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            backgroundColor: 'rgba(17,17,24,0.95)', titleColor: '#e0e0e0', bodyColor: '#e0e0e0',
            borderColor: '#1e1e2a', borderWidth: 1, padding: 12,
            callbacks: {{
              label: ctx2 => {{
                const v = ctx2.parsed.y;
                return v != null ? ctx2.dataset.label + ': ' + v.toFixed(1) + '%' : '';
              }}
            }}
          }}
        }},
        scales: {{
          x: {{ type: 'category', ticks: {{ color: '#666', maxTicksLimit: 10, maxRotation: 0, font: {{ size: 11 }} }}, grid: {{ color: '#d5cdc2' }} }},
          y: {{ ticks: {{ color: '#666', font: {{ size: 11 }}, callback: v => v + '%' }}, grid: {{ color: '#d5cdc2' }} }}
        }}
      }}
    }});
  }}
}})();

// ─── Topology Graph ──────────────────────────────────────────────────────────
(function() {{
  const LAYERS = [
    // Layer 4: Institutional
    {{ id: 'debt_gdp',     label: '债务/GDP',     layer: 4, color: '#e74c3c', desc: '政府杠杆率，过高意味着偿债压力' }},
    {{ id: 'deficit_gdp', label: '赤字/GDP',     layer: 4, color: '#e67e22', desc: '财政缺口，持续赤字推高债务' }},
    {{ id: 'interest',    label: '净利息支出',   layer: 4, color: '#9b59b6', desc: '利息/财政收入，过高进入金融抑制' }},
    {{ id: 'cb_gold',     label: '央行购金',     layer: 4, color: '#8B5A2B', desc: 'WGC季度数据，年化1000吨级别' }},
    {{ id: 'usd_reserve', label: '美元储备占比', layer: 4, color: '#3498db', desc: 'IMF COFER，储备货币地位' }},
    // Layer 3: Macro
    {{ id: 'real_rate',   label: '实际利率',     layer: 3, color: '#27ae60', desc: 'DFII10，实际利率与黄金负相关' }},
    {{ id: 'inflation',  label: '通胀预期',     layer: 3, color: '#e74c3c', desc: 'T10YIE，通胀预期上升利好黄金' }},
    {{ id: 'dxy',         label: '美元指数',     layer: 3, color: '#3498db', desc: 'DXY，美元强则黄金弱' }},
    {{ id: 'fci',         label: '金融条件',     layer: 3, color: '#9b59b6', desc: 'NFCI，收紧→资金撤出风险资产' }},
    {{ id: 'pce',         label: '核心PCE',      layer: 3, color: '#f39c12', desc: '美联储通胀目标，>2.5%滞胀风险' }},
    {{ id: 'unemp',       label: '失业率',       layer: 3, color: '#1abc9c', desc: 'UNRATE，高失业+高通胀=滞胀' }},
    // Layer 2: Market
    {{ id: 'gld_etf',     label: 'GLD ETF持仓', layer: 2, color: '#f5c518', desc: '机构配置行为代理' }},
    {{ id: 'cfct',        label: 'CFTC净多头',   layer: 2, color: '#e67e22', desc: 'COT周报，投机仓位拥挤度' }},
    {{ id: 'gvz',         label: 'GVZ波动率',    layer: 2, color: '#e74c3c', desc: 'CBOE黄金波动率指数' }},
    {{ id: 'momentum',    label: '短中长动量',   layer: 2, color: '#2ecc71', desc: 'MA系统，跟踪趋势强度' }},
    // Layer 1: Outcome
    {{ id: 'price',       label: '价格中枢',     layer: 1, color: '#f5c518', desc: '黄金现货价格' }},
    {{ id: 'trend',       label: '趋势强弱',     layer: 1, color: '#2ecc71', desc: '趋势方向与强度' }},
    {{ id: 'vol',         label: '波动率',        layer: 1, color: '#9b59b6', desc: '历史波动率' }},
    {{ id: 'alloc',       label: '配置价值',     layer: 1, color: '#3498db', desc: '相对其他资产的配置价值' }},
    {{ id: 'insurance',   label: '地缘保险',     layer: 1, color: '#e74c3c', desc: '美元秩序的保险溢价' }},
  ];

  const W = 800, H = 360;
  const svg = d3.select('#topo-svg').attr('viewBox', `0 0 ${{W}} ${{H}}`);

  // Layer X positions
  const lx = l => 70 + (l - 1) * (W - 140) / 3;

  // Assign initial positions
  const nodes = LAYERS.map(n => {{
    const layerNodes = LAYERS.filter(x => x.layer === n.layer);
    const idx = layerNodes.indexOf(n);
    const spacing = (H - 60) / (layerNodes.length + 1);
    return {{
      ...n,
      x: lx(n.layer),
      y: 30 + spacing * (idx + 1),
      fx: lx(n.layer),
      fy: 30 + spacing * (idx + 1),
    }};
  }});

  // Links between layers (adjacent only)
  const links = [];
  for (let l = 4; l >= 2; l--) {{
    const upper = nodes.filter(n => n.layer === l);
    const lower = nodes.filter(n => n.layer === l - 1);
    upper.forEach(u => {{
      lower.forEach(lo => {{
        links.push({{ source: u.id, target: lo.id }});
      }});
    }});
  }}

  // Draw links
  svg.append('g').selectAll('line')
    .data(links)
    .join('line')
    .attr('x1', d => nodes.find(n => n.id === d.source).x)
    .attr('y1', d => nodes.find(n => n.id === d.source).y)
    .attr('x2', d => nodes.find(n => n.id === d.target).x)
    .attr('y2', d => nodes.find(n => n.id === d.target).y)
    .attr('stroke', '#d5cdc2')
    .attr('stroke-width', 0.8)
    .attr('stroke-opacity', 0.5);

  // Draw layer labels
  const layerNames = ['', '结果层', '市场层', '宏观层', '制度层'];
  [1, 2, 3, 4].forEach(l => {{
    svg.append('text')
      .attr('x', lx(l))
      .attr('y', 18)
      .attr('text-anchor', 'middle')
      .attr('font-size', 10)
      .attr('fill', '#8a7d72')
      .text(layerNames[l]);
  }});

  // Draw nodes
  const node = svg.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .attr('transform', d => `translate(${{d.x}},${{d.y}})`)
    .style('cursor', 'pointer')
    .on('click', (event, d) => openPanel(d));

  node.append('circle')
    .attr('r', 22)
    .attr('fill', d => d.color)
    .attr('fill-opacity', 0.2)
    .attr('stroke', d => d.color)
    .attr('stroke-width', 1.5);

  node.append('text')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .attr('font-size', 9)
    .attr('fill', '#2a2520')
    .attr('font-weight', 600)
    .each(function(d) {{
      const words = d.label.split('/');
      if (words.length === 1) {{
        d3.select(this).text(d.label);
      }} else {{
        words.forEach((w, i) => {{
          d3.select(this).append('tspan')
            .attr('x', 0).attr('dy', i * 11 - 4)
            .text(w);
        }});
      }}
    }});

  // Node hover effect
  node.on('mouseover', function(event, d) {{
    d3.select(this).select('circle').attr('fill-opacity', 0.4);
  }}).on('mouseout', function(event, d) {{
    d3.select(this).select('circle').attr('fill-opacity', 0.2);
  }});

  function openPanel(d) {{
    const panel = document.getElementById('topo-panel');
    document.getElementById('panel-title').textContent = d.label;
    document.getElementById('panel-desc').textContent = d.desc;
    document.getElementById('panel-signal').textContent = '';
    document.getElementById('panel-value').textContent = '';
    document.getElementById('panel-date').textContent = '';

    // ── Value lookup by node id ──────────────────────────────────────────
    const v4 = rawData.fiscal_index || {{}};
    const v3 = (rawData.layers && rawData.layers['3_macro']) || {{}};
    const v2 = rawData.four_suits || {{}};
    const v1 = rawData;

    const valMap = {{
      'debt_gdp':    {{ val: v4.debt_gdp_raw,            fmt: v => v != null ? v.toFixed(1) + '%' : '—', date: v4.debt_gdp_date }},
      'deficit_gdp': {{ val: v4.deficit_gdp_raw,         fmt: v => v != null ? v.toFixed(1) + '%' : '—', date: v4.deficit_gdp_date }},
      'interest':    {{ val: rawData.interest_burden,     fmt: v => v != null ? v.toFixed(1) + '%' : '—', date: null }},
      'cb_gold':     {{ val: null,                        fmt: () => '季度数据',                          date: null }},
      'usd_reserve': {{ val: null,                        fmt: () => 'IMF COFER',                          date: null }},
      'real_rate':   {{ val: v3.real_rate,                fmt: v => v != null ? v.toFixed(2) + '%' : '—', date: v3.real_rate_date }},
      'inflation':   {{ val: v3.inflation_exp,            fmt: v => v != null ? v.toFixed(2) + '%' : '—', date: v3.inflation_exp_date }},
      'dxy':         {{ val: v3.dxy,                      fmt: v => v != null ? v.toFixed(1) : '—',       date: v3.dxy_date }},
      'fci':         {{ val: v3.financial_cond,           fmt: v => v != null ? v.toFixed(3) : '—',       date: v3.financial_cond_date }},
      'pce':         {{ val: v3.pce_yoy,                 fmt: v => v != null ? v.toFixed(1) + '%' : '—', date: v3.pce_yoy_date }},
      'unemp':       {{ val: v3.unemployment,             fmt: v => v != null ? v.toFixed(1) + '%' : '—', date: v3.unemployment_date }},
      'gld_etf':     {{ val: v2.gld_etf && v2.gld_etf.shares, fmt: v => v != null ? v.toFixed(1) + 'M' : '—', date: null }},
      'cfct':        {{ val: v2.cfct && v2.cfct.net_long, fmt: v => v != null ? v.toLocaleString() : '—', date: v2.cfct && v2.cfct.week }},
      'gvz':         {{ val: v2.gvz && v2.gvz.value, fmt: v => v != null ? v.toFixed(1) : '—', date: v2.gvz && v2.gvz.date }},
      'momentum':    {{ val: v2.ma_system && v2.ma_system.value, fmt: v => v != null ? '$' + v.toFixed(0) : '—', date: null }},
      'price':       {{ val: v1.gold_price && v1.gold_price.current, fmt: v => v != null ? '$' + v.toFixed(2) : '—', date: null }},
      'trend':       {{ val: v2.ma_system && v2.ma_system.value, fmt: v => v != null ? '$' + v.toFixed(0) : '—', date: null }},
      'vol':         {{ val: null,                        fmt: () => '—',                                  date: null }},
      'alloc':       {{ val: null,                        fmt: () => '框架评估',                           date: null }},
      'insurance':   {{ val: null,                        fmt: () => '定性指标',                            date: null }},
    }};

    const info = valMap[d.id] || {{ val: null, fmt: () => '—', date: null }};
    document.getElementById('panel-value').textContent = info.fmt(info.val);
    if (info.date) {{
      document.getElementById('panel-date').textContent = '更新: ' + info.date;
    }}

    // Signal coloring
    const signalEl = document.getElementById('panel-signal');
    const sig = getSignal(d.id, info.val);
    if (sig) {{
      signalEl.textContent = sig.label;
      signalEl.style.color = sig.color;
    }}

    panel.classList.add('show');
  }}

  // ── Signal interpretation ─────────────────────────────────────────────────
  function getSignal(id, val) {{
    if (val == null) return null;
    const signals = {{
      'debt_gdp':    {{ lo: 60,  hi: 100, label: v => v > 100 ? '高杠杆' : v > 80 ? '中高' : '中等' }},
      'deficit_gdp': {{ lo: 3,   hi: 7,   label: v => v > 5 ? '高赤字' : v > 3 ? '中等' : '可控' }},
      'interest':    {{ lo: 10,  hi: 20,  label: v => v > 15 ? '高利息负担' : v > 10 ? '中等' : '可控' }},
      'real_rate':   {{ lo: 0,   hi: 2,   label: v => v < 0 ? '负实际利率→黄金利好' : v < 1 ? '低实际利率' : '正常' }},
      'dxy':         {{ lo: 90,  hi: 115, label: v => v > 110 ? '强势美元' : v > 100 ? '中等' : '偏弱' }},
      'gvz':         {{ lo: 15,  hi: 25,  label: v => v > 25 ? '高波动' : v > 15 ? '中等' : '低波动' }},
    }};
    const s = signals[id];
    if (!s) return null;
    const v = typeof val === 'number' ? val : parseFloat(val);
    if (isNaN(v)) return null;
    const color = v > s.hi ? '#e74c3c' : v < s.lo ? '#27ae60' : '#f39c12';
    const label = s.label(v);
    return {{ color, label }};
  }}

  window.closePanel = function() {{
    document.getElementById('topo-panel').classList.remove('show');
  }};
}})();
</script>
</body>
</html>
"""


def main():
    data_file = DATA_DIR / "gold_board_data.json"
    if not data_file.exists():
        print(f"[WARN] {data_file} not found — run fetch_gold_board_data.py first")
        # Write empty template
        data = {"updated_at": datetime.now().astimezone().isoformat(), "layers": {}, "fiscal_index": {"score": None, "zone": "unknown"}, "matrix_2x2": {}, "four_suits": {}, "price_history": []}
    else:
        with open(data_file) as f:
            data = json.load(f)

    html = build_html(data)
    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[DONE] Gold board → {HTML_OUT}")


if __name__ == "__main__":
    main()
