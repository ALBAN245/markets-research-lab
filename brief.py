"""Daily morning brief, generated end to end by Python: market snapshot, key levels and setups for the
breakout strategy with rule-based arguments for and against, macro calendar, headlines and charts.

Writes docs/briefs/YYYY-MM-DD.html, copies it to docs/index.html (the latest brief is the site's home page)
and refreshes docs/archive.html. Runs every weekday morning on GitHub Actions (.github/workflows/brief.yml).

    python brief.py
"""
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import charts
from backtest import ASSETS as STRATEGY_ASSETS
from backtest import trades
from macro_calendar import events
from market import snapshot
from monitor import fmt, levels
from news import headlines

REPO = "https://github.com/ALBAN245/markets-research-lab"
SITE = "https://alban245.github.io/markets-research-lab"
DOCS = Path(__file__).parent / "docs"
PARIS = ZoneInfo("Europe/Paris")
WATCHLIST = 5  # setups detailed in "What to watch"

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
td.l, th.l { text-align:left; white-space:normal; }
th { color:var(--muted); font-weight:700; }
.up { color:var(--up); font-weight:700; } .down { color:var(--down); font-weight:700; }
ul { padding-left:20px; margin:4px 0; } li { margin:3px 0; }
a { color:var(--accent); }
.note { font-size:.82rem; color:var(--muted); }
.setup { border-left:3px solid var(--accent); padding:2px 0 4px 12px; margin:14px 0; }
.setup h3 { margin:0 0 4px; }
.pc { display:grid; grid-template-columns:1fr 1fr; gap:4px 18px; }
@media (max-width:640px) { .pc { grid-template-columns:1fr; } }
.pc b { font-size:.85rem; }
.news li { margin:4px 0; } .news .t { color:var(--muted); font-size:.82rem; }
footer { margin-top:36px; font-size:.8rem; color:var(--muted); border-top:1px solid var(--rule); padding-top:10px; }
"""


def pct(v, digits=2):
    if v != v:
        return "–"
    return f'<span class="{"up" if v >= 0 else "down"}">{v:+.{digits}%}</span>'


def trend_cell(t):
    return {"up": '<span class="up">▲ up</span>', "down": '<span class="down">▼ down</span>'}.get(t, t)


def table(head, rows, left=()):
    th = "".join(f'<th{" class=l" if i in left else ""}>{h}</th>' for i, h in enumerate(head))
    body = "".join("<tr>" + "".join(f'<td{" class=l" if i in left else ""}>{c}</td>' for i, c in enumerate(r)) + "</tr>"
                   for r in rows)
    return f"<table><tr>{th}</tr>{body}</table>"


def ul(items):
    return "<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>" if items else ""


def currencies(name):
    return name.split("/") if "/" in name else ["USD"]


def pips(v, pip):
    return f"{round(v / pip):+d}"


# ---------------------------------------------------------------- sections

def at_a_glance(by, lv, week):
    out = []
    d = by.loc["Dollar index (DXY)"]
    out.append(f"<b>Dollar index</b> {d['last']:.2f} ({d['1d']:+.2%} on the day, {d['1m']:+.2%} over a month), trend {d['trend']}.")
    broken = [f"{n} {k}" for n, s in lv.items() for k, ok in (("PDH", s["high"] > s["pdh"]), ("PDL", s["low"] < s["pdl"])) if ok]
    out.append("<b>Levels already broken today</b>: " + (", ".join(broken) if broken else "none") + ".")
    close = sorted(((abs(lvl - s["price"]) / (s["pdh"] - s["pdl"]), n, k, lvl, s) for n, s in lv.items()
                    for k, lvl, ok in (("PDH", s["pdh"], s["high"] <= s["pdh"]), ("PDL", s["pdl"], s["low"] >= s["pdl"])) if ok))[:3]
    if close:
        out.append("<b>Closest untouched levels</b>: " + ", ".join(
            f"{n} {k} {fmt(lvl, s['pip'])} ({pips(lvl - s['price'], s['pip'])} pips, {share:.0%} of yesterday's range)"
            for share, n, k, lvl, s in close) + ".")
    movers = by.drop(index="VIX").assign(a=lambda x: x["1d"].abs()).nlargest(3, "a")
    out.append("<b>Biggest daily moves</b>: " + ", ".join(f"{n} {r['1d']:+.2%}" for n, r in movers.iterrows()) + ".")
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
    v, t, w = by.loc["VIX"], by.loc["US 10Y yield (%)"], by.loc["WTI crude"]
    out.append(f"<b>Risk gauges</b>: VIX {v['last']:.1f} ({v['1m']:+.0%} over a month), US 10-year {t['last']:.2f} %, "
               f"WTI ${w['last']:.2f} ({w['1d']:+.2%} on the day).")
    high = [e for e in week if e["impact"] == "High"]
    if high:
        out.append("<b>High-impact releases this week</b>: " + "; ".join(
            f"{e['when']:%a %H:%M} {e['currency']} {escape(e['title'])}" for e in high[:8]) + ".")
    return ul(out)


def arguments(name, side, s, m, week, backtest_mean):
    """Rule-based points for and against a breakout. side = 1 buy above PDH, -1 sell below PDL."""
    pro, con = [], []
    direction = "up" if side == 1 else "down"
    if m["trend"] == direction:
        pro.append(f"breakout in the direction of the {m['trend']} trend (50/200-day MAs)")
    elif m["trend"] in ("up", "down"):
        con.append(f"against the {m['trend']} trend (50/200-day MAs)")
    if m["1w"] == m["1w"]:
        (pro if m["1w"] * side > 0 else con).append(f"1-week momentum {m['1w']:+.2%}")
    if side == 1 and m["rsi"] >= 70:
        con.append(f"RSI {m['rsi']:.0f}: overbought")
    if side == -1 and m["rsi"] <= 30:
        con.append(f"RSI {m['rsi']:.0f}: oversold")
    if (side == 1 and m["last"] >= m["high20"]) or (side == -1 and m["last"] <= m["low20"]):
        pro.append(f"price at a 20-day {'high' if side == 1 else 'low'}: the breakout would extend it")
    soon = datetime.now(PARIS) + timedelta(hours=24)
    for e in week:
        if e["impact"] == "High" and e["currency"] in currencies(name) and e["when"] <= soon:
            con.append(f"event risk: {e['currency']} {escape(e['title'])} {e['when']:%a %H:%M}")
    share = 15 / s["range"]
    if share < 0.15:
        con.append(f"a fixed 15-pip stop is {share:.0%} of yesterday's range: inside the noise")
    if backtest_mean is not None:
        (pro if backtest_mean > 0 else con).append(f"backtest with the scaled stop on {name}: {backtest_mean:+.2f} R per trade")
    return pro, con


def watchlist(lv, by, week):
    """The untouched levels closest to price, relative to yesterday's range, with both stop rules."""
    candidates = []
    for n, s in lv.items():
        rng = s["pdh"] - s["pdl"]
        for side, lvl, untouched in ((1, s["pdh"], s["high"] <= s["pdh"]), (-1, s["pdl"], s["low"] >= s["pdl"])):
            if untouched and rng > 0:
                candidates.append((abs(lvl - s["price"]) / rng, n, side, lvl))
    seen, picks = set(), []
    for share, n, side, lvl in sorted(candidates):
        if n not in seen and n in by.index:
            seen.add(n)
            picks.append((share, n, side, lvl))
    html = ""
    for share, n, side, lvl in picks[:WATCHLIST]:
        s, m, p = lv[n], by.loc[n], lv[n]["pip"]
        fixed, scaled = 15 * p, 0.25 * (s["pdh"] - s["pdl"])
        try:
            bt = trades(n, "scaled")[0].mean()
        except Exception:
            bt = None
        pro, con = arguments(n, side, s, m, week, bt)
        verb, label = ("Buy above", "PDH") if side == 1 else ("Sell below", "PDL")
        html += f"""<div class="setup"><h3>{n} · {label} {fmt(lvl, p)} ({pips(lvl - s['price'], p)} pips)</h3>
<div class="note">Price {fmt(s['price'], p)} · trend {m['trend']} · RSI {m['rsi']:.0f} · 1 week {m['1w']:+.2%} ·
1 month {m['1m']:+.2%} · yesterday's range {s['range']:.0f} pips</div>
<ul><li><b>{verb} {fmt(lvl, p)}</b>, fixed rule: stop {fmt(lvl - side * fixed, p)}, target {fmt(lvl + side * 2 * fixed, p)}</li>
<li>Scaled stop ({scaled / p:.0f} pips): stop {fmt(lvl - side * scaled, p)}, target {fmt(lvl + side * 2 * scaled, p)}</li></ul>
<div class="pc"><div><b>For</b>{ul(pro) or '<p class="note">nothing in the data</p>'}</div>
<div><b>Against</b>{ul(con) or '<p class="note">nothing in the data</p>'}</div></div></div>"""
    return html or "<p>No untouched level today.</p>"


