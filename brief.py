"""Daily morning brief, generated end to end by Python: market snapshot, key levels for the breakout
strategy, macro calendar, rule-based observations and charts. Writes docs/briefs/YYYY-MM-DD.html
(served by GitHub Pages) and refreshes docs/index.html.

    python brief.py
"""
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import charts
from backtest import ASSETS as STRATEGY_ASSETS
from macro_calendar import events
from market import snapshot
from monitor import fmt, levels

REPO = "https://github.com/ALBAN245/markets-research-lab"
DOCS = Path(__file__).parent / "docs"
PARIS = ZoneInfo("Europe/Paris")

CSS = """
:root { --accent:#7b1730; --ink:#1c1c1c; --muted:#6b6b6b; --rule:#e2dcd8; --up:#2f6f4e; --down:#7b1730; }
body { background:#fff; color:var(--ink); margin:0; font:15px/1.55 Lato, "Helvetica Neue", Arial, sans-serif; }
main { max-width:900px; margin:0 auto; padding:36px 16px 56px; }
h1 { text-align:center; font-size:1.9rem; letter-spacing:.04em; margin:0; }
.sub { text-align:center; font-style:italic; color:var(--muted); margin:2px 0 4px; }
.src { text-align:center; font-size:.82rem; color:var(--muted); margin:0 0 8px; }
h2 { color:var(--accent); font-size:1.15rem; border-bottom:1.5px solid var(--accent); padding-bottom:3px; margin:30px 0 10px; }
h3 { font-size:.95rem; margin:16px 0 6px; }
table { border-collapse:collapse; width:100%; font-size:.86rem; display:block; overflow-x:auto; }
th, td { padding:5px 9px; border-bottom:1px solid var(--rule); text-align:right; white-space:nowrap; }
th:first-child, td:first-child { text-align:left; }
th { color:var(--muted); font-weight:700; }
.up { color:var(--up); font-weight:700; } .down { color:var(--down); font-weight:700; }
ul { padding-left:20px; } li { margin:3px 0; }
a { color:var(--accent); }
.note { font-size:.82rem; color:var(--muted); }
footer { margin-top:36px; font-size:.8rem; color:var(--muted); border-top:1px solid var(--rule); padding-top:10px; }
"""


def pct(v):
    if v != v:
        return "–"
    return f'<span class="{"up" if v >= 0 else "down"}">{v:+.2%}</span>'


def trend_cell(t):
    return {"up": '<span class="up">▲ up</span>', "down": '<span class="down">▼ down</span>'}.get(t, t)


def table(head, rows):
    th = "".join(f"<th>{h}</th>" for h in head)
    return f"<table><tr>{th}</tr>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>"


def at_a_glance(df, cal):
    """Rule-based observations: no opinion, only what the data says."""
    by = df.set_index("name")
    out = []
    d = by.loc["Dollar index (DXY)"]
    out.append(f"<b>Dollar index</b> {d['last']:.2f} ({d['1d']:+.2%} on the day, {d['1m']:+.2%} over a month), trend {d['trend']}.")
    movers = df[df["name"] != "VIX"].assign(a=df["1d"].abs()).nlargest(3, "a")
    out.append("<b>Biggest moves</b>: " + ", ".join(f"{r['name']} {r['1d']:+.2%}" for _, r in movers.iterrows()) + ".")
    hot = [f"{n} ({r['rsi']:.0f})" for n, r in by.iterrows() if r["rsi"] >= 70]
    cold = [f"{n} ({r['rsi']:.0f})" for n, r in by.iterrows() if r["rsi"] <= 30]
    if hot or cold:
        out.append("<b>RSI extremes</b>: " + "; ".join(filter(None, [
            "overbought " + ", ".join(hot) if hot else "", "oversold " + ", ".join(cold) if cold else ""])) + ".")
    highs = [n for n, r in by.iterrows() if r["last"] >= r["high20"]]
    lows = [n for n, r in by.iterrows() if r["last"] <= r["low20"]]
    if highs or lows:
        out.append("<b>20-day extremes</b>: " + "; ".join(filter(None, [
            "at a high: " + ", ".join(highs) if highs else "", "at a low: " + ", ".join(lows) if lows else ""])) + ".")
    t = by.loc["US 10Y yield (%)"]
    out.append(f"<b>US 10-year yield</b> {t['last']:.2f} % ({t['1m']:+.1%} over a month); VIX {by.loc['VIX', 'last']:.1f}.")
    high = [e for e in cal if e["impact"] == "High"]
    if high:
        e = high[0]
        out.append(f"<b>Next high-impact release</b>: {e['currency']} {escape(e['title'])}, {e['when']:%a %H:%M} Paris "
                   f"(forecast {e['forecast']}, previous {e['previous']}).")
    return "<ul>" + "".join(f"<li>{x}</li>" for x in out) + "</ul>"


