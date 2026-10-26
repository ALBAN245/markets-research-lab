"""Inline SVG charts for the brief (no JS library): 1-month performance bars and 6-month price curves
with 50/200-day moving averages, hover to read values."""
import json

COLORS = {"price": "#7b1730", "ma50": "#c58a2e", "ma200": "#5b6b7a", "pos": "#2f6f4e", "neg": "#7b1730",
          "grid": "#ebe7e4", "axis": "#c9c3be", "muted": "#8a8580"}
CURVES = ["Dollar index (DXY)", "EUR/USD", "USD/JPY", "GBP/USD", "Bitcoin", "Ethereum", "S&P 500", "Gold"]
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

CSS = """
.curves { display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:12px; }
.card { border:1px solid var(--rule); border-radius:6px; padding:8px 10px; position:relative; }
.card h3 { font-size:.9rem; margin:0; } .card .meta { font-size:.78rem; color:var(--muted); }
.viz svg { width:100%; height:auto; display:block; overflow:visible; }
.tip { position:absolute; pointer-events:none; background:#fff; border:1px solid var(--rule); border-radius:4px;
       padding:3px 7px; font-size:.75rem; white-space:nowrap; display:none; z-index:2; }
.legend { display:flex; gap:16px; font-size:.8rem; color:var(--muted); margin:6px 0 10px; flex-wrap:wrap; }
.legend i { display:inline-block; width:14px; height:2px; vertical-align:middle; margin-right:5px; }
"""

JS = """
document.querySelectorAll('.viz [data-series]').forEach(svg => {
  const d = JSON.parse(svg.dataset.series), card = svg.parentElement, tip = card.querySelector('.tip');
  const line = svg.querySelector('.cursor'), dot = svg.querySelector('.dot');
  svg.addEventListener('mousemove', e => {
    const r = svg.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * d.w;
    const i = Math.max(0, Math.min(d.x.length - 1, Math.round((x - d.l) / (d.w - d.l - d.r) * (d.x.length - 1))));
    line.setAttribute('x1', d.px[i]); line.setAttribute('x2', d.px[i]); line.style.display = '';
    dot.setAttribute('cx', d.px[i]); dot.setAttribute('cy', d.py[i]); dot.style.display = '';
    tip.innerHTML = `<b>${d.x[i]}</b><br>Price ${d.p[i]}<br>MA50 ${d.m50[i] ?? '–'} · MA200 ${d.m200[i] ?? '–'}`;
    tip.style.display = 'block';
    tip.style.left = Math.min(d.px[i] / d.w * r.width + 10, card.clientWidth - tip.offsetWidth - 4) + 'px';
    tip.style.top = '36px';
  });
  svg.addEventListener('mouseleave', () => { tip.style.display = line.style.display = dot.style.display = 'none'; });
});
"""