def key_levels(lv, by):
    rows, notes = [], []
    for n, s in lv.items():
        p = s["pip"]
        broken = [k for k, ok in (("PDH", s["high"] > s["pdh"]), ("PDL", s["low"] < s["pdl"])) if ok]
        rows.append([n, fmt(s["price"], p), fmt(s["pdh"], p), pips(s["pdh"] - s["price"], p), fmt(s["pdl"], p),
                     pips(s["pdl"] - s["price"], p), f"{s['range']:.0f}", f"{0.25 * s['range']:.0f}",
                     ", ".join(broken) or "–"])
        if n in by.index:
            m = by.loc[n]
            notes.append(f"<b>{n}</b>: trend {m['trend']} (50-day MA {m['ma50']:.{m['dec']}f}, 200-day "
                         f"{m['ma200']:.{m['dec']}f}), RSI {m['rsi']:.0f}; fixed 15-pip stop = "
                         f"{15 / s['range']:.0%} of yesterday's range, scaled stop {0.25 * s['range']:.0f} pips.")
    return table(["Asset", "Price", "PDH", "to PDH (pips)", "PDL", "to PDL (pips)", "Prev. range (pips)",
                  "Scaled stop (pips)", "Broken today"], rows) + ul(notes)


def news_section(items):
    html = ""
    for section, rows in items.items():
        if rows:
            html += f"<h3>{section}</h3><ul class='news'>" + "".join(
                f'<li><span class="t">{w.astimezone(PARIS):%a %H:%M} · {escape(src)}</span> '
                f'<a href="{escape(link)}">{escape(title)}</a></li>' for w, src, title, link in rows) + "</ul>"
    return html or "<p>No headlines available.</p>"


