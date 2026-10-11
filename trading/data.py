"""Price data from Yahoo Finance via yfinance, cached to CSV.

Daily bars go back as far as you like. Hourly bars only go back about 730 days on
Yahoo, so intraday backtests cover roughly the last two years. 2h and 4h bars are
built from 1h bars, aligned to the 9:30 New York open the way TradingView does it
(2h: 9:30, 11:30, 13:30, 15:30; 4h: 9:30, 13:30).

You can also drop your own CSVs (Date, Open, High, Low, Close, Volume) into the
cache folder as TICKER_1d.csv or TICKER_1h.csv and run with --offline.
"""

from pathlib import Path
import sys

import pandas as pd

CACHE_DIR = Path(__file__).parent / "data"
COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
HOURLY_HISTORY_DAYS = 729


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


def resample_session(hourly: pd.DataFrame, hours: int) -> pd.DataFrame:
    """Group 1h bars into N-hour bars that restart at each day's open."""
    if hours == 1:
        return hourly
    day = hourly.index.normalize()
    slot = hourly.groupby(day).cumcount() // hours
    out = hourly.assign(ts=hourly.index).groupby([day, slot.to_numpy()]).agg(
        ts=("ts", "first"), Open=("Open", "first"), High=("High", "max"),
        Low=("Low", "min"), Close=("Close", "last"), Volume=("Volume", "sum"))
    return out.set_index("ts").rename_axis("Date")[COLUMNS]


def _load_one(ticker: str, raw_interval: str, start: str, refresh: bool, offline: bool,
              cache_dir: Path) -> pd.DataFrame | None:
    path = cache_dir / f"{ticker}_{raw_interval}.csv"
    if path.exists() and not refresh:
        return pd.read_csv(path, index_col="Date", parse_dates=True)
    if offline:
        print(f"  {ticker}: no cached {raw_interval} data, skipping", file=sys.stderr)
        return None
    try:
        df = _download(ticker, start, raw_interval)
    except Exception as e:  # network errors, delisted tickers
        print(f"  {ticker}: download failed ({e}), skipping", file=sys.stderr)
        return None
    if df.empty:
        print(f"  {ticker}: no {raw_interval} data returned, skipping", file=sys.stderr)
        return None
    df.to_csv(path)
    return df


def load(tickers: list[str], start: str = "2015-01-01", interval: str = "1d",
         refresh: bool = False, offline: bool = False,
         cache_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """interval: 1d, 1h, 2h or 4h."""
    cache_dir = cache_dir or CACHE_DIR
    cache_dir.mkdir(exist_ok=True)
    raw = "1d" if interval == "1d" else "1h"
    if raw == "1h":
        earliest = pd.Timestamp.today().normalize() - pd.Timedelta(days=HOURLY_HISTORY_DAYS)
        start = max(pd.Timestamp(start), earliest).strftime("%Y-%m-%d")
    out = {}
    for t in tickers:
        df = _load_one(t, raw, start, refresh, offline, cache_dir)
        if df is None:
            continue
        df = df[COLUMNS].sort_index()
        if interval != "1d":
            df = resample_session(df, int(interval.rstrip("h")))
        out[t] = df
    return out
