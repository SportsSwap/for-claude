"""Turns a price history into entry and exit signals.

Every signal on bar t uses only data up to and including bar t's close. The
backtester acts on it at bar t+1's open, so nothing looks into the future.
"""

import pandas as pd

from config import Strategy
from data import bar_ends, bar_minutes
from indicators import atr, ema, macd, sma


def marker_agreement(chart: pd.DataFrame, interval: str, markers: dict[str, pd.DataFrame],
                     s: Strategy) -> pd.DataFrame:
    """For each chart bar, count the marker timeframes (30m, 45m, 1h) whose MACD is above its
    signal line (mk_up) or below it (mk_down), using the last marker bar that had FINISHED by the
    time the chart bar closed. A 45m bar that straddles the end of a 2h bar (11:00-11:45 vs
    9:30-11:30) is not used. mk_n: how many markers had data on that bar."""
    chart_end = bar_ends(chart.index, interval)
    window = pd.Timedelta(minutes=bar_minutes(interval))
    out = pd.DataFrame({"mk_up": 0, "mk_down": 0, "mk_n": 0}, index=chart.index)
    left = pd.DataFrame({"end": chart_end, "start": chart.index, "i": range(len(chart))}).sort_values("end")
    for tf in s.marker_tfs:
        bars = markers.get(tf)
        if bars is None or bars.empty or bar_minutes(tf) >= bar_minutes(interval):
            continue
        m = macd(bars["Close"], s.macd_fast, s.macd_slow, s.macd_signal)
        ready = (pd.Series(range(len(bars))) >= 2 * s.macd_slow).to_numpy()   # warm-up: unknown
        end = bar_ends(bars.index, tf)
        lo = pd.DataFrame({"end": end, "lower_end": end,
                           "up": pd.Series((m["macd"] > m["macd_signal"]).to_numpy(), dtype=float).where(ready).to_numpy(),
                           "down": pd.Series((m["macd"] < m["macd_signal"]).to_numpy(), dtype=float).where(ready).to_numpy()}
                          ).sort_values("end")
        hit = pd.merge_asof(left, lo, on="end", direction="backward", tolerance=window).sort_values("i")
        # The marker bar must have closed inside this chart bar (never one from a previous day).
        hit.loc[~(hit["lower_end"] > hit["start"]), ["up", "down"]] = float("nan")
        out["mk_n"] += hit["up"].notna().to_numpy().astype(int)
        out["mk_up"] += (hit["up"] == 1).to_numpy().astype(int)
        out["mk_down"] += (hit["down"] == 1).to_numpy().astype(int)
    return out


def add_signals(prices: pd.DataFrame, s: Strategy, daily: pd.DataFrame | None = None,
                markers: dict[str, pd.DataFrame] | None = None, interval: str = "2h") -> pd.DataFrame:
    """prices: bars of the chart timeframe (2h or 4h). daily: daily bars of the same stock, for
    the 200-day EMA. markers: {"30m": bars, "45m": bars, "1h": bars}. Without markers the marker
    check is skipped (the backtester and scanner always pass them)."""
    df = prices.copy()
    df = df.join(macd(df["Close"], s.macd_fast, s.macd_slow, s.macd_signal))
    df["atr"] = atr(df, s.atr_period)
    df["momentum_20"] = df["Close"].pct_change(20)

    above = df["macd"] > df["macd_signal"]
    was_above = above.shift(1, fill_value=False)
    df["cross_up"] = above & ~was_above
    df["cross_down"] = ~above & was_above
    df["zero_cross_up"] = (df["macd"] > 0) & (df["macd"].shift(1) <= 0)
    df["zero_cross_down"] = (df["macd"] < 0) & (df["macd"].shift(1) >= 0)

    if s.trend_ma:
        average = ema if s.trend_ma_type == "ema" else sma
        if s.trend_ma_source == "daily" and daily is not None:
            # Yesterday's 200-day value: what you could see before today's open.
            ma = average(daily["Close"], s.trend_ma).shift(1)
            df["trend_ma"] = ma.reindex(df.index.normalize(), method="ffill").to_numpy()
        else:
            df["trend_ma"] = average(df["Close"], s.trend_ma)
    if s.max_run_atr is not None:
        df["run_atr"] = (df["Close"] - df["Low"].rolling(s.run_lookback).min()) / df["atr"]
        df["run_atr_down"] = (df["High"].rolling(s.run_lookback).max() - df["Close"]) / df["atr"]

    # Skip the warm-up period while the slow EMA settles.
    warmup = max(2 * s.macd_slow, s.atr_period, s.run_lookback) + 1
    if s.trend_ma and s.trend_ma_source == "bars":
        warmup = max(warmup, s.trend_ma)

    def finish(sig: pd.Series) -> pd.Series:
        sig = sig.copy()
        sig.iloc[:warmup] = False
        return sig.fillna(False).astype(bool)

    if markers is not None:
        df = df.join(marker_agreement(df, interval, markers, s))

    no = pd.Series(False, index=df.index)
    df["entry_signal"] = finish(_long_entry(df, s)) if s.sides in ("long", "both") else no
    df["short_signal"] = finish(_short_entry(df, s)) if s.sides in ("short", "both") else no
    return df


def _long_entry(df: pd.DataFrame, s: Strategy) -> pd.Series:
    if s.entry == "signal_cross":
        entry = df["cross_up"].copy()
        if s.require_below_zero:
            entry &= df["macd"] < 0
    elif s.entry == "zero_cross":
        entry = df["zero_cross_up"].copy()
    else:
        raise ValueError(f"unknown entry type {s.entry!r}")
    if s.trend_ma:
        entry &= df["Close"] < df["trend_ma"] if s.trend_side == "below" else df["Close"] > df["trend_ma"]
    if s.max_run_atr is not None:
        entry &= df["run_atr"] <= s.max_run_atr
    return entry & _markers_agree(df, s, "mk_up")


def _markers_agree(df: pd.DataFrame, s: Strategy, col: str) -> pd.Series:
    """Every marker (30m, 45m, 1h) with data on this bar agrees, and at least one has data."""
    if not s.require_markers or "mk_n" not in df:
        return pd.Series(True, index=df.index)
    return (df["mk_n"] >= 1) & (df[col] == df["mk_n"])


def _short_entry(df: pd.DataFrame, s: Strategy) -> pd.Series:
    """The long rule turned upside down: MACD crosses DOWN through its signal line while
    ABOVE zero, and (by default) price is BELOW the 200-day EMA, i.e. already in a downtrend."""
    if s.entry == "signal_cross":
        entry = df["cross_down"].copy()
        if s.require_below_zero:
            entry &= df["macd"] > 0
    elif s.entry == "zero_cross":
        entry = df["zero_cross_down"].copy()
    else:
        raise ValueError(f"unknown entry type {s.entry!r}")
    if s.trend_ma:
        entry &= df["Close"] > df["trend_ma"] if s.trend_side == "below" else df["Close"] < df["trend_ma"]
    if s.max_run_atr is not None:
        entry &= df["run_atr_down"] <= s.max_run_atr
    return entry & _markers_agree(df, s, "mk_down")
