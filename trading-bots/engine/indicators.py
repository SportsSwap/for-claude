"""Indicators. Every one uses data up to and including bar t only."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(x, n):
    return x.rolling(n, min_periods=n).mean()


def ema(x, n):
    return x.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(close, n=2):
    """Wilder RSI."""
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100.0)


def ibs(high, low, close):
    """Internal bar strength: where the close sits in the day's range (0..1)."""
    rng = (high - low).replace(0, np.nan)
    return ((close - low) / rng).fillna(0.5)


def realized_vol(close, n=20, ann=252):
    return np.log(close).diff().rolling(n, min_periods=n).std() * np.sqrt(ann)


def month_end_flags(index: pd.DatetimeIndex) -> pd.Series:
    """True on the last trading day of each month in the data."""
    s = pd.Series(index.month, index=index)
    return s != s.shift(-1)


def trading_day_of_month(index: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    """(day number from the start of the month 1.., day number from the end
    -1.., i.e. -1 = last trading day). The 'from end' count for the current
    month uses the calendar, so it is known in advance (holidays aside)."""
    df = pd.DataFrame(index=index)
    ym = index.year * 100 + index.month
    df["ym"] = ym
    df["fwd"] = df.groupby("ym").cumcount() + 1
    df["bwd"] = -(df.groupby("ym").cumcount(ascending=False) + 1)
    return df["fwd"], df["bwd"]


def resample_month_end(df: pd.DataFrame) -> pd.DataFrame:
    """Rows on the last trading day of each month."""
    return df[month_end_flags(df.index)]
