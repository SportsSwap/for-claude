"""Turns a price history into entry and exit signals.

Every signal on bar t uses only data up to and including bar t's close. The
backtester acts on it at bar t+1's open, so nothing looks into the future.
"""

import pandas as pd

from config import Strategy
from indicators import atr, ema, macd, sma


def add_signals(prices: pd.DataFrame, s: Strategy, daily: pd.DataFrame | None = None) -> pd.DataFrame:
    """prices: bars of the chart timeframe. daily: daily bars of the same stock, needed
    for a 200-day average on an intraday chart. Without it the average is taken over bars."""
    df = prices.copy()
    df = df.join(macd(df["Close"], s.macd_fast, s.macd_slow, s.macd_signal))
    df["atr"] = atr(df, s.atr_period)
    df["momentum_20"] = df["Close"].pct_change(20)

    above = df["macd"] > df["macd_signal"]
    was_above = above.shift(1, fill_value=False)
    df["cross_up"] = above & ~was_above
    df["cross_down"] = ~above & was_above
    df["zero_cross_up"] = (df["macd"] > 0) & (df["macd"].shift(1) <= 0)

    if s.entry == "signal_cross":
        entry = df["cross_up"].copy()
        if s.require_below_zero:
            entry &= df["macd"] < 0
    elif s.entry == "zero_cross":
        entry = df["zero_cross_up"].copy()
    else:
        raise ValueError(f"unknown entry type {s.entry!r}")

    if s.trend_ma:
        average = ema if s.trend_ma_type == "ema" else sma
        if s.trend_ma_source == "daily" and daily is not None:
            # Yesterday's 200-day value: what you could see before today's open.
            ma = average(daily["Close"], s.trend_ma).shift(1)
            df["trend_ma"] = ma.reindex(df.index.normalize(), method="ffill").to_numpy()
        else:
            df["trend_ma"] = average(df["Close"], s.trend_ma)
        if s.trend_side == "below":
            entry &= df["Close"] < df["trend_ma"]
        else:
            entry &= df["Close"] > df["trend_ma"]

    if s.max_run_atr is not None:
        run = (df["Close"] - df["Low"].rolling(s.run_lookback).min()) / df["atr"]
        df["run_atr"] = run
        entry &= run <= s.max_run_atr

    # Skip the warm-up period while the slow EMA settles.
    warmup = max(2 * s.macd_slow, s.atr_period, s.run_lookback) + 1
    if s.trend_ma and s.trend_ma_source == "bars":
        warmup = max(warmup, s.trend_ma)
    entry.iloc[:warmup] = False
    df["entry_signal"] = entry.fillna(False).astype(bool)
    return df
