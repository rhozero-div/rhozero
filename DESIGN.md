# RhoZero GitHub Pages — Design Specification

## Color System

All pages share a unified warm cream + muted brown palette.

### CSS Variables

```css
:root {
  --bg:         #f5f0e8;   /* warm cream background */
  --card:       #faf7f2;   /* slightly lighter card surface */
  --border:     #e0d8cc;   /* soft warm border */
  --text:       #2a2520;   /* deep warm charcoal */
  --text-muted: #8a7d72;   /* muted warm gray for secondary text */
  --accent:     #8B5A2B;   /* muted sienna brown — links, highlights, CTA */
  --up:         #2d8a4e;   /* positive / gain */
  --down:       #c0392b;   /* negative / loss */
}
```

### Usage by Role

| Variable | Hex | Usage |
|----------|-----|-------|
| `--bg` | `#f5f0e8` | Page background |
| `--card` | `#faf7f2` | Card / panel backgrounds |
| `--border` | `#e0d8cc` | Borders, dividers |
| `--text` | `#2a2520` | Body text, headings |
| `--text-muted` | `#8a7d72` | Captions, secondary info, dates |
| `--accent` | `#8B5A2B` | Links, hover states, CTA buttons, chart accent |
| `--up` | `#2d8a4e` | Positive values, green |
| `--down` | `#c0392b` | Negative values, red |

### Level Colors (Liquidity Dashboard)

| Level | Hex | Meaning |
|-------|-----|---------|
| L1 | `#3fb950` |宽松 |
| L2 | `#d29922` |正常偏松 |
| L3 | `#f0883e` |正常偏紧 |
| L4 | `#f85149` |紧张 |
| L5 | `#da3633` |危机 |

### Migration Notes

- **2026-04-22**: Unified from dark theme to warm cream. All pages now share the `:root` vars above.
- `--accent` replaced `#c4922a` (bright gold) → `#8B5A2B` (sienna brown) for a more mature, understated tone.
- `gold.html` had a double-brace CSS syntax bug (`{{` in `<style>` tag) — fixed to valid `{ }` so the theme actually applies.

### Applying the Theme to New Pages

Copy the `:root` block into your `<style>` tag and use CSS variables throughout. Do not hardcode hex colors — use the variables so future theme changes propagate automatically.

```html
<style>
  :root {
    --bg: #f5f0e8; --card: #faf7f2; --border: #e0d8cc;
    --text: #2a2520; --text-muted: #8a7d72; --accent: #8B5A2B;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
</style>
```

## Typography

- Font stack: `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
- No external font dependencies (pure system fonts)
- Line height: `1.6`–`1.7` for body text

## Chart.js Integration

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
```

## File Structure

```
docs/
├── index.html                              # Homepage
├── demo/
│   └── gold.html                           # Gold price demo (Chart.js + news + AI button)
├── implementation/
│   └── index.html                          # Dollar Liquidity Theory implementation
└── dollar-liquidity-weekly-report/
    ├── index.html                          # Report archive listing
    └── 20260421.html                       # W17 2026 weekly report
```

## Deployment

- Platform: GitHub Pages
- Source: `/docs` folder served as site root
- Auto-update: GitHub Actions runs daily at 09:00 UTC, fetches live market data and pushes updated HTML
