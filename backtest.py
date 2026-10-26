"""Backtest of a previous-day high/low breakout strategy.

Rule: buy when price breaks above the previous day's high (PDH), sell when it breaks below
the previous day's low (PDL). One entry per level per day, exit at stop, target or end of day.
Two stop rules are compared:
  - fixed:  15 pips stop, 30 pips target (the rule I started trading with)
  - scaled: stop = 25 % of the previous day's range, target = 2x stop
Results are in R (1R = the amount risked on the trade), spread included.

Data: 5-minute candles, ~60 days for FX and gold (Yahoo Finance), 1 year for BTC/ETH (Binance).
A frozen snapshot lives in data/ so the published numbers can be reproduced exactly.

    python backtest.py            # uses the snapshot in data/
    python backtest.py --refresh  # downloads fresh data and overwrites the snapshot
"""
import json
import sys
import urllib.request
from datetime import timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA = Path(__file__).parent / "data"

# name: (source, symbol, pip size, spread in pips)
ASSETS = {
    "EUR/USD": ("yahoo", "EURUSD=X", 0.0001, 0.8),
    "GBP/USD": ("yahoo", "GBPUSD=X", 0.0001, 1.2),
    "USD/JPY": ("yahoo", "JPY=X", 0.01, 1.0),
    "AUD/USD": ("yahoo", "AUDUSD=X", 0.0001, 1.0),
    "USD/CAD": ("yahoo", "CAD=X", 0.0001, 1.5),
    "USD/CHF": ("yahoo", "CHF=X", 0.0001, 1.5),
    "Gold": ("yahoo", "GC=F", 0.1, 3.0),
    "Bitcoin": ("binance", "BTCUSDT", 1.0, 10.0),
    "Ethereum": ("binance", "ETHUSDT", 0.1, 5.0),
}
MODES = {"fixed": "Fixed stop 15 pips / target 30 pips",
         "scaled": "Stop = 25 % of previous day's range / target 2x"}


def download(source, symbol, days=None):
    """5-minute candles: 60 days max on Yahoo, 1 year by default on Binance."""
    if source == "yahoo":
        d = yf.download(symbol, interval="5m", period=f"{min(days or 60, 60)}d", progress=False, auto_adjust=False)
        d.columns = d.columns.get_level_values(0)
        return d[["High", "Low", "Close"]].dropna()
    rows, end = [], None
    for _ in range(-(-(days or 368) * 288 // 1000)):  # 288 candles a day, 1000 per request
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=1000"
        if end:
            url += f"&endTime={end}"
        batch = json.load(urllib.request.urlopen(url, timeout=20))
        if not batch:
            break
        rows = batch + rows
        end = batch[0][0] - 1
    d = pd.DataFrame(rows).iloc[:, :5].astype(float)
    d.index = pd.to_datetime(d[0], unit="ms", utc=True)
    return d.rename(columns={2: "High", 3: "Low", 4: "Close"})[["High", "Low", "Close"]]


def candles(name, refresh=False):
    """Candles from the frozen snapshot, or freshly downloaded (and saved) with refresh=True."""
    path = DATA / f"{name.replace('/', '')}.csv.gz"
    if refresh or not path.exists():
        source, symbol, _, _ = ASSETS[name]
        DATA.mkdir(exist_ok=True)
        download(source, symbol).to_csv(path)
    d = pd.read_csv(path, index_col=0)
    d.index = pd.to_datetime(d.index, utc=True)
    return d


def sessions(d, source, complete=200):
    """Split into trading days: FX/gold 5pm-5pm New York time (market convention), crypto in UTC.
    Days with fewer than `complete` candles (Sunday evening opens) are dropped."""
    if source == "yahoo":
        day = (d.index.tz_convert("America/New_York") - timedelta(hours=17)).date
    else:
        day = d.index.tz_convert("UTC").date
    return [g for _, g in d.groupby(day) if len(g) >= complete]


def trade(day, level, side, stop):
    """Result in R of one breakout, before costs. side = 1 for a buy above PDH, -1 for a sell below PDL.
    Returns (entry time, R) or None if the level is not broken."""
    broken = day["High"] > level if side == 1 else day["Low"] < level
    if not broken.any():
        return None
    after = day.loc[broken.idxmax():]
    sl, tp = level - side * stop, level + side * 2 * stop
    for _, c in after.iterrows():
        hit_sl = c["Low"] <= sl if side == 1 else c["High"] >= sl
        hit_tp = c["High"] >= tp if side == 1 else c["Low"] <= tp
        if hit_sl:  # stop and target in the same candle: count the loss (conservative)
            return after.index[0], -1.0
        if hit_tp:
            return after.index[0], 2.0
    return after.index[0], side * (after["Close"].iloc[-1] - level) / stop


def trades(name, mode, refresh=False):
    """All trades of one asset as a Series of R (spread included), indexed by entry time."""
    source, _, pip, spread = ASSETS[name]
    days = sessions(candles(name, refresh), source)
    times, results = [], []
    for prev, day in zip(days, days[1:]):
        pdh, pdl = prev["High"].max(), prev["Low"].min()
        stop = 15 * pip if mode == "fixed" else (pdh - pdl) * 0.25
        if stop <= 0:
            continue
        for side, level in ((1, pdh), (-1, pdl)):
            if res := trade(day, level, side, stop):
                times.append(res[0])
                results.append(res[1] - spread * pip / stop)
    return pd.Series(results, index=pd.DatetimeIndex(times), dtype=float).sort_index(), len(days) - 1


def summary(r):
    equity = r.cumsum()
    return {"trades": len(r), "win rate": (r > 0).mean(), "mean R": r.mean(), "total R": r.sum(),
            "max drawdown R": (equity - equity.cummax()).min()}


def main():
    refresh = "--refresh" in sys.argv
    for mode, title in MODES.items():
        print(f"\n## {title}\n")
        print("| Asset | Days | Trades | Win rate | Mean R/trade | Total R | Max drawdown |")
        print("|---|---|---|---|---|---|---|")
        for name in ASSETS:
            r, n_days = trades(name, mode, refresh and mode == "fixed")
            s = summary(r)
            print(f"| {name} | {n_days} | {s['trades']} | {s['win rate']:.0%} | {s['mean R']:+.2f} | "
                  f"{s['total R']:+.1f} | {s['max drawdown R']:.1f} |", flush=True)
    print("\nBreak-even win rate with a 1:2 payoff: 33 %, before costs.")


if __name__ == "__main__":
    main()
