"""Turns a price history into entry and exit signals.

Every signal on bar t uses only data up to and including bar t's close. The
backtester acts on it at bar t+1's open, so nothing looks into the future.
"""

import pandas as pd

from config import Strategy
from data import bar_ends, bar_minutes
from indicators import atr, ema, macd, sma


def lower_tf_agreement(chart: pd.DataFrame, interval: str, lower: dict[str, pd.DataFrame],
                       s: Strategy) -> pd.DataFrame:
    """For each chart bar, count the lower timeframes whose MACD agrees with a buy (up) or a
    short (down), using only lower bars that had CLOSED by the time the chart bar closed.
    A 45m bar that straddles the end of a 2h bar (11:00-11:45 vs 9:30-11:30) is not used."""
    chart_end = pd.Series(bar_ends(chart.index, interval), index=chart.index)
    window = pd.Timedelta(minutes=bar_minutes(interval))
    usable = [tf for tf in s.confirm_tfs if bar_minutes(tf) < bar_minutes(interval)]
    # mtf_max: how many lower timeframes could agree; mtf_n: how many had data on this bar.
    out = pd.DataFrame({"mtf_up": 0, "mtf_down": 0, "mtf_n": 0, "mtf_max": len(usable)}, index=chart.index)
    for tf in usable:
        bars = lower.get(tf)
        if bars is None or bars.empty:
            continue
        m = macd(bars["Close"], s.macd_fast, s.macd_slow, s.macd_signal)
        rising = m["macd_hist"] > m["macd_hist"].shift(1)
        falling = m["macd_hist"] < m["macd_hist"].shift(1)
        # Until the lower MACD has warmed up (2 x slow bars) its reading is unknown, not "no".
        ready = (pd.Series(range(len(bars)), index=bars.index) >= 2 * s.macd_slow).to_numpy()
        up = ((m["macd"] > m["macd_signal"]) & rising).to_numpy()
        down = ((m["macd"] < m["macd_signal"]) & falling).to_numpy()
        end = bar_ends(bars.index, tf)
        lo = pd.DataFrame({"end": end, "lower_end": end,
                           "up": pd.Series(up, dtype=float).where(ready).to_numpy(),
                           "down": pd.Series(down, dtype=float).where(ready).to_numpy()}).sort_values("end")
        left = pd.DataFrame({"end": chart_end.to_numpy(), "start": chart.index.to_numpy(),
                             "i": range(len(chart))}).sort_values("end")
        # Latest lower bar that closed at or before the chart bar's close...
        hit = pd.merge_asof(left, lo, on="end", direction="backward", tolerance=window).sort_values("i")
        # ...and closed after the chart bar opened (never yesterday's bar on a daily chart).
        stale = ~(hit["lower_end"] > hit["start"])
        hit.loc[stale, ["up", "down"]] = float("nan")
        known = hit["up"].notna().to_numpy()
        out["mtf_n"] += known.astype(int)
        out["mtf_up"] += (hit["up"] == 1).to_numpy().astype(int)
        out["mtf_down"] += (hit["down"] == 1).to_numpy().astype(int)
    return out


def add_signals(prices: pd.DataFrame, s: Strategy, daily: pd.DataFrame | None = None,
                lower: dict[str, pd.DataFrame] | None = None, interval: str = "1d") -> pd.DataFrame:
    """prices: bars of the chart timeframe. daily: daily bars of the same stock, needed
    for a 200-day average on an intraday chart. Without it the average is taken over bars.
    lower: {"15m": bars, ...} for the lower-timeframe check; interval: the chart's bar size."""
    df = prices.copy()
    df = df.join(macd(df["Close"], s.macd_fast, s.macd_slow, s.macd_signal))
    df["atr"] = atr(df, s.atr_period)
    df["momentum_20"] = df["Close"].pct_change(20)
    # How far from zero the MACD is, in ATRs. The buffer filters on this; it's logged per trade.
    df["depth_atr"] = df["macd"] / df["atr"]
    if lower:
        df = df.join(lower_tf_agreement(df, interval, lower, s))

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

    no = pd.Series(False, index=df.index)
    df["entry_signal"] = finish(_long_entry(df, s)) if s.sides in ("long", "both") else no
    df["short_signal"] = finish(_short_entry(df, s)) if s.sides in ("short", "both") else no
    return df


def _long_entry(df: pd.DataFrame, s: Strategy) -> pd.Series:
    if s.entry == "signal_cross":
        entry = df["cross_up"].copy()
        if s.require_below_zero:
            entry &= df["macd"] < -s.min_macd_depth_atr * df["atr"] if s.min_macd_depth_atr else df["macd"] < 0
    elif s.entry == "zero_cross":
        entry = df["zero_cross_up"].copy()
    else:
        raise ValueError(f"unknown entry type {s.entry!r}")
    if s.trend_ma:
        entry &= df["Close"] < df["trend_ma"] if s.trend_side == "below" else df["Close"] > df["trend_ma"]
    if s.max_run_atr is not None:
        entry &= df["run_atr"] <= s.max_run_atr
    return entry & _confirmed(df, s, "mtf_up")


def _confirmed(df: pd.DataFrame, s: Strategy, col: str) -> pd.Series:
    """Enough lower timeframes agree. If the chart has fewer lower timeframes than confirm_min
    (only 15m sits under a 30m chart), all of those must agree. A lower timeframe with no data
    on that bar (outside Yahoo's 60 days) counts as not agreeing, so no trade there.
    With no lower data loaded at all, no trade."""
    if not s.confirm_min:
        return pd.Series(True, index=df.index)
    if col not in df:
        return pd.Series(False, index=df.index)
    return df[col] >= df["mtf_max"].clip(upper=s.confirm_min)


def _short_entry(df: pd.DataFrame, s: Strategy) -> pd.Series:
    """The long rule turned upside down: MACD crosses DOWN through its signal line while
    ABOVE zero, and (by default) price is ABOVE the 200-day EMA, i.e. stretched too far up."""
    if s.entry == "signal_cross":
        entry = df["cross_down"].copy()
        if s.require_below_zero:
            entry &= df["macd"] > s.min_macd_depth_atr * df["atr"] if s.min_macd_depth_atr else df["macd"] > 0
    elif s.entry == "zero_cross":
        entry = df["zero_cross_down"].copy()
    else:
        raise ValueError(f"unknown entry type {s.entry!r}")
    if s.trend_ma:
        entry &= df["Close"] > df["trend_ma"] if s.trend_side == "below" else df["Close"] < df["trend_ma"]
    if s.max_run_atr is not None:
        entry &= df["run_atr_down"] <= s.max_run_atr
    return entry & _confirmed(df, s, "mtf_down")
