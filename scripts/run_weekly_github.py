#!/usr/bin/env python3
"""
Dollar Liquidity Weekly Report — GitHub Actions version
Reads data/liquidity_history.csv → generates content.json + charts + HTML
No AI, no PDF, no macOS deps.
"""
import os, sys, json
from pathlib import Path
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
os.chdir(Path(__file__).parent)
SCRIPT_DIR   = Path(__file__).parent
DATA_DIR     = SCRIPT_DIR.parent / "data"
REPORT_BASE   = SCRIPT_DIR.parent / "docs" / "dollar-liquidity-weekly-report"
DATE_STR      = datetime.now().strftime("%Y%m%d")
WEEK_NUM      = datetime.now().isocalendar()[1]
OUT_DIR       = REPORT_BASE          # charts + HTML at root, not in date subfolder
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PNG_DIR   = REPORT_BASE / "charts"   # shared across all reports
OUT_PNG_DIR.mkdir(parents=True, exist_ok=True)

# ── matplotlib sans-serif ─────────────────────────────────────────────────────
plt.rcParams["font.family"] = ["DejaVu Sans", "Arial", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# ── Load data ─────────────────────────────────────────────────────────────────
df = pd.read_csv(DATA_DIR / "liquidity_history.csv", parse_dates=["date"])
df = df.sort_values("date")

def safe(s, factor=1.0):
    s = pd.to_numeric(s, errors="coerce") * factor
    return s.dropna()

df["SOFR_bp"]      = safe(df["SOFR"]) * 100
df["RRP_M"]        = safe(df["RRPONTTLD"]) * 1000
df["NetLiq_M"]     = safe(df["Net_Liquidity"])
df["NetLiq_T"]     = df["NetLiq_M"] / 1_000_000
df["WALCL_M"]      = safe(df["WALCL"])
df["WALCL_T"]      = df["WALCL_M"] / 1_000_000
df["M2_YoY"]       = safe(df["M2_YoY"])
df["WALCL_YoY"]    = safe(df["WALCL_YoY"])
df["T10Y2Y_bp"]    = safe(df["T10Y2Y"]) * 100
df["DXY"]          = safe(df["DTWEXBGS"])
df["FEDFUNDS_bp"]  = safe(df["FEDFUNDS"]) * 100
df["DFF_bp"]        = safe(df["DFF"]) * 100
df["DFF_bp"]       = df["DFF_bp"].ffill()
df["SOFR_DFF_bp"]  = df["SOFR_bp"] - df["DFF_bp"]

# ── Rating functions (v3.1) ───────────────────────────────────────────────────
def rate_sofr_spread(bp):
    if bp < 5:   return 1, "充裕", "利差<5bp，银行间市场平稳"
    if bp < 15:  return 2, "略紧", "利差5-15bp，季末/月度资金压力"
    if bp < 35:  return 3, "收紧", "利差15-35bp，融资溢价扩大"
    if bp < 50:  return 4, "危险", "利差35-50bp，接近历史日均值峰值"
    return 5, "危机", "利差>50bp，历史日均值峰值"

def rate_ted(bp):
    if bp < 20:  return 1, "正常", f"SOFR-DFF={bp:.0f}bp，<历史P10（LIBOR已停用，以SOFR-DFF替代）"
    if bp < 40:  return 2, "关注", f"SOFR-DFF={bp:.0f}bp，P10-P50"
    if bp < 70:  return 3, "预警", f"SOFR-DFF={bp:.0f}bp，P50-P75"
    if bp < 140: return 4, "紧张", f"SOFR-DFF={bp:.0f}bp，P75-P95"
    return 5, "危机", f"SOFR-DFF={bp:.0f}bp，>P95"

def rate_rrp(millions):
    if millions > 500_000:  return 1, "充裕", f"RRP=${millions/1e6:.1f}T，蓄水池满"
    if millions > 100_000:  return 2, "略紧", f"RRP=${millions/1e6:.1f}T，正常区间"
    if millions > 50_000:   return 3, "收紧", f"RRP=${millions/1e6:.1f}B，蓄水池下降"
    if millions > 5_000:    return 4, "紧张", f"RRP=${millions/1e6:.0f}B，蓄水池接近枯竭"
    return None, "辅助观察", f"RRP=${millions:.0f}M（不参与综合评级）"

def rate_net_liq_wow(current, prev):
    if pd.isna(current) or pd.isna(prev) or prev == 0:
        return 3, "收紧", "数据不可用"
    pct = (current - prev) / prev * 100
    if pct >= 0:   return 1, "充裕", "净流动性扩张"
    if pct > -5:   return 2, "略紧", "净流动性轻微收缩"
    if pct > -10:  return 3, "收紧", "净流动性持续下降"
    if pct > -20:  return 4, "危险", "流动性快速萎缩"
    return 5, "危机", "流动性断崖下滑"

def rate_m2_yoy(pct):
    if pd.isna(pct): return None, None, "数据不可用"
    if pct > 15:  return 2, "过剩", f"M2 YoY={pct:.1f}%，流动性泛滥"
    if pct < 0:   return 5, "危机", f"M2 YoY={pct:.1f}%，货币供给萎缩"
    if pct < 2:   return 4, "危险", f"M2 YoY={pct:.1f}%，信贷收缩"
    if pct < 5:   return 3, "收紧", f"M2 YoY={pct:.1f}%，货币供给偏紧"
    if pct < 10:  return 2, "略紧", f"M2 YoY={pct:.1f}%，增速温和"
    return 1, "充裕", f"M2 YoY={pct:.1f}%，供给充足"

def rate_walcl_yoy(pct):
    if pd.isna(pct): return None, None, "数据不可用"
    if pct > 5:   return 1, "扩表", f"WALCL YoY={pct:.1f}%，QE扩张"
    if pct > 0:   return 2, "略扩", f"WALCL YoY={pct:.1f}%，温和扩表"
    if pct > -5:  return 3, "略缩", f"WALCL YoY={pct:.1f}%，QT初期"
    if pct > -10: return 4, "缩表", f"WALCL YoY={pct:.1f}%，QT持续"
    return 5, "强缩", f"WALCL YoY={pct:.1f}%，激进QT"

def rate_yc(bp):
    if bp > 150:  return 1, "陡峭危机", "利差>150bp，flight-to-safety危机信号"
    if bp > 80:   return 2, "陡峭", "利差>80bp，宽松预期升温"
    if bp > 0:    return 3, "正常", f"利差{bp:.0f}bp，正常区间"
    if bp > -50:  return 4, "倒挂", f"利差{bp:.0f}bp，QT周期正常现象"
    return 5, "深度倒挂", "利差<-50bp，激进QT，非危机"

def rate_dxy(dxy):
    if dxy < 100: return 1, "弱势", "DXY<100，弱势美元"
    if dxy < 109: return 2, "正常偏低", "DXY 100-109"
    if dxy < 116: return 3, "正常", "DXY 109-116"
    if dxy < 121: return 4, "强势", "DXY 116-121，极端区间"
    return 5, "极端强势", "DXY>121，历史P95"

def overall_rating(r_sofr, r_ted, r_nl):
    return max(r_sofr or 0, r_ted or 0, r_nl or 0)

# ── Latest values ─────────────────────────────────────────────────────────────
latest = df.dropna(subset=["SOFR_bp"]).iloc[-1]
sofr_dff_bp = float(latest["SOFR_DFF_bp"])
ted_bp      = sofr_dff_bp
rrp_m       = float(latest["RRP_M"])
nl_curr     = float(latest["NetLiq_M"])
nl_prev     = df.dropna(subset=["NetLiq_M"])["NetLiq_M"].iloc[-2] if len(df.dropna(subset=["NetLiq_M"])) > 1 else None
m2_yoy      = float(df["M2_YoY"].dropna().iloc[-1]) if len(df["M2_YoY"].dropna()) > 0 else None
walcl_yoy   = float(df["WALCL_YoY"].dropna().iloc[-1]) if len(df["WALCL_YoY"].dropna()) > 0 else None
t10y2y_bp   = float(df["T10Y2Y_bp"].dropna().iloc[-1]) if len(df["T10Y2Y_bp"].dropna()) > 0 else None
dxy         = float(df["DXY"].dropna().iloc[-1]) if len(df["DXY"].dropna()) > 0 else None

r_sofr, n_sofr, e_sofr = rate_sofr_spread(sofr_dff_bp)
r_ted,  n_ted,  e_ted  = rate_ted(ted_bp)
r_rrp,  n_rrp,  e_rrp  = rate_rrp(rrp_m)
r_nl,   n_nl,   e_nl   = rate_net_liq_wow(nl_curr, nl_prev) if nl_prev is not None else (3, "收紧", "数据不足")
r_m2,   n_m2,   e_m2   = rate_m2_yoy(m2_yoy)
r_walcl,n_walcl,e_walcl= rate_walcl_yoy(walcl_yoy)
r_yc,   n_yc,   e_yc   = (rate_yc(t10y2y_bp) if t10y2y_bp is not None else (3, "正常", "数据不可用"))
r_dxy,  n_dxy,  e_dxy  = (rate_dxy(dxy) if dxy is not None else (3, "正常", "数据不可用"))
r_overall = overall_rating(r_sofr, r_ted, r_nl)

L_NAMES = {1: "L1 充裕", 2: "L2 略紧", 3: "L3 收紧", 4: "L4 危险", 5: "L5 危机"}

print(f"Latest: SOFR-DFF={sofr_dff_bp:.1f}bp L{r_sofr} | TED={ted_bp:.1f}bp L{r_ted} | RRP=${rrp_m/1e6:.2f}T | NL=${nl_curr/1e6:.2f}T")
print(f"Overall Rating: L{r_overall} {L_NAMES[r_overall]}")

# ── Monthly trend ──────────────────────────────────────────────────────────────
sofr_monthly   = df.groupby(df["date"].dt.to_period("M"))["SOFR_bp"].mean()
sofr_dff_monthly = df.groupby(df["date"].dt.to_period("M"))["SOFR_DFF_bp"].mean()
last_complete_month = sofr_monthly.index[-2] if len(sofr_monthly) > 1 else sofr_monthly.index[-1]

df["yearmonth"] = df["date"].dt.to_period("M")
monthly = df.groupby("yearmonth").apply(
    lambda g: g.dropna(subset=["NetLiq_M"]).iloc[-1] if len(g.dropna(subset=["NetLiq_M"])) > 0 else g.iloc[-1]
)
monthly = monthly[monthly.index <= last_complete_month].tail(6)

m2_yoy_monthly    = df.groupby("yearmonth")["M2_YoY"].last().reindex(monthly.index)
walcl_yoy_monthly = df.groupby("yearmonth")["WALCL_YoY"].last().reindex(monthly.index)
t10y2y_monthly    = df.groupby("yearmonth")["T10Y2Y_bp"].mean().reindex(monthly.index)

month_rows = []
for i, (mo, m_data) in enumerate(monthly.iterrows()):
    mo_str = str(mo)
    nl_t = float(m_data["NetLiq_T"])
    rrp_mo = float(m_data["RRP_M"])
    sofr_mo_bp = float(sofr_dff_monthly.loc[mo]) if mo in sofr_dff_monthly.index else None
    m2_mo = float(m2_yoy_monthly.loc[mo]) if mo in m2_yoy_monthly.index else None
    walcl_mo = float(walcl_yoy_monthly.loc[mo]) if mo in walcl_yoy_monthly.index else None
    t10y_mo = float(t10y2y_monthly.loc[mo]) if mo in t10y2y_monthly.index else None

    # WoW for net liquidity
    month_list = list(monthly.index)
    if i < len(month_list) - 1:
        prev_mo = month_list[len(month_list) - i - 2]
        prev_data = monthly.loc[prev_mo]
        nl_prev_mo = float(prev_data["NetLiq_M"])
        wow_pct = (float(m_data["NetLiq_M"]) - nl_prev_mo) / nl_prev_mo * 100
    else:
        wow_pct = None

    def fmt_v(v, unit):
        if v is None: return "—"
        if unit == "bp": return f"{v:.0f}bp"
        if unit == "T":  return f"${v:.2f}T"
        if unit == "M":  return f"${v:.0f}M"
        if unit == "%":  return f"{v:+.1f}%"
        return str(v)

    r_sofr_m = (rate_sofr_spread(sofr_mo_bp)[0] if sofr_mo_bp is not None else None)
    r_nl_m   = (rate_net_liq_wow(float(m_data["NetLiq_M"]), nl_prev_mo)[0] if wow_pct is not None else None)
    r_rrp_m  = rate_rrp(rrp_mo)[0]

    month_rows.append([
        mo_str, fmt_v(sofr_mo_bp, "bp"), r_sofr_m,
        fmt_v(rrp_mo/1e6, "T"), r_rrp_m,
        fmt_v(nl_t, "T"), r_nl_m,
        fmt_v(m2_mo, "%"), (rate_m2_yoy(m2_mo)[0] if m2_mo is not None else None),
        fmt_v(walcl_mo, "%"), (rate_walcl_yoy(walcl_mo)[0] if walcl_mo is not None else None),
        fmt_v(t10y_mo, "bp"), (rate_yc(t10y_mo)[0] if t10y_mo is not None else None),
    ])

# ── Charts ───────────────────────────────────────────────────────────────────
def plot_line(dates, values, label, color, out_path, y_fmt=None):
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.plot(dates, values, color=color, linewidth=1.5)
    ax.fill_between(dates, values, alpha=0.15, color=color)
    ax.set_ylabel(label, fontsize=9)
    ax.tick_params(labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=30)
    ax.grid(alpha=0.3, linewidth=0.5)
    if y_fmt:
        ax.yaxis.set_major_formatter(y_fmt)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  ✓ {out_path.name}")

from matplotlib.ticker import FuncFormatter
def billions(x, pos): return f"${x:.0f}B"
def trillions(x, pos): return f"${x:.1f}T"

# Chart 1: SOFR-DFF Spread
d_sofr = df.dropna(subset=["SOFR_DFF_bp"])["date"]
v_sofr = df.dropna(subset=["SOFR_DFF_bp"])["SOFR_DFF_bp"]
plot_line(d_sofr, v_sofr, "SOFR-DFF Spread (bp)", "#2196F3",
          OUT_PNG_DIR / "sofr-dff-spread.png")

# Chart 2: RRP Balance
d_rrp = df.dropna(subset=["RRP_M"])["date"]
v_rrp = df.dropna(subset=["RRP_M"])["RRP_M"] / 1_000
plot_line(d_rrp, v_rrp, "RRP Balance ($B)", "#FF5722",
          OUT_PNG_DIR / "rrp-balance.png", FuncFormatter(billions))

# Chart 3: Net Liquidity
d_nl = df.dropna(subset=["NetLiq_T"])["date"]
v_nl = df.dropna(subset=["NetLiq_T"])["NetLiq_T"]
plot_line(d_nl, v_nl, "Net Liquidity ($T)", "#4CAF50",
          OUT_PNG_DIR / "net-liquidity.png", FuncFormatter(trillions))

# Chart 4: M2 + WALCL YoY
fig, ax = plt.subplots(figsize=(7, 3.2))
ax2 = ax.twinx()
d_m2 = df.dropna(subset=["M2_YoY"])["date"]
v_m2 = df.dropna(subset=["M2_YoY"])["M2_YoY"]
d_walcl = df.dropna(subset=["WALCL_YoY"])["date"]
v_walcl = df.dropna(subset=["WALCL_YoY"])["WALCL_YoY"]
ax.plot(d_m2, v_m2, color="#9C27B0", linewidth=1.5, label="M2 YoY")
ax2.plot(d_walcl, v_walcl, color="#00BCD4", linewidth=1.5, linestyle="--", label="WALCL YoY")
ax.axhline(0, color="gray", linewidth=0.5, linestyle=":")
ax.set_ylabel("M2 YoY (%)", fontsize=9, color="#9C27B0")
ax2.set_ylabel("WALCL YoY (%)", fontsize=9, color="#00BCD4")
ax.tick_params(labelsize=8)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
plt.xticks(rotation=30)
ax.grid(alpha=0.3, linewidth=0.5)
lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper right")
fig.tight_layout()
fig.savefig(OUT_PNG_DIR / "m2-walcl-yoy.png", dpi=150)
plt.close(fig)
print(f"  ✓ m2-walcl-yoy.png")

# Chart 5: Yield Curve + DXY
fig, ax = plt.subplots(figsize=(7, 3.2))
ax2 = ax.twinx()
d_yc = df.dropna(subset=["T10Y2Y_bp"])["date"]
v_yc = df.dropna(subset=["T10Y2Y_bp"])["T10Y2Y_bp"]
d_dxy = df.dropna(subset=["DXY"])["date"]
v_dxy = df.dropna(subset=["DXY"])["DXY"]
ax.plot(d_yc, v_yc, color="#FF9800", linewidth=1.5, label="10Y-2Y (bp)")
ax2.plot(d_dxy, v_dxy, color="#795548", linewidth=1.5, linestyle="--", label="DXY Index")
ax.axhline(0, color="gray", linewidth=0.5, linestyle=":")
ax.set_ylabel("10Y-2Y Spread (bp)", fontsize=9, color="#FF9800")
ax2.set_ylabel("DXY Index", fontsize=9, color="#795548")
ax.tick_params(labelsize=8)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
plt.xticks(rotation=30)
ax.grid(alpha=0.3, linewidth=0.5)
lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper right")
fig.tight_layout()
fig.savefig(OUT_PNG_DIR / "yc-dxy.png", dpi=150)
plt.close(fig)
print(f"  ✓ yc-dxy.png")

# Chart 6: TED Spread (same as SOFR-DFF)
plot_line(d_sofr, v_sofr, "TED / SOFR-DFF (bp)", "#E91E63",
          OUT_PNG_DIR / "ted-spread.png")

# ── content.json ──────────────────────────────────────────────────────────────
def _h1(t): return {"type": "h1", "text": t}
def _h2(t): return {"type": "h2", "text": t}
def _h3(t): return {"type": "h3", "text": t}
def _body(t): return {"type": "body", "text": t}
def _sp(pt=8): return {"type": "spacer", "pt": pt}
def _pb(): return {"type": "pagebreak"}
def _img(path, caption=""):
    return {"type": "image", "path": path, "caption": caption}
def _tbl(headers, rows):
    return {"type": "table", "headers": headers, "rows": rows}

primary_rows = [
    ["SOFR-DFF利差", f"{sofr_dff_bp:.1f}bp", f"L{r_sofr} {n_sofr}", e_sofr],
    ["TED利差", f"{ted_bp:.1f}bp", f"L{r_ted} {n_ted}", "LIBOR已停用，以SOFR-DFF替代"],
    ["RRP余额", f"${rrp_m/1e6:.2f}T", f"L{r_rrp} {n_rrp}", e_rrp],
    ["净流动性", f"${nl_curr/1e6:.2f}T", f"L{r_nl} {n_nl}", e_nl],
]
secondary_rows = [
    ["M2同比", f"{m2_yoy:.2f}%" if m2_yoy is not None else "—", f"L{r_m2} {n_m2}" if r_m2 else "—", e_m2],
    ["WALCL同比", f"{walcl_yoy:.2f}%" if walcl_yoy is not None else "—", f"L{r_walcl} {n_walcl}" if r_walcl else "—", e_walcl],
    ["10Y-2Y利差", f"{t10y2y_bp:.0f}bp" if t10y2y_bp is not None else "—", f"L{r_yc} {n_yc}" if r_yc else "—", e_yc],
    ["美元指数DXY", f"{dxy:.2f}" if dxy is not None else "—", f"L{r_dxy} {n_dxy}" if r_dxy else "—", "FRED贸易加权Broad指数(DTWEXBGS)，非ICE DXY"],
]

monthly_headers = ["月份", "SOFR-DFF", "R", "RRP余额", "R", "净流动性", "R", "M2同比", "R", "WALCL同比", "R", "10Y-2Y", "R"]
monthly_rows_clean = []
for row in month_rows:
    r = []
    for j, val in enumerate(row):
        if j == 2 or j == 5 or j == 7 or j == 9 or j == 11:  # rating cols
            r.append(f"L{val}" if val is not None else "—")
        else:
            r.append(val)
    monthly_rows_clean.append(r)

blocks = [
    _h1(f"美元流动性周度分析 W{WEEK_NUM}"),
    _sp(8),
    _h2("一、综合评级"),
    _body(f"<b>综合评级：L{r_overall} {L_NAMES[r_overall]}</b>（SOFR-DFF L{r_sofr} · TED L{r_ted} · 净流动性 L{r_nl}）"),
    _sp(4),
    _h2("二、一级指标当前值"),
    _tbl(["指标", "最新值", "评级", "备注"], primary_rows),
    _sp(4),
    _h3("一级指标说明"),
    _body(f"<b>SOFR-DFF利差</b>（当前: {sofr_dff_bp:.1f}bp）：SOFR与有效联邦基金利率(DFF)之差，反映银行间担保融资市场的信用溢价。FRED SOFR为日均值，>50bp为2020 COVID实测危机级别。"),
    _body(f"<b>TED利差</b>（当前: {ted_bp:.1f}bp）：LIBOR已于2022-01-21停用；当前以SOFR-DFF日频利差替代，不代表原始LIBOR口径TED利差。"),
    _body(f"<b>美联储净流动性</b>（当前: ${nl_curr/1e6:.2f}T）：美联储总资产(WALCL)减财政部一般账户(TGA)减RRP余额，反映货币政策与财政政策合力的基础流动性供给。"),
    _sp(8),
    _h2("三、二级指标当前值"),
    _tbl(["指标", "当前值", "评级", "说明"], secondary_rows),
    _sp(4),
    _h3("二级指标说明"),
    _body(f"<b>M2同比增速</b>（当前: {m2_yoy:.2f}%）{e_m2}"),
    _body(f"<b>WALCL同比</b>（当前: {walcl_yoy:.2f}%）{e_walcl}"),
    _body(f"<b>10Y-2Y利差</b>（当前: {t10y2y_bp:.0f}bp）{e_yc}"),
    _body(f"<b>美元指数DXY</b>（当前: {dxy:.2f}）{e_dxy}"),
    _sp(8),
    _h2("四、月度趋势"),
    _tbl(monthly_headers, monthly_rows_clean),
    _sp(8),
    _h2("五、图表"),
    _img(str(OUT_PNG_DIR / "sofr-dff-spread.png"), "SOFR-DFF利差历史（bp）"),
    _sp(4),
    _img(str(OUT_PNG_DIR / "rrp-balance.png"), "隔夜逆回购余额（$B）"),
    _sp(4),
    _img(str(OUT_PNG_DIR / "net-liquidity.png"), "美联储净流动性（$T）"),
    _sp(4),
    _img(str(OUT_PNG_DIR / "m2-walcl-yoy.png"), "M2同比 + WALCL同比（%）"),
    _sp(4),
    _img(str(OUT_PNG_DIR / "yc-dxy.png"), "10Y-2Y利差 + DXY指数"),
    _sp(4),
    _img(str(OUT_PNG_DIR / "ted-spread.png"), "TED利差 / SOFR-DFF（bp）"),
    _sp(8),
    _h1("附录"),
    _h2("评级阈值速查表"),
    _h3("（一）一级指标（主导综合评级，取最差值）"),
    _body("<b>SOFR-DFF 利差（日均值）</b>"),
    _tbl(["区间", "评级", "含义"],
         [["<5bp","L1","充裕，正常宽松"],
          ["5–15bp","L2","温和，货币市场轻微收紧"],
          ["15–35bp","L3","关注，流动性收紧信号"],
          ["35–50bp","L4","警惕，银行间压力上升"],
          [">50bp","L5","危机（2020 COVID峰值约50bp）"]]),
    _body(f"当前: {sofr_dff_bp:.1f}bp → L{r_sofr} {n_sofr}"),
    _sp(4),
    _body("<b>TED 利差（LIBOR已停用，以SOFR-DFF替代）</b>"),
    _tbl(["区间", "评级", "含义"],
         [["<20bp","L1","充裕（历史P10）"],
          ["20–40bp","L2","温和（历史P25）"],
          ["40–70bp","L3","关注（历史P50–P75）"],
          ["70–140bp","L4","警惕（历史P95）"],
          [">140bp","L5","危机（2008 GFC峰值458bp）"]]),
    _body(f"当前: {ted_bp:.1f}bp → L{r_ted} {n_ted}"),
    _sp(4),
    _body("<b>美联储净流动性（WALCL − TGA − RRP）</b>"),
    _tbl(["区间", "评级", "含义"],
         [[">6.5T","L1","QE大规模放水"],
          ["5.5–6.5T","L2","正常区间"],
          ["4.5–5.5T","L3","QT进行中"],
          ["3.5–4.5T","L4","深度QT"],
          ["<3.5T","L5","极度收紧"]]),
    _body(f"当前: ${nl_curr/1e6:.2f}T → L{r_nl} {n_nl}"),
    _sp(8),
    _h3("（二）二级指标（辅助验证，不参与综合评级）"),
    _body("<b>WALCL 同比变化</b>"),
    _tbl(["区间", "信号"],
         [[">10%","L1 QE大扩表"],
          ["5–10%","L2 温和扩张"],
          ["0–5%","L3 正常"],
          ["-5–0%","L4 QT进行中"],
          ["<-5%","L5 深度QT"]]),
    _body(f"当前: WALCL同比 {walcl_yoy:.2f}% → L{r_walcl} {n_walcl}" if walcl_yoy is not None else "当前: WALCL同比 —"),
    _sp(4),
    _body("<b>M2 同比变化</b>"),
    _tbl(["区间", "信号"],
         [[">15%","L1 超级QE"],
          ["10–15%","L2 扩张"],
          ["5–10%","L3 正常"],
          ["0–5%","L4 收紧"],
          ["<0%","L5 收缩"]]),
    _body(f"当前: M2同比 {m2_yoy:.2f}% → L{r_m2} {n_m2}" if m2_yoy is not None else "当前: M2同比 —"),
    _sp(4),
    _body("<b>10Y-2Y 收益率曲线利差</b>"),
    _tbl(["区间", "信号"],
         [[">150bp","L1 正常陡峭（危机前兆）"],
          ["50–150bp","L2 正常至接近倒挂"],
          ["0–50bp","L3 接近倒挂"],
          ["-50–0bp","L4 倒挂（QT周期正常现象）"],
          ["<-50bp","L5 深度倒挂（激进QT，非危机）"]]),
    _body(f"当前: {t10y2y_bp:.0f}bp → L{r_yc} {n_yc}。注：倒挂≠危机。方向比绝对值更重要。" if t10y2y_bp is not None else "当前: 10Y-2Y —"),
    _sp(4),
    _body("<b>RRP 隔夜逆回购余额（辅助观察）</b>"),
    _tbl(["余额", "信号"],
         [[">1.0T","流动性冗余淤积"],
          ["0.5–1.0T","正常区间"],
          ["0.1–0.5T","缓冲量减少，流动性流入市场"],
          ["<0.1T","极低（需结合情境判断含义）"]]),
    _body(f"当前: ${rrp_m/1e6:.2f}T → 辅助观察"),
    _sp(4),
    _body("<b>DXY 美元指数（FRED贸易加权Broad）</b>"),
    _tbl(["区间", "信号"],
         [["<100","L1 弱势美元"],
          ["100–109","L2 正常偏低"],
          ["109–116","L3 正常"],
          ["116–121","L4 强势"],
          [">121","L5 极端强势（历史P95）"]]),
    _body(f"当前: DXY {dxy:.2f} → L{r_dxy} {n_dxy}" if dxy is not None else "当前: DXY —"),
    _sp(8),
    _h1("数据来源"),
    _body("SOFR: FRED SOFR | RRP余额: FRED RRPONTTLD（辅助观察） | 净流动性: FRED WALCL - WTREGEN - RRPONTTLD | M2同比: FRED M2SL | WALCL同比: FRED WALCL | 10Y-2Y: FRED T10Y2Y | 美元指数: FRED DTWEXBGS"),
    _body("框架说明: Dollar Liquidity Theory Framework v3.1"),
]

print(f"  ✓ content.json generated (in-memory, not saved to disk)")

# ── HTML generation ──────────────────────────────────────────────────────────
def render_element(el):
    t = el.get("type")
    if t == "h1": return f"<h1>{el['text']}</h1>"
    if t == "h2": return f"<h2>{el['text']}</h2>"
    if t == "h3": return f"<h3>{el['text']}</h3>"
    if t == "body": return f"<p>{el['text']}</p>"
    if t == "spacer": return f"<div style=\"height:{el.get('pt',8)}px\"></div>"
    if t == "pagebreak": return '<hr class="page-break">'
    if t == "table":
        th = "".join(f"<th>{h}</th>" for h in el.get("headers", []))
        td_rows = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
                          for row in el.get("rows", []))
        return f'<table class="report-table"><thead><tr>{th}</tr></thead><tbody>{td_rows}</tbody></table>'
    if t == "image":
        filename = Path(el.get("path", "")).name
        return f'<figure><img src="charts/{filename}" alt="{el.get("caption","")}"><figcaption>{el.get("caption","")}</figcaption></figure>'
    return ""