def group_reading(g):
    """One computed line per asset class."""
    n = len(g)
    ups, downs = (g["trend"] == "up").sum(), (g["trend"] == "down").sum()
    highs, lows = (g["last"] >= g["high20"]).sum(), (g["last"] <= g["low20"]).sum()
    best, worst = g.loc[g["1w"].idxmax()], g.loc[g["1w"].idxmin()]
    return (f"{ups} of {n} in an uptrend, {downs} in a downtrend; {highs} at a 20-day high, {lows} at a 20-day low. "
            f"Average 1-week change {g['1w'].mean():+.2%} (best {best['name']} {best['1w']:+.2%}, "
            f"worst {worst['name']} {worst['1w']:+.2%}).")


def markets(df):
    html = ""
    for group, g in df.groupby("group", sort=False):
        rows = [[r["name"], f"{r['last']:.{r['dec']}f}", pct(r["1d"]), pct(r["1w"]), pct(r["1m"]),
                 f"{r['low20']:.{r['dec']}f} – {r['high20']:.{r['dec']}f}", f"{r['ma50']:.{r['dec']}f}",
                 f"{r['ma200']:.{r['dec']}f}", f"{r['rsi']:.0f}", trend_cell(r["trend"])] for _, r in g.iterrows()]
        html += (f"<h3>{group}</h3>" + table(["Asset", "Last", "1d", "1w", "1m", "20-day range", "50-day MA",
                                              "200-day MA", "RSI 14", "Trend"], rows)
                 + f'<p class="note">{group_reading(g)}</p>')
    return html


