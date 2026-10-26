"""Latest market headlines from public RSS feeds, without commentary.

    python news.py
"""
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# section: [(source, feed url, max age in hours)]
FEEDS = {
    "FX & macro": [("FXStreet", "https://www.fxstreet.com/rss/news", 24),
                   ("Investing.com", "https://www.investing.com/rss/news_1.rss", 24)],
    "Central banks": [("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml", 72),
                      ("ECB", "https://www.ecb.europa.eu/rss/press.html", 72)],
    "Crypto": [("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", 24)],
}


def parse_date(text):
    try:
        return parsedate_to_datetime(text)
    except (TypeError, ValueError):  # Investing.com: "2026-10-26 15:01:16", GMT
        return datetime.fromisoformat(text.strip()).replace(tzinfo=timezone.utc)


def headlines(per_section=6):
    """{section: [(datetime, source, title, link)]}, newest first. A feed that fails is skipped."""
    now = datetime.now(timezone.utc)
    out = {}
    for section, feeds in FEEDS.items():
        items, cap = [], -(-per_section // len(feeds))  # same share for each source
        for source, url, max_age in feeds:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                root = ET.fromstring(urllib.request.urlopen(req, timeout=20).read())
            except Exception:
                continue
            fresh = []
            for it in root.iter("item"):
                title, link = (it.findtext("title") or "").strip(), (it.findtext("link") or "").strip()
                try:
                    when = parse_date(it.findtext("pubDate") or "")
                except ValueError:
                    continue
                if title and now - when <= timedelta(hours=max_age):
                    fresh.append((when.astimezone(timezone.utc), source, title, link))
            items += sorted(fresh, reverse=True)[:cap]
        out[section] = sorted(items, reverse=True)[:per_section]
    return out


if __name__ == "__main__":
    for section, items in headlines().items():
        print(f"\n## {section}")
        for when, source, title, _ in items:
            print(f"- {when:%d/%m %H:%M} UTC · {source} · {title}")