def _path(xs, ys):
    pts = [(x, y) for x, y in zip(xs, ys) if y is not None]
    return " ".join(f"{'L' if i else 'M'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))


def curve(name, closes, dec):
    """6-month price with 50- and 200-day moving averages, one shared axis."""
    ma50, ma200 = closes.rolling(50).mean().tail(126), closes.rolling(200).mean().tail(126)
    s = closes.tail(126)
    w, h, left, right, top, bottom = 300, 130, 4, 44, 8, 18
    vals = [v for series in (s, ma50, ma200) for v in series.dropna()]
    lo, hi = min(vals), max(vals)
    px = [left + i * (w - left - right) / (len(s) - 1) for i in range(len(s))]
    y = lambda v: None if v != v else top + (hi - v) / (hi - lo) * (h - top - bottom)  # v != v: NaN
    f = lambda v: None if v != v else f"{v:.{dec}f}"
    data = {"w": w, "l": left, "r": right, "px": [round(v, 1) for v in px], "py": [round(y(v), 1) for v in s],
            "x": [f"{d:%d %b}" for d in s.index], "p": [f(v) for v in s],
            "m50": [f(v) for v in ma50], "m200": [f(v) for v in ma200]}
    grid = "".join(f'<line x1="{left}" x2="{w - right}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{COLORS["grid"]}"/>'
                   f'<text x="{w - right + 4}" y="{y(v) + 3:.1f}" font-size="9" fill="{COLORS["muted"]}">{v:.{dec}f}</text>'
                   for v in (lo, (lo + hi) / 2, hi))
    months = "".join(f'<text x="{px[i]:.1f}" y="{h - 4}" font-size="9" fill="{COLORS["muted"]}" text-anchor="middle">'
                     f'{MONTHS[s.index[i].month - 1]}</text>' for i in range(0, len(s), 42))
    svg = (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{name}, 6 months" data-series=\'{json.dumps(data)}\'>'
           f'{grid}{months}'
           f'<path d="{_path(px, [y(v) for v in ma200])}" fill="none" stroke="{COLORS["ma200"]}" stroke-width="1.4"/>'
           f'<path d="{_path(px, [y(v) for v in ma50])}" fill="none" stroke="{COLORS["ma50"]}" stroke-width="1.4"/>'
           f'<path d="{_path(px, data["py"])}" fill="none" stroke="{COLORS["price"]}" stroke-width="2"/>'
           f'<line class="cursor" y1="{top}" y2="{h - bottom}" stroke="{COLORS["axis"]}" style="display:none"/>'
           f'<circle class="dot" r="4" fill="{COLORS["price"]}" stroke="#fff" stroke-width="2" style="display:none"/></svg>')
    var = s.iloc[-1] / s.iloc[0] - 1
    return (f'<div class="card"><h3>{name}</h3><div class="meta">{s.iloc[-1]:.{dec}f} · {var:+.1%} over 6 months</div>'
            f'{svg}<div class="tip"></div></div>')


def performance(rows):
    """Diverging horizontal bars: 1-month change of each asset, sorted."""
    rows = sorted(((r["name"], r["1m"] * 100) for r in rows if r["1m"] == r["1m"]), key=lambda t: -t[1])
    w, lh, lab, val = 640, 20, 150, 56
    m = max(abs(v) for _, v in rows)
    zero = lab + (w - lab - val) / 2
    k = (w - lab - val) / 2 / m
    bars = ""
    for i, (name, v) in enumerate(rows):
        y = i * lh + 4
        bars += (f'<g><title>{name}: {v:+.2f} % over 1 month</title>'
                 f'<text x="{lab - 8}" y="{y + 11}" font-size="11" fill="{COLORS["muted"]}" text-anchor="end">{name}</text>'
                 f'<rect x="{zero + min(0, v) * k:.1f}" y="{y}" width="{max(abs(v) * k, 1):.1f}" height="{lh - 6}" rx="2" '
                 f'fill="{COLORS["pos"] if v >= 0 else COLORS["neg"]}"/>'
                 f'<text x="{zero + v * k + (6 if v >= 0 else -6):.1f}" y="{y + 11}" font-size="10" '
                 f'text-anchor="{"start" if v >= 0 else "end"}">{v:+.1f} %</text></g>')
    h = len(rows) * lh + 8
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="1-month performance">'
            f'<line x1="{zero}" x2="{zero}" y1="0" y2="{h}" stroke="{COLORS["axis"]}"/>{bars}</svg>')


def section(snapshot, closes):
    """Charts block: performance bars, then the 6-month curves."""
    from market import ASSETS
    tickers = {n: t for g in ASSETS.values() for n, t in g.items()}
    dec = dict(zip(snapshot["name"], snapshot["dec"]))
    rows = [r for r in snapshot.to_dict("records") if r["name"] != "VIX" and "%" not in r["name"]]
    cards = "".join(curve(n, closes[tickers[n]].dropna(), dec[n]) for n in CURVES)
    return (f'<div class="viz"><h3>1-month performance</h3>{performance(rows)}'
            f'<h3>Last 6 months</h3><div class="legend"><span><i style="background:{COLORS["price"]}"></i>Price</span>'
            f'<span><i style="background:{COLORS["ma50"]}"></i>50-day MA</span>'
            f'<span><i style="background:{COLORS["ma200"]}"></i>200-day MA</span><span>Hover a chart to read values</span></div>'
            f'<div class="curves">{cards}</div></div><script>{JS}</script>')
