"""Checks on the trade logic: python test_backtest.py (or pytest)."""
import pandas as pd

from backtest import trade


def day(*candles):
    idx = pd.date_range("2026-01-05 00:00", periods=len(candles), freq="5min", tz="UTC")
    return pd.DataFrame(candles, columns=["High", "Low", "Close"], index=idx)


def test_target_hit_long():
    # level 100, stop 1: break above 100, then target 102 reached -> +2R
    assert trade(day((99.5, 99, 99.2), (100.5, 99.8, 100.4), (102.1, 100.2, 102)), 100, 1, 1)[1] == 2


def test_stop_hit_short():
    # sell below 100, price comes back above 101 -> -1R
    assert trade(day((100.5, 99.8, 99.9), (101.2, 99.9, 101)), 100, -1, 1)[1] == -1


def test_stop_counted_first_in_same_candle():
    # one candle touches both stop (99) and target (102): conservative -> -1R
    assert trade(day((99.5, 99.2, 99.4), (102.5, 98.5, 100)), 100, 1, 1)[1] == -1


def test_no_break_no_trade():
    assert trade(day((99.5, 99, 99.2), (99.9, 99.1, 99.5)), 100, 1, 1) is None


def test_end_of_day_exit():
    # broken, neither stop nor target: closed at last price 100.5 -> +0.5R
    assert trade(day((100.3, 99.9, 100.2), (100.6, 100.1, 100.5)), 100, 1, 1)[1] == 0.5


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
    print("all checks passed")
