"""Turns a price history into entry and exit signals.

Every signal on day t uses only data up to and including day t's close. The
backtester acts on it at day t+1's open, so nothing looks into the future.
"""

import pandas as pd

from config import Strategy
from indicators import atr, macd, sma


def add_signals(prices: pd.DataFrame, s: Strategy) -> pd.DataFrame:
    df = prices.copy()
    df = df.join(macd(df["Close"], s.macd_fast, s.macd_slow, s.macd_signal))
    df["atr"] = atr(df, s.atr_period)
    df["momentum_20d"] = df["Close"].pct_change(20)

    above = df["macd"] > df["macd_signal"]
    was_above = above.shift(1, fill_value=False)
    df["cross_up"] = above & ~was_above
    df["cross_down"] = ~above & was_above

    entry = df["cross_up"].copy()
    if s.trend_sma:
        df["trend_sma"] = sma(df["Close"], s.trend_sma)
        entry &= df["Close"] > df["trend_sma"]
    if s.require_below_zero:
        entry &= df["macd"] < 0

    # Skip the warm-up period where the indicators are not yet reliable.
    warmup = max(s.macd_slow + s.macd_signal, s.trend_sma or 0, s.atr_period) + 1
    entry.iloc[:warmup] = False
    df["entry_signal"] = entry
    return df
