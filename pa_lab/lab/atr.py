"""Wilder's ATR using only bars before the current one.

atr[i] is the 14-bar Wilder ATR computed through bar i-1, so a decision made on
bar i never sees bar i's own range. The first 14 values are NaN (bar 14 is the
first with 14 prior true ranges).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import lfilter


def true_range(high, low, close) -> np.ndarray:
    h, l, c = (np.asarray(x, dtype=float) for x in (high, low, close))
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - l, np.abs(h - pc), np.abs(l - pc)]), axis=0)
    return tr


def wilder_through(tr: np.ndarray, n: int = 14) -> np.ndarray:
    """ATR including bar i (the classic definition)."""
    out = np.full(len(tr), np.nan)
    if len(tr) < n:
        return out
    seed = tr[:n].mean()
    out[n - 1] = seed
    if len(tr) > n:
        a = 1.0 / n
        y, _ = lfilter([a], [1, -(1 - a)], tr[n:], zi=[(1 - a) * seed])
        out[n:] = y
    return out


def atr_prior(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = true_range(df["high"], df["low"], df["close"])
    through = wilder_through(tr, n)
    return pd.Series(np.r_[np.nan, through[:-1]], index=df.index, name="atr")
