"""Higher charts from 1-minute bars, counted from the 18:00 ET session open.

Each bar carries:
  ts_open   - nominal start of the bucket (UTC)
  ts_avail  - nominal end of the bucket (UTC); the bar is usable only from here
  n_1m      - how many 1-minute bars built it (gaps are never filled)
4h buckets: 18-22, 22-02, 02-06, 06-10, 10-14, 14-17 ET. Daily = whole session.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .sessions import session_bounds, wall_boundaries

ORDER = ["1m", "5m", "15m", "1h", "4h", "daily"]
STEP_MIN = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}
FOUR_H = ["18:00", "22:00", "02:00", "06:00", "10:00", "14:00"]


def lower(chart: str, steps: int = 1) -> str | None:
    i = ORDER.index(chart) - steps
    return ORDER[i] if i >= 0 else None


def higher(chart: str, steps: int = 1) -> str | None:
    i = ORDER.index(chart) + steps
    return ORDER[i] if i < len(ORDER) else None


def _agg(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    g = df.groupby(keys, sort=True)
    out = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                close=("close", "last"), volume=("volume", "sum"),
                contract=("contract", "last"), n_1m=("open", "size"),
                first_1m=("ts_event", "first"))
    return out.reset_index()


def build(bars_1m: pd.DataFrame, chart: str) -> pd.DataFrame:
    """bars_1m: clean 1-minute bars with ts_event (UTC) and session, sorted."""
    b = bars_1m.sort_values("ts_event").reset_index(drop=True)
    b["ts_event"] = pd.to_datetime(b["ts_event"], utc=True)
    bounds = session_bounds(b["session"])
    b = b.merge(bounds, on="session", how="left")
    if chart == "1m":
        out = b[["session", "ts_event", "open", "high", "low", "close", "volume", "contract"]].copy()
        out = out.rename(columns={"ts_event": "ts_open"})
        out["ts_avail"] = out["ts_open"] + pd.Timedelta(minutes=1)
        out["n_1m"] = 1
    elif chart in STEP_MIN:
        step = pd.Timedelta(minutes=STEP_MIN[chart])
        k = ((b["ts_event"] - b["open_utc"]) // step).astype(int)
        b["bucket"] = k
        out = _agg(b, ["session", "bucket"])
        out = out.merge(bounds, on="session")
        out["ts_open"] = out["open_utc"] + out["bucket"] * step
        out["ts_avail"] = np.minimum(out["ts_open"] + step, out["close_utc"])
    elif chart == "4h":
        wb = wall_boundaries(b["session"], FOUR_H)
        wb = wb.sort_values("start_utc").reset_index(drop=True)
        idx = np.searchsorted(wb["start_utc"].to_numpy(), b["ts_event"].to_numpy(), side="right") - 1
        b["bucket"] = wb["bucket"].to_numpy()[idx]
        out = _agg(b, ["session", "bucket"]).merge(wb, on=["session", "bucket"])
        out["ts_open"], out["ts_avail"] = out["start_utc"], out["end_utc"]
    elif chart == "daily":
        b["bucket"] = 0
        out = _agg(b, ["session", "bucket"]).merge(bounds, on="session")
        out["ts_open"], out["ts_avail"] = out["open_utc"], out["close_utc"]
    else:
        raise ValueError(chart)
    cols = ["session", "ts_open", "ts_avail", "open", "high", "low", "close", "volume", "contract", "n_1m"]
    out = out[cols].sort_values("ts_open").reset_index(drop=True)
    out["ts_open"] = pd.to_datetime(out["ts_open"], utc=True)
    out["ts_avail"] = pd.to_datetime(out["ts_avail"], utc=True)
    return out


def build_all(bars_1m: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {c: build(bars_1m, c) for c in ORDER}


def align(lower_bars: pd.DataFrame, higher_bars: pd.DataFrame, cols: list[str],
          suffix: str) -> pd.DataFrame:
    """Attach to each lower-chart bar the latest higher-chart bar that had
    closed by the time the lower bar closed (ts_avail <= lower ts_avail)."""
    h = higher_bars[["ts_avail"] + cols].rename(columns={c: f"{c}_{suffix}" for c in cols})
    h = h.rename(columns={"ts_avail": f"ts_avail_{suffix}"})
    lo = lower_bars.sort_values("ts_avail")
    return pd.merge_asof(lo, h.sort_values(f"ts_avail_{suffix}"), left_on="ts_avail",
                         right_on=f"ts_avail_{suffix}", direction="backward",
                         allow_exact_matches=True)
