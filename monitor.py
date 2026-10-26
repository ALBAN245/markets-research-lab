"""Real-time monitor of previous-day high/low levels, with macOS notifications.

Every minute it checks each asset and sends an alert when price gets close to the previous day's
high (PDH) or low (PDL), and when it breaks it, with context: stop and target under both rules,
background trend, and any high-impact release within 30 minutes.

    python monitor.py         # runs until Ctrl+C
    python monitor.py --once  # prints today's levels and exits
Yahoo prices (FX, gold) can lag by a few minutes. Notifications use osascript (macOS only).
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone

import yfinance as yf

from backtest import ASSETS, download, sessions
from macro_calendar import events
from market import trend

PAUSE = 60  # seconds between checks
YAHOO_CRYPTO = {"BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD"}
DAILY = {"Bitcoin": "BTC-USD", "Ethereum": "ETH-USD"}  # daily candles for the background trend


def notify(title, text):
    print(f"\n[{datetime.now():%H:%M}] {title}\n{text}", flush=True)
    script = f"display notification {json.dumps(text)} with title {json.dumps(title)} sound name \"Glass\""
    subprocess.run(["osascript", "-e", script], check=False)


def levels(name):
    """Previous day's high/low and the current day's state for one asset."""
    source, symbol, pip, _ = ASSETS[name]
    try:
        candles = download(source, symbol, days=5)
    except OSError:  # Binance refuses US-hosted servers (HTTP 451): same pair from Yahoo
        candles = download("yahoo", YAHOO_CRYPTO[symbol], days=5)
    days = sessions(candles, source, complete=0)
    today, prev = days[-1], next(g for g in reversed(days[:-1]) if len(g) >= 200)
    pdh, pdl = prev["High"].max(), prev["Low"].min()
    return {"pip": pip, "pdh": pdh, "pdl": pdl, "price": today["Close"].iloc[-1],
            "high": today["High"].max(), "low": today["Low"].min(), "range": (pdh - pdl) / pip}


def fmt(v, pip):
    return f"{v:.{max(0, len(f'{pip:f}'.rstrip('0').split('.')[1]) + 1)}f}"


def table(states):
    print("| Asset | Price | PDH | to PDH | PDL | to PDL | Prev. range | Broken today |\n|---|---|---|---|---|---|---|---|")
    for name, s in states.items():
        p = s["pip"]
        broken = [k for k, ok in (("PDH", s["high"] > s["pdh"]), ("PDL", s["low"] < s["pdl"])) if ok]
        print(f"| {name} | {fmt(s['price'], p)} | {fmt(s['pdh'], p)} | {(s['pdh'] - s['price']) / p:+.0f} pips "
              f"| {fmt(s['pdl'], p)} | {(s['pdl'] - s['price']) / p:+.0f} pips | {s['range']:.0f} pips "
              f"| {', '.join(broken) or 'no'} |")


def release_nearby(name, agenda, minutes=30):
    ccys = name.split("/") if "/" in name else ["USD"]
    now = datetime.now(timezone.utc)
    for e in agenda:
        gap = (e["when"] - now).total_seconds() / 60
        if e["currency"] in ccys and -minutes <= gap <= minutes:
            return f"High-impact {e['currency']} release at {e['when']:%H:%M}: {e['title']}"
    return ""


def breakout_message(name, s, side, background, agenda):
    p, level = s["pip"], s["pdh"] if side == 1 else s["pdl"]
    fixed, scaled = 15 * p, (s["pdh"] - s["pdl"]) * 0.25
    lines = [f"{'Buy' if side == 1 else 'Sell'} breakout of {'PDH' if side == 1 else 'PDL'} {fmt(level, p)}",
             f"Fixed rule: stop {fmt(level - side * fixed, p)} / target {fmt(level + side * 2 * fixed, p)}",
             f"Scaled stop ({scaled / p:.0f} pips): stop {fmt(level - side * scaled, p)} / "
             f"target {fmt(level + side * 2 * scaled, p)}"]
    if 15 / s["range"] < 0.15:
        lines.append(f"15-pip stop = {15 / s['range']:.0%} of yesterday's range: inside the noise.")
    if background in ("up", "down"):
        lines.append(f"Background trend {background}: breakout "
                     f"{'with' if (background == 'up') == (side == 1) else 'against'} the trend.")
    if alert := release_nearby(name, agenda):
        lines.append(alert)
    return "\n".join(lines)


def main():
    states = {name: levels(name) for name in ASSETS}
    table(states)
    if "--once" in sys.argv:
        return
    tickers = {n: DAILY.get(n, s) for n, (_, s, _, _) in ASSETS.items()}
    closes = yf.download(list(tickers.values()), period="1y", progress=False, auto_adjust=False)["Close"]
    background = {n: trend(closes[t].dropna()) for n, t in tickers.items()}
    try:
        agenda = events(days=7, impacts=("High",))
    except Exception:
        agenda = []
    sent = set()
    print(f"\nMonitoring {len(ASSETS)} assets every {PAUSE} s. Ctrl+C to stop.", flush=True)
    while True:
        time.sleep(PAUSE)
        for name in ASSETS:
            try:
                s = levels(name)
            except Exception as err:  # transient network error: retry on the next pass
                print(f"{name}: data unavailable ({err})", flush=True)
                continue
            p, key = s["pip"], (datetime.now().date(), name)
            for side, level, label in ((1, s["pdh"], "PDH"), (-1, s["pdl"], "PDL")):
                broken = s["high"] > level if side == 1 else s["low"] < level
                close = abs(s["price"] - level) <= max(5 * p, 0.1 * (s["pdh"] - s["pdl"]))
                if broken and (key, label, "break") not in sent:
                    sent.add((key, label, "break"))
                    notify(f"{name}: {label} broken", breakout_message(name, s, side, background[name], agenda))
                elif close and not broken and (key, label, "near") not in sent:
                    sent.add((key, label, "near"))
                    notify(f"{name} near {label}", f"Price {fmt(s['price'], p)}, {label} {fmt(level, p)} "
                           f"({abs(s['price'] - level) / p:.0f} pips). {release_nearby(name, agenda)}".strip())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