def key_levels():
    rows = []
    for name in STRATEGY_ASSETS:
        try:
            s = levels(name)
        except Exception:  # one feed down must not break the brief
            continue
        p = s["pip"]
        broken = [k for k, ok in (("PDH", s["high"] > s["pdh"]), ("PDL", s["low"] < s["pdl"])) if ok]
        scaled = 0.25 * s["range"]
        rows.append([name, fmt(s["price"], p), fmt(s["pdh"], p), f"{round((s['pdh'] - s['price']) / p):+d}",
                     fmt(s["pdl"], p), f"{round((s['pdl'] - s['price']) / p):+d}", f"{s['range']:.0f}",
                     f"{scaled:.0f}", ", ".join(broken) or "–"])
    return table(["Asset", "Price", "PDH", "to PDH (pips)", "PDL", "to PDL (pips)", "Prev. range (pips)",
                  "Scaled stop (pips)", "Broken today"], rows)


def build():
    now = datetime.now(PARIS)
    df, closes = snapshot()
    try:
        cal = events(days=1)
    except OSError:
        cal = []
    markets = ""
    for group, g in df.groupby("group", sort=False):
        rows = [[r["name"], f"{r['last']:.{r['dec']}f}", pct(r["1d"]), pct(r["1w"]), pct(r["1m"]),
                 f"{r['low20']:.{r['dec']}f} – {r['high20']:.{r['dec']}f}", f"{r['rsi']:.0f}", trend_cell(r["trend"])]
                for _, r in g.iterrows()]
        markets += f"<h3>{group}</h3>" + table(["Asset", "Last", "1d", "1w", "1m", "20-day range", "RSI 14", "Trend"], rows)
    calendar = table(["Day", "Paris", "Ccy", "Event", "Impact", "Forecast", "Previous"],
                     [[f"{e['when']:%a %d/%m}", f"{e['when']:%H:%M}", e["currency"], escape(e["title"]), e["impact"],
                       e["forecast"], e["previous"]] for e in cal]) if cal else "<p>No medium or high-impact release today or tomorrow.</p>"
    body = f"""
<h1>MORNING BRIEF</h1>
<p class="sub">{now:%A %d %B %Y}</p>
<p class="src">Generated automatically by <a href="{REPO}/blob/main/brief.py">brief.py</a> at {now:%H:%M} Paris ·
data: Yahoo Finance, Binance, Forex Factory</p>
<h2>At a glance</h2>{at_a_glance(df, cal)}
<h2>Key levels for the breakout strategy</h2>
<p class="note">Previous day's high (PDH) and low (PDL). FX/gold days run 5pm–5pm New York, crypto in UTC.
Scaled stop = 25 % of the previous day's range, the rule that survives the <a href="{REPO}/blob/main/results/report.md">robustness tests</a>.</p>
{key_levels()}
<h2>Macro calendar (today and tomorrow, Paris time)</h2>{calendar}
<h2>Markets</h2>{markets}
<p class="note">Trend: price above its 50-day MA above its 200-day MA = up, the reverse = down, otherwise mixed.</p>
<h2>Charts</h2>{charts.section(df, closes)}
<footer>Personal research project by Alban Laurens · <a href="{REPO}">source code</a> ·
observations are generated from data, not investment advice.</footer>"""
    html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>Morning brief {now:%d %b %Y}</title>'
            f'<link href="https://fonts.googleapis.com/css2?family=Lato:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">'
            f'<style>{CSS}{charts.CSS}</style></head><body><main>{body}</main></body></html>')
    out = DOCS / "briefs" / f"{now:%Y-%m-%d}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    index(CSS)
    return out


def index(css):
    """Landing page of the GitHub Pages site: list of briefs, newest first."""
    briefs = sorted((DOCS / "briefs").glob("*.html"), reverse=True)
    items = "".join(f'<li><a href="briefs/{b.name}">{datetime.strptime(b.stem, "%Y-%m-%d"):%A %d %B %Y}</a></li>'
                    for b in briefs)
    (DOCS / "index.html").write_text(
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>Markets research lab</title>'
        f'<link href="https://fonts.googleapis.com/css2?family=Lato:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">'
        f'<style>{css}</style></head><body><main><h1>MARKETS RESEARCH LAB</h1>'
        f'<p class="sub">Alban Laurens · FX, gold and crypto, in Python</p>'
        f'<h2>Morning briefs</h2><ul>{items}</ul>'
        f'<h2>Research</h2><ul><li><a href="{REPO}/blob/main/results/report.md">Breakout strategy: robustness report</a></li>'
        f'<li><a href="{REPO}">Source code and README</a></li></ul></main></body></html>')


if __name__ == "__main__":
    print(build())
