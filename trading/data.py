"""Daily price data: Yahoo Finance via yfinance, cached to CSV.

You can also drop your own CSVs (Date, Open, High, Low, Close, Volume) into the
cache folder as TICKER.csv and run with --offline.
"""

from pathlib import Path
import sys

import pandas as pd

CACHE_DIR = Path(__file__).parent / "data"
COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def _download(ticker: str, start: str) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[COLUMNS].dropna()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "Date"
    return df


def load(tickers: list[str], start: str = "2015-01-01", refresh: bool = False,
         offline: bool = False, cache_dir: Path = CACHE_DIR) -> dict[str, pd.DataFrame]:
    cache_dir.mkdir(exist_ok=True)
    out = {}
    for t in tickers:
        path = cache_dir / f"{t}.csv"
        if path.exists() and not refresh:
            df = pd.read_csv(path, index_col="Date", parse_dates=True)
        elif offline:
            print(f"  {t}: no cached data, skipping", file=sys.stderr)
            continue
        else:
            try:
                df = _download(t, start)
            except Exception as e:  # network errors, delisted tickers
                print(f"  {t}: download failed ({e}), skipping", file=sys.stderr)
                continue
            if df.empty:
                print(f"  {t}: no data returned, skipping", file=sys.stderr)
                continue
            df.to_csv(path)
        out[t] = df[COLUMNS].sort_index()
    return out
