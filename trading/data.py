"""Price data from Yahoo Finance via yfinance, cached to CSV.

Daily bars go back as far as you like. Hourly bars only go back about 730 days on
Yahoo, so intraday backtests cover roughly the last two years. 2h and 4h bars are
built from 1h bars, aligned to the 9:30 New York open the way TradingView does it
(2h: 9:30, 11:30, 13:30, 15:30; 4h: 9:30, 13:30).

15m and 30m bars only go back 60 days on Yahoo. 45m bars are built from 15m bars
(9:30, 10:15, 11:00, ...). Each download of these is merged into the cache, so if
you run the scanner regularly the saved history keeps growing past 60 days.

You can also drop your own CSVs (Date, Open, High, Low, Close, Volume) into the
cache folder as TICKER_1d.csv or TICKER_1h.csv and run with --offline.
"""

from pathlib import Path
import sys

import pandas as pd

CACHE_DIR = Path(__file__).parent / "data"
COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
HOURLY_HISTORY_DAYS = 729
MINUTE_HISTORY_DAYS = 59

# interval -> (Yahoo interval to download, how many of those make one bar)
SOURCES = {"1d": ("1d", 1), "1h": ("1h", 1), "2h": ("1h", 2), "4h": ("1h", 4),
           "15m": ("15m", 1), "30m": ("30m", 1), "45m": ("15m", 3)}


def bar_minutes(interval: str) -> int:
    """Length of one bar in minutes (a daily bar counts as a whole day)."""
    if interval == "1d":
        return 24 * 60
    return int(interval[:-1]) * (60 if interval.endswith("h") else 1)


def bar_ends(index: pd.DatetimeIndex, interval: str) -> pd.DatetimeIndex:
    """When each bar closes: start + bar length, cut off at the 16:00 close (the last 2h bar
    of the day is only 30 minutes; a daily bar closes at 16:00)."""
    end = index + pd.Timedelta(minutes=bar_minutes(interval))
    close = index.normalize() + pd.Timedelta(hours=16)
    return end.where(end <= close, close)


def _download(ticker: str, start: str, interval: str) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(ticker, start=start, interval=interval, auto_adjust=True,
                     prepost=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[COLUMNS].dropna()
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    df.index = idx
    df.index.name = "Date"
    return df


def resample_session(bars: pd.DataFrame, n: int) -> pd.DataFrame:
    """Group every n bars into one, restarting at each day's open (1h x2 = 2h, 15m x3 = 45m)."""
    if n == 1:
        return bars
    day = bars.index.normalize()
    slot = bars.groupby(day).cumcount() // n
    out = bars.assign(ts=bars.index).groupby([day, slot.to_numpy()]).agg(
        ts=("ts", "first"), Open=("Open", "first"), High=("High", "max"),
        Low=("Low", "min"), Close=("Close", "last"), Volume=("Volume", "sum"))
    return out.set_index("ts").rename_axis("Date")[COLUMNS]


def _load_one(ticker: str, raw_interval: str, start: str, refresh: bool, offline: bool,
              cache_dir: Path) -> pd.DataFrame | None:
    path = cache_dir / f"{ticker}_{raw_interval}.csv"
    cached = pd.read_csv(path, index_col="Date", parse_dates=True) if path.exists() else None
    if cached is not None and not refresh:
        return cached
    if offline:
        print(f"  {ticker}: no cached {raw_interval} data, skipping", file=sys.stderr)
        return None
    try:
        df = _download(ticker, start, raw_interval)
    except Exception as e:  # network errors, delisted tickers
        print(f"  {ticker}: download failed ({e}), "
              + ("using cached data" if cached is not None else "skipping"), file=sys.stderr)
        return cached
    if df.empty:
        print(f"  {ticker}: no {raw_interval} data returned, skipping", file=sys.stderr)
        return cached
    if cached is not None and raw_interval != "1d":
        # Keep older intraday bars Yahoo no longer serves; new data wins on overlap.
        df = pd.concat([cached[COLUMNS], df])
        df = df[~df.index.duplicated(keep="last")].sort_index()
    df.to_csv(path)
    return df


def load(tickers: list[str], start: str = "2015-01-01", interval: str = "1d",
         refresh: bool = False, offline: bool = False,
         cache_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """interval: 1d, 1h, 2h, 4h, 15m, 30m or 45m."""
    cache_dir = cache_dir or CACHE_DIR
    cache_dir.mkdir(exist_ok=True)
    raw, n = SOURCES[interval]
    if raw != "1d":
        days = HOURLY_HISTORY_DAYS if raw == "1h" else MINUTE_HISTORY_DAYS
        earliest = pd.Timestamp.today().normalize() - pd.Timedelta(days=days)
        start = max(pd.Timestamp(start), earliest).strftime("%Y-%m-%d")
    out = {}
    for t in tickers:
        df = _load_one(t, raw, start, refresh, offline, cache_dir)
        if df is None:
            continue
        out[t] = resample_session(df[COLUMNS].sort_index(), n)
    return out


def load_higher(tickers: list[str], start: str, interval: str, tfs: tuple[str, ...],
                daily: dict[str, pd.DataFrame] | None = None, refresh: bool = False, offline: bool = False,
                cache_dir: Path | None = None) -> dict[str, dict[str, pd.DataFrame]]:
    """Bars of the timeframes in tfs that are longer than the chart's, as {ticker: {"4h": bars, ...}}.
    Pass the daily bars you already loaded to avoid loading them twice."""
    frames = {}
    for tf in tfs:
        if bar_minutes(tf) <= bar_minutes(interval):
            continue
        frames[tf] = daily if tf == "1d" and daily is not None else load(tickers, start, tf, refresh, offline, cache_dir)
    return {t: {tf: by_t[t] for tf, by_t in frames.items() if t in by_t} for t in tickers}


def load_lower(tickers: list[str], start: str, refresh: bool = False, offline: bool = False,
               cache_dir: Path | None = None) -> dict[str, dict[str, pd.DataFrame]]:
    """15m, 30m and 45m bars for the lower-timeframe check, as {ticker: {"15m": bars, ...}}.
    15m is downloaded once and also grouped into 45m. Bars that haven't finished yet (the one
    forming right now during market hours) are dropped, so a half-built bar can't 'agree'."""
    m15 = load(tickers, start, "15m", refresh, offline, cache_dir)
    m30 = load(tickers, start, "30m", refresh, offline, cache_dir)
    now = pd.Timestamp.now(tz="America/New_York").tz_localize(None)
    out: dict[str, dict[str, pd.DataFrame]] = {}
    for t in tickers:
        frames = {"15m": m15.get(t), "30m": m30.get(t)}
        if frames["15m"] is not None:
            frames["45m"] = resample_session(frames["15m"], 3)
        kept = {}
        for tf, df in frames.items():
            if df is None or df.empty:
                continue
            kept[tf] = df[bar_ends(df.index, tf) <= now]
        if kept:
            out[t] = kept
    return out