def calendar(week):
    if not week:
        return "<p>No medium or high-impact release for the rest of the week.</p>"
    return table(["Day", "Paris", "Ccy", "Event", "Impact", "Forecast", "Previous"],
                 [[f"{e['when']:%a %d/%m}", f"{e['when']:%H:%M}", e["currency"], escape(e["title"]),
                   '<span class="down">High</span>' if e["impact"] == "High" else "Medium", e["forecast"], e["previous"]]
                  for e in week], left=(3,))


# ---------------------------------------------------------------- page

def page(title, body):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>'
            f'<link href="https://fonts.googleapis.com/css2?family=Lato:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">'
            f'<style>{CSS}{charts.CSS}</style></head><body><main>{body}</main></body></html>')


def build():
    now = datetime.now(PARIS)
    df, closes = snapshot()
    by = df.set_index("name")
    try:
        week = events(days=6)
    except Exception:  # calendar feed down or blocked: the brief goes out without it
        week = []
    lv = {}
    for name in STRATEGY_ASSETS:
        try:
            lv[name] = levels(name)
        except Exception:  # one feed down must not break the brief
            pass
    body = f"""
<h1>MORNING BRIEF</h1>
<p class="sub">{now:%A %d %B %Y}</p>
<p class="src">Generated automatically by <a href="{REPO}/blob/main/brief.py">brief.py</a> at {now:%H:%M} Paris ·
data: Yahoo Finance, Binance, Forex Factory · headlines: public RSS feeds</p>
<h2>At a glance</h2>{at_a_glance(by, lv, week)}
<h2>What to watch</h2>
<p class="note">The {WATCHLIST} untouched previous-day levels closest to price, relative to yesterday's range. Arguments are
generated by fixed rules from the data (trend, momentum, RSI, 20-day extremes, releases within 24 h, stop size, backtest),
not opinions.</p>
{watchlist(lv, by, week)}
<h2>Key levels for the breakout strategy</h2>
<p class="note">Previous day's high (PDH) and low (PDL). FX/gold days run 5pm–5pm New York, crypto in UTC.
Scaled stop = 25 % of the previous day's range, the rule tested in the <a href="{REPO}/blob/main/results/report.md">robustness report</a>.</p>
{key_levels(lv, by)}
<h2>Headlines</h2>{news_section(headlines())}
<h2>Macro calendar, rest of the week (Paris time)</h2>{calendar(week)}
<h2>Markets</h2>{markets(df)}
<p class="note">Trend: price above its 50-day MA above its 200-day MA = up, the reverse = down, otherwise mixed.</p>
<h2>Charts</h2>{charts.section(df, closes)}
<footer>Personal research project by Alban Laurens · <a href="{REPO}">source code</a> · <a href="{SITE}/archive.html">past briefs</a> ·
generated from data, not investment advice.</footer>"""
    html = page(f"Morning brief {now:%d %b %Y}", body)
    out = DOCS / "briefs" / f"{now:%Y-%m-%d}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    (DOCS / "index.html").write_text(html)  # home page = latest brief
    archive()
    return out


def archive():
    briefs = sorted((DOCS / "briefs").glob("*.html"), reverse=True)
    items = "".join(f'<li><a href="briefs/{b.name}">{datetime.strptime(b.stem, "%Y-%m-%d"):%A %d %B %Y}</a></li>'
                    for b in briefs)
    (DOCS / "archive.html").write_text(page("Morning briefs archive", f"""
<h1>MORNING BRIEFS</h1><p class="sub">Archive · one brief every weekday morning</p>
<h2>All briefs</h2><ul>{items}</ul>
<h2>Project</h2><ul><li><a href="{SITE}/">Latest brief</a></li>
<li><a href="{REPO}/blob/main/results/report.md">Breakout strategy: robustness report</a></li>
<li><a href="{REPO}">Source code and README</a></li></ul>"""))


if __name__ == "__main__":
    print(build())
