"""1-minute Nasdaq-100 (NQ) and S&P 500 (ES) bars from HistData.com.

HistData stamps bars in EST with no daylight saving (always UTC-5). Here every
bar is converted to New York local time, so 09:30 is the cash open all year.
A bar stamped 09:30 covers 09:30:00-09:30:59.

These are index CFD quotes, not CME futures: same points (no roll gaps), but
the futures trade at a small premium (the basis) and real fills differ.
"""
from __future__ import annotations

import io
import zipfile
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent / "data"
RAW = ROOT / "histdata"
CACHE = ROOT / "minute"
CACHE.mkdir(parents=True, exist_ok=True)
PAIR = {"NQ": "NSXUSD", "ES": "SPXUSD"}


def _read_zip(p: Path) -> pd.DataFrame:
    with zipfile.ZipFile(p) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        txt = z.read(name)
    df = pd.read_csv(io.BytesIO(txt), sep=";", header=None,
                     names=["ts", "open", "high", "low", "close", "vol"])
    df["ts"] = pd.to_datetime(df["ts"], format="%Y%m%d %H%M%S")
    return df.drop(columns="vol")


@lru_cache(maxsize=4)
def minutes(sym: str) -> pd.DataFrame:
    """All 1-minute bars for 'NQ' or 'ES', indexed by New York local time."""
    out = CACHE / f"{sym}_1m.pkl"
    files = sorted(RAW.glob(f"DAT_ASCII_{PAIR[sym]}_M1_*.zip"))
    if out.exists() and out.stat().st_mtime > max(f.stat().st_mtime for f in files):
        return pd.read_pickle(out)
    df = pd.concat([_read_zip(f) for f in files]).drop_duplicates("ts").sort_values("ts")
    utc = (df["ts"] + pd.Timedelta(hours=5)).dt.tz_localize("UTC")
    df.index = utc.dt.tz_convert("America/New_York").dt.tz_localize(None)
    df = df.drop(columns="ts")
    df = df[~df.index.duplicated()]
    df.to_pickle(out)
    return df


@lru_cache(maxsize=4)
def rth(sym: str) -> pd.DataFrame:
    """Regular session bars 09:30-15:59 with a 'day' column and minute-of-session 'm' (0..389)."""
    df = minutes(sym)
    t = df.index.hour * 60 + df.index.minute
    x = df[(t >= 570) & (t < 960)].copy()
    x["day"] = x.index.normalize()
    x["m"] = (x.index.hour * 60 + x.index.minute) - 570
    # keep days with a reasonably complete session (holidays/half days have fewer bars)
    n = x.groupby("day")["m"].transform("size")
    return x[n >= 200]


@lru_cache(maxsize=4)
def daily_rth(sym: str) -> pd.DataFrame:
    x = rth(sym)
    g = x.groupby("day")
    d = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                      "close": g["close"].last(), "bars": g.size()})
    return d


@lru_cache(maxsize=4)
def daily_globex(sym: str) -> pd.DataFrame:
    """Futures-style daily bars: 18:00 the evening before to 17:00, labelled by the 17:00 date."""
    df = minutes(sym)
    lab = (df.index + pd.Timedelta(hours=6)).normalize()  # 18:00 rolls to the next day
    g = df.groupby(lab)
    d = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                      "close": g["close"].last(), "bars": g.size()})
    d = d[d.index.dayofweek < 5]
    return d[d["bars"] >= 600]


def day_matrix(sym: str, field: str) -> pd.DataFrame:
    """days x 390 minutes matrix of one field for the regular session (NaN where missing),
    forward-filled within each day."""
    x = rth(sym)
    m = x.pivot(index="day", columns="m", values=field).reindex(columns=range(390))
    return m.ffill(axis=1)
