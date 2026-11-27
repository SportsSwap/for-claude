"""Daily price data from Yahoo Finance, cached on disk.

Prices are split- and dividend-adjusted (auto_adjust=True), so open, high,
low and close all include dividends. That matters: an ETF strategy that
ignores dividends understates buy-and-hold by ~2% a year.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd

CACHE = Path(__file__).resolve().parent.parent / "data"
CACHE.mkdir(exist_ok=True)


def _cache_path(ticker: str, interval: str) -> Path:
    safe = ticker.replace("^", "IDX_").replace("=", "_").replace("/", "_")
    return CACHE / f"{safe}_{interval}.csv"


def load(ticker: str, start: str = "1990-01-01", interval: str = "1d",
         refresh_days: float = 1.0) -> pd.DataFrame:
    """OHLCV for one ticker. Columns: open high low close volume."""
    path = _cache_path(ticker, interval)
    if path.exists() and (time.time() - path.stat().st_mtime) < refresh_days * 86400:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
    else:
        import yfinance as yf
        for attempt in range(4):
            try:
                if interval == "1d":
                    raw = yf.download(ticker, start="1980-01-01", interval=interval,
                                      progress=False, auto_adjust=True, threads=False)
                else:
                    raw = yf.download(ticker, period="730d", interval=interval,
                                      progress=False, auto_adjust=True, threads=False)
                break
            except Exception:  # network hiccup
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"download failed for {ticker}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw = raw.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        raw = raw.dropna(subset=["close"])
        raw.index = pd.to_datetime(raw.index).tz_localize(None)
        if raw.empty:
            raise RuntimeError(f"no data for {ticker}")
        raw.to_csv(path)
        df = raw
    df = df[df.index >= pd.Timestamp(start)]
    # Yahoo occasionally has open == 0 or NaN on old bars; fall back to prior close.
    bad = (df["open"] <= 0) | df["open"].isna()
    df.loc[bad, "open"] = df["close"].shift(1)[bad]
    return df.dropna(subset=["open", "close"])


def panel(tickers: list[str], field: str = "close", start: str = "1990-01-01",
          how: str = "inner") -> pd.DataFrame:
    """One field for many tickers, aligned on dates."""
    frames = {t: load(t, start)[field] for t in tickers}
    df = pd.concat(frames, axis=1, join=how)
    return df.sort_index()


def ohlc_panel(tickers: list[str], start: str = "1990-01-01", how: str = "inner") -> dict:
    """{'open': df, 'high': df, 'low': df, 'close': df} aligned on common dates."""
    data = {t: load(t, start) for t in tickers}
    idx = None
    for d in data.values():
        idx = d.index if idx is None else (idx.intersection(d.index) if how == "inner" else idx.union(d.index))
    out = {}
    for f in ["open", "high", "low", "close", "volume"]:
        out[f] = pd.concat({t: d[f].reindex(idx) for t, d in data.items()}, axis=1)
    return out
