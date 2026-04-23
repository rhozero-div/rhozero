# Round 3 待完成清单

**生成时间：** 2026-04-26
**状态：** 部分完成，代码已修改但未验证

---

## P0 — 必须完成

### 1. interest_burden 重算 fiscal_index
**文件：** `scripts/fetch_gold_board_data.py`

**问题：** calc_fiscal_index 里的 d3 阈值（`(interest-5)/15*35`）是为旧错误数据设计的。
- 新正确 interest_burden ≈ 22.6%
- 按旧公式：d3 = (22.6-5)/15*35 = 41.2
- 导致总分 ≈ 29+15+41 = 85 → 直接进 Crisis 区间
- 老钱原文总分 67.8，对应 interest_burden ≈ 18.5%

**需要 Chris 判断：**
- 阈值是否需要重新标定？
- 还是接受当前公式让评分更敏感？
Chris: 接受当前公式
---

### 2. 本地 fetch 验证
```bash
cd ~/hermes/projects/GitHub-Pages
FRED_API_KEY=25c071b9d060642abadc96004737d7f4 python3 scripts/fetch_gold_board_data.py
```

验证目标：
- [ ] interest_burden ≈ 22.6%
- [ ] CFTC net_long 有数值（非 null）
- [ ] GLD percentile 有数值
- [ ] PCEPI history 存入 series_history.pcepi

---

## P1 — 建议完成

### 3. Fiscal chart 修复
**文件：** `scripts/build_gold_board.py`（Panel 5 JS 部分）

**问题：** FYFSD=Annual 无法与 GFDEGDQ188S=Quarterly 混在同一个季度折线图里。当前实现把 FYFSD 当季度点注入，造成时间轴错位。

**方案：** 图表改为债务/GDP 单独折线，赤字/GDP 仅标注在最新季度位置。
Chris: 同意

---

### 4. interest_burden 卡片显示
**文件：** `scripts/build_gold_board.py`（宏观指标区）

**问题：** "利息/收入占比" 卡片目前数据为 null（FYONET 问题）。NA000308Q 已修复，但卡片还未更新显示正确值。
Chris：好

---

## P2 — 可选

| # | 任务 | 说明 |
|---|------|------|
| 5 | 拓扑图节点点击显示数值 | D3 点击交互增强 |
| 6 | 导出 PNG | 看板一键导出高清图 |
| 7 | 移动端响应式 | CSS 适配手机 |
Chris：只做5，6和7先不做

---

## 已完成修改（代码层面）

| 功能 | 状态 | 备注 |
|------|------|------|
| interest_burden 数据源修复 | ✅ | FYONET → NA000308Q 季度求和 |
| CFTC COT 抓取 | ✅ | fetch_cftc_cot() 已写入 |
| GLD ETF 分位数 | ✅ | fetch_gld_holdings() 返回 dict |
| PCEPI 历史存储 | ✅ | hist_configs 新增 pcepi |
| Panel 4 PCE YoY JS 计算 | ✅ | computePceYoy() 函数 |
| 四件套 CFTC 展示 | ✅ | 显示 net_long+week |
| 四件套 GLD 展示 | ✅ | 显示 shares+percentile |

---

## 关键数据对照

| 指标 | 当前实现 | 目标值 |
|------|----------|--------|
| interest_burden | null（FYONET错误） | ≈ 22.6%（NA000308Q） |
| deficit_gdp | 6.5% | 6.5%（FYFSD 正确） |
| debt_gdp | 122.6% | 122.6%（GFDEGDQ188S） |
| fiscal_index 评分 | 44.3 | 需重新计算（取决于阈值） |
| CFTC 净多头 | null | 需抓取验证 |
| GLD percentile | null | 需抓取验证 |
