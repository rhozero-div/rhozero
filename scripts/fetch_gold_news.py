#!/usr/bin/env python3
"""
Fetch gold news via RSS — direct article URLs, reliable sources only.
Primary: Gold Eagle (gold specialist)
Secondary: Mining.com (filter for gold), Bloomberg (strict filter)
"""
import json
import re
import time
import feedparser
from datetime import datetime
from pathlib import Path
import requests

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = DATA_DIR / "gold_news.json"

RSS_FEEDS = [
    # (name, url, max_items, gold_only)
    ("Gold Eagle",    "https://www.gold-eagle.com/rss.xml",        6, True),   # gold specialist
    ("Mining.com",   "https://www.mining.com/feed/",              4, True),   # gold/mining
    ("Bloomberg",    "https://feeds.bloomberg.com/markets/news.rss", 3, True),  # filter for gold
]

# Must contain at least one of these
GOLD_KW = [
    "gold", "xau", "gold futures", "spot gold", "gold price",
    "precious metal", "gold bullion", "gold market", "gold rally",
    "gold surged", "gold fell", "gold mining", "gold miner",
    "comex gold", "lbma", "safe haven", "central bank gold",
    "gold etf", "gld", "gold bar", "gold silver"
]
# Exclude these even if gold keywords appear
EXCLUDE_KW = ["oil ", "crude oil", "natural gas", "wheat ", "corn ", "soybean",
              "copper ", "aluminum", "iron ore", "coal ", "lithium", "zinc ", "uranium"]


def is_gold(text):
    t = text.lower()
    has = any(kw.lower() in t for kw in GOLD_KW)
    bad = any(kw.lower() in t for kw in EXCLUDE_KW)
    return has and not bad


def clean(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def parse_date(entry):
    for f in ("published_parsed", "updated_parsed", "dc_date_parsed"):
        p = getattr(entry, f, None)
        if p:
            try:
                return datetime(*p[:6]).strftime("%Y-%m-%d")
            except Exception:
                pass
    return ""


def fetch_one(name, url, max_items, gold_only):
    try:
        r = requests.get(url, timeout=12,
                         headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        out = []
        for e in feed.entries:
            title = clean(e.get("title", ""))
            link = e.get("link") or e.get("id", "")
            summ = clean(e.get("summary") or e.get("description", ""))
            date = parse_date(e)
            if not title or not link:
                continue
            if gold_only and not is_gold(title + " " + summ[:200]):
                continue
            out.append({"title": title[:200], "url": link, "source": name,
                         "published": date, "summary": summ[:300]})
            if len(out) >= max_items:
                break
        return out
    except Exception as ex:
        print(f"  FAIL {name}: {ex}")
        return []


def fetch_all():
    articles = []
    for name, url, max_items, gold_only in RSS_FEEDS:
        print(f"  -> {name}...", end=" ", flush=True)
        items = fetch_one(name, url, max_items, gold_only)
        print(f"{len(items)} articles")
        articles.extend(items)
        time.sleep(0.3)

    # Dedupe by title
    seen, uniq = set(), []
    for a in articles:
        t = a["title"][:100]
        if t not in seen:
            seen.add(t)
            uniq.append(a)

    # Sort by date desc
    uniq.sort(key=lambda x: x["published"] or "", reverse=True)
    return uniq[:5]


def fallback():
    return [{
        "title": "Gold Prices Steady as Investors Eye Fed Policy Direction",
        "url": "https://www.gold-eagle.com/",
        "source": "Gold Eagle",
        "published": datetime.now().strftime("%Y-%m-%d"),
        "summary": "Gold held firm as market participants assessed Federal Reserve signals on interest rates..."
    }]


if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Gold news via RSS...")
    articles = fetch_all()
    if not articles:
        print("[WARN] All feeds failed, using fallback")
        articles = fallback()

    result = {
        "updated": datetime.now().astimezone().isoformat(),
        "count": len(articles),
        "articles": articles
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n[DONE] {len(articles)} articles")
    for a in articles:
        print(f"  [{a['source']}] {a['published']} | {a['title'][:65]}")
