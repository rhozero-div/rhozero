#!/usr/bin/env python3
"""
Build weekly liquidity report HTML from content.json.
Outputs to docs/weekly/{date}.html
"""
import json
import os
import sys
from datetime import datetime

REPORT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'dollar-liquidity-theory', 'weekly')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs', 'weekly')

def render_table(headers, rows):
    th = ''.join(f'<th>{h}</th>' for h in headers)
    td_rows = ''
    for row in rows:
        td_rows += '<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>'
    return f'<table class="report-table"><thead><tr>{th}</tr></thead><tbody>{td_rows}</tbody></table>'

def render_element(el, report_date):
    t = el.get('type')
    if t == 'h1':
        return f'<h1>{el["text"]}</h1>'
    elif t == 'h2':
        return f'<h2>{el["text"]}</h2>'
    elif t == 'h3':
        return f'<h3>{el["text"]}</h3>'
    elif t == 'body':
        return f'<p>{el["text"]}</p>'
    elif t == 'table':
        return render_table(el.get('headers', []), el.get('rows', []))
    elif t == 'spacer':
        return f'<div style="height:{el.get("pt", 8)}px"></div>'
    elif t == 'pagebreak':
        return '<hr class="page-break">'
    elif t == 'image':
        # Relative to report dir
        img_path = el.get('path', '')
        caption = el.get('caption', '')
        # Convert absolute path to relative path for web
        filename = os.path.basename(img_path)
        return f'<figure><img src="charts/{filename}" alt="{caption}"><figcaption>{caption}</figcaption></figure>'
    return ''

def build_html(content_json_path, report_date):
    with open(content_json_path) as f:
        blocks = json.load(f)

    body = ''
    for block in blocks:
        body += render_element(block, report_date)

    html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>美元流动性周度分析 {report_date}</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card: #161b22;
      --border: #30363d;
      --text: #e6edf3;
      --text-muted: #8b949e;
      --accent: #58a6ff;
      --l1: #3fb950;
      --l2: #d29922;
      --l3: #f0883e;
      --l4: #f85149;
      --l5: #da3633;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.7; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 2rem; }}
    
    header {{ margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem; }}
    h1 {{ font-size: 1.75rem; color: var(--accent); margin-bottom: 0.5rem; }}
    h2 {{ font-size: 1.25rem; color: var(--text); margin: 1.5rem 0 0.75rem; border-left: 3px solid var(--accent); padding-left: 0.75rem; }}
    h3 {{ font-size: 1rem; color: var(--text-muted); margin: 1rem 0 0.5rem; }}
    p {{ margin-bottom: 0.75rem; color: var(--text); }}
    
    .report-table {{ width: 100%; border-collapse: collapse; margin: 0.75rem 0; font-size: 0.9rem; }}
    .report-table th {{ background: var(--card); color: var(--text-muted); padding: 0.6rem 0.75rem; text-align: left; border: 1px solid var(--border); font-weight: 500; }}
    .report-table td {{ padding: 0.5rem 0.75rem; border: 1px solid var(--border); vertical-align: top; }}
    .report-table tr:hover td {{ background: rgba(88,166,255,0.05); }}
    
    figure {{ margin: 1rem 0; text-align: center; }}
    figure img {{ max-width: 100%; height: auto; border-radius: 6px; border: 1px solid var(--border); }}
    figcaption {{ font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem; }}
    
    .page-break {{ border: none; border-top: 1px solid var(--border); margin: 2rem 0; page-break-after: always; }}
    
    .rating-L1 {{ color: var(--l1); font-weight: bold; }}
    .rating-L2 {{ color: var(--l2); font-weight: bold; }}
    .rating-L3 {{ color: var(--l3); font-weight: bold; }}
    .rating-L4 {{ color: var(--l4); font-weight: bold; }}
    .rating-L5 {{ color: var(--l5); font-weight: bold; }}
    
    footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border); text-align: center; color: var(--text-muted); font-size: 0.75rem; }}
    .nav {{ margin-bottom: 1.5rem; }}
    .nav a {{ color: var(--accent); text-decoration: none; font-size: 0.875rem; }}
    .nav a:hover {{ text-decoration: underline; }}
    
    @media print {{
      .page-break {{ page-break-after: always; }}
      body {{ background: white; color: black; }}
      .report-table th {{ background: #f0f0f0 !important; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="nav"><a href="../">← 返回首页</a></div>
    <header>
      <h1>美元流动性周度分析</h1>
      <p style="color:var(--text-muted);font-size:0.9rem">报告日期：{report_date} | 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
    </header>
    {body}
    <footer>
      <p>数据来源：FRED (Federal Reserve Economic Data) | 框架：Dollar Liquidity Theory v3.1</p>
    </footer>
  </div>
</body>
</html>'''
    return html

def main():
    # Find latest report
    weekly_base = os.path.join(os.path.dirname(__file__), '..', '..', 'dollar-liquidity-theory', 'weekly')
    
    # Get date from command line or use latest
    if len(sys.argv) > 1:
        report_date = sys.argv[1]
    else:
        # Find latest
        dirs = sorted([d for d in os.listdir(weekly_base) if d.isdigit()], reverse=True)
        report_date = dirs[0] if dirs else datetime.now().strftime('%Y%m%d')
    
    content_json = os.path.join(weekly_base, report_date, 'content.json')
    charts_dir = os.path.join(weekly_base, report_date, 'charts')
    
    if not os.path.exists(content_json):
        print(f"[ERROR] Report not found: {content_json}")
        sys.exit(1)
    
    # Copy charts to docs/weekly/charts
    output_charts = os.path.join(OUTPUT_DIR, 'charts')
    os.makedirs(output_charts, exist_ok=True)
    if os.path.exists(charts_dir):
        import shutil
        for f in os.listdir(charts_dir):
            if f.endswith('.png'):
                shutil.copy(os.path.join(charts_dir, f), os.path.join(output_charts, f))
    
    # Build HTML
    html = build_html(content_json, report_date)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f'{report_date}.html')
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"[DONE] {output_path}")

if __name__ == '__main__':
    main()