body_html = "".join(render_element(b) for b in blocks)

report_display_date = f"2026-W{WEEK_NUM} · {datetime.now().strftime('%Y年%m月%d日')}"
html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>美元流动性周度分析 {report_display_date}</title>
  <style>
    :root {{
      --bg: #0d1117; --card: #161b22; --border: #30363d;
      --text: #e6edf3; --text-muted: #8b949e; --accent: #58a6ff;
      --l1: #3fb950; --l2: #d29922; --l3: #f0883e; --l4: #f85149; --l5: #da3633;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.7; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 2rem; }}
    header {{ margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem; }}
    h1 {{ font-size: 1.75rem; color: var(--accent); margin-bottom: 0.5rem; }}
    h2 {{ font-size: 1.25rem; color: var(--text); margin: 1.5rem 0 0.75rem; border-left: 3px solid var(--accent); padding-left: 0.75rem; }}
    h3 {{ font-size: 1rem; color: var(--text-muted); margin: 1rem 0 0.5rem; }}
    p {{ margin-bottom: 0.75rem; }}
    .report-table {{ width: 100%; border-collapse: collapse; margin: 0.75rem 0; font-size: 0.9rem; }}
    .report-table th {{ background: var(--card); color: var(--text-muted); padding: 0.6rem 0.75rem; text-align: left; border: 1px solid var(--border); font-weight: 500; }}
    .report-table td {{ padding: 0.5rem 0.75rem; border: 1px solid var(--border); vertical-align: top; }}
    .report-table tr:hover td {{ background: rgba(88,166,255,0.05); }}
    figure {{ margin: 1rem 0; text-align: center; }}
    figure img {{ max-width: 100%; height: auto; border-radius: 6px; border: 1px solid var(--border); }}
    figcaption {{ font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem; }}
    footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border); text-align: center; color: var(--text-muted); font-size: 0.75rem; }}
    .nav {{ margin-bottom: 1.5rem; }}
    .nav a {{ color: var(--accent); text-decoration: none; font-size: 0.875rem; }}
    .nav a:hover {{ text-decoration: underline; }}
    .rating-L1 {{ color: var(--l1); font-weight: bold; }}
    .rating-L2 {{ color: var(--l2); font-weight: bold; }}
    .rating-L3 {{ color: var(--l3); font-weight: bold; }}
    .rating-L4 {{ color: var(--l4); font-weight: bold; }}
    .rating-L5 {{ color: var(--l5); font-weight: bold; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="nav"><a href="./">← 周报目录</a> <a href="../">← 指标主页</a></div>
    <header>
      <h1>美元流动性周度分析</h1>
      <p style="color:var(--text-muted);font-size:0.9rem">{report_display_date} | Framework v3.1</p>
    </header>
    {body_html}
    <footer>
      <p>数据来源：FRED (Federal Reserve Economic Data) | 框架：Dollar Liquidity Theory v3.1</p>
    </footer>
  </div>
</body>
</html>'''

html_path = REPORT_BASE / f"{DATE_STR}.html"
html_path.write_text(html, encoding="utf-8")
print(f"  ✓ HTML saved: {html_path.name}")

# Also generate index listing
index_html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>美元流动性周报</title>
  <style>
    :root {{ --bg: #0d1117; --card: #161b22; --border: #30363d; --text: #e6edf3; --text-muted: #8b949e; --accent: #58a6ff; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
    .container {{ max-width: 900px; margin: 0 auto; padding: 2rem; }}
    header {{ margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem; }}
    h1 {{ color: var(--accent); font-size: 1.75rem; margin-bottom: 0.5rem; }}
    .subtitle {{ color: var(--text-muted); font-size: 0.9rem; }}
    .back {{ margin-bottom: 1.5rem; }}
    .back a {{ color: var(--accent); text-decoration: none; font-size: 0.875rem; }}
    .back a:hover {{ text-decoration: underline; }}
    .report-list {{ display: flex; flex-direction: column; gap: 1rem; }}
    .report-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem 1.5rem; transition: border-color 0.2s; }}
    .report-card:hover {{ border-color: var(--accent); }}
    .report-card a {{ text-decoration: none; color: var(--text); display: block; }}
    .report-date {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 0.25rem; }}
    .report-meta {{ font-size: 0.8rem; color: var(--text-muted); }}
    footer {{ margin-top: 3rem; text-align: center; color: var(--text-muted); font-size: 0.75rem; border-top: 1px solid var(--border); padding-top: 1rem; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="back"><a href="../">← 返回首页</a></div>
    <header>
      <h1>美元流动性周度分析</h1>
      <p class="subtitle">Dollar Liquidity Weekly Report · Framework v3.1</p>
    </header>
    <div class="report-list">
      <div class="report-card">
        <a href="{DATE_STR}.html">
          <div class="report-date">2026-W{WEEK_NUM} · {datetime.now().strftime('%Y年%m月%d日')} <span style="color:var(--accent)">L{r_overall} {L_NAMES[r_overall]}</span></div>
          <div class="report-meta">综合评级 L{r_overall} | SOFR-DFF: {sofr_dff_bp:.1f}bp (L{r_sofr}) | 净流动性: ${nl_curr/1e6:.2f}T (L{r_nl})</div>
        </a>
      </div>
    </div>
    <footer>
      <p>数据来源：FRED | 框架：Dollar Liquidity Theory v3.1</p>
    </footer>
  </div>
</body>
</html>'''

index_path = REPORT_BASE / "index.html"
index_path.write_text(index_html, encoding="utf-8")
print(f"  ✓ Index saved")

print(f"\n[DONE] Weekly report generated: {DATE_STR}")
