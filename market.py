"""Market snapshot: last price, changes, 20-day range, 50/200-day moving averages, RSI 14 and trend.

    python market.py   # prints the snapshot as Markdown tables
"""
import pandas as pd
import yfinance as yf

ASSETS = {
    "FX": {
        "EUR/USD": "EURUSD=X", "USD/JPY": "JPY=X", "GBP/USD": "GBPUSD=X", "USD/CHF": "CHF=X",
        "AUD/USD": "AUDUSD=X", "USD/CAD": "CAD=X", "EUR/GBP": "EURGBP=X", "Dollar index (DXY)": "DX-Y.NYB",
    },
    "Crypto": {"Bitcoin": "BTC-USD", "Ethereum": "ETH-USD", "Solana": "SOL-USD", "XRP": "XRP-USD", "BNB": "BNB-USD"},
    "Equity indices": {
        "S&P 500": "^GSPC", "Nasdaq 100": "^NDX", "Euro Stoxx 50": "^STOXX50E", "CAC 40": "^FCHI",
        "DAX": "^GDAXI", "Nikkei 225": "^N225", "VIX": "^VIX",
    },
    "Rates & commodities": {"US 10Y yield (%)": "^TNX", "Gold": "GC=F", "WTI crude": "CL=F"},
}


def rsi(closes, n=14):
    """Wilder's RSI on daily closes."""
    delta = closes.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up.iloc[-1] / down.iloc[-1])


def trend(closes):
    """Price vs 50- and 200-day moving averages."""
    if len(closes) < 200:
        return "n/a"
    price, ma50, ma200 = closes.iloc[-1], closes.tail(50).mean(), closes.tail(200).mean()
    if price > ma50 > ma200:
        return "up"
    if price < ma50 < ma200:
        return "down"
    return "mixed"


def change(closes, days):
    return closes.iloc[-1] / closes.iloc[-1 - days] - 1 if len(closes) > days else float("nan")


def decimals(group, name):
    return 3 if "JPY" in name else 4 if group == "FX" and "DXY" not in name else 2


def snapshot(period="2y"):
    """One row per asset, plus the raw daily closes (used by the charts)."""
    tickers = [t for g in ASSETS.values() for t in g.values()]
    closes = yf.download(tickers, period=period, progress=False, auto_adjust=False)["Close"]
    rows = []
    for group, assets in ASSETS.items():
        for name, t in assets.items():
            c = closes[t].dropna()
            if c.empty:
                continue
            last20 = c.tail(20)
            rows.append({"group": group, "name": name, "dec": decimals(group, name), "last": c.iloc[-1],
                         "1d": change(c, 1), "1w": change(c, 5), "1m": change(c, 21),
                         "low20": last20.min(), "high20": last20.max(), "ma50": c.tail(50).mean(),
                         "ma200": c.tail(200).mean(), "rsi": rsi(c), "trend": trend(c), "date": c.index[-1]})
    return pd.DataFrame(rows), closes


def main():
    df, _ = snapshot()
    for group, g in df.groupby("group", sort=False):
        print(f"\n## {group}\n\n| Asset | Last | 1d | 1w | 1m | 20d range | RSI 14 | Trend |\n|---|---|---|---|---|---|---|---|")
        for _, r in g.iterrows():
            d = r["dec"]
            print(f"| {r['name']} | {r['last']:.{d}f} | {r['1d']:+.2%} | {r['1w']:+.2%} | {r['1m']:+.2%} "
                  f"| {r['low20']:.{d}f} – {r['high20']:.{d}f} | {r['rsi']:.0f} | {r['trend']} |")


if __name__ == "__main__":
    main()
