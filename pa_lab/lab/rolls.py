"""Roll rules: no entries in the last N minutes before a roll; an open trade
closes at the close of the last bar that opens before the roll."""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_roll_flags(bars: pd.DataFrame, rolls: pd.DataFrame, minutes_before: int = 60,
                   ts_col: str = "ts_event") -> pd.DataFrame:
    """Adds:
      next_roll_utc   - the next roll at or after the bar's open
      roll_no_entry   - bar opens within `minutes_before` of the next roll
      roll_force_exit - last bar opening strictly before a roll (exit at its close)
    """
    out = bars.copy()
    ts = pd.to_datetime(out[ts_col], utc=True)
    rt = pd.to_datetime(rolls["roll_time_utc"], utc=True).sort_values().to_numpy()
    tsv = ts.to_numpy()
    j = np.searchsorted(rt, tsv, side="right")  # first roll strictly after the bar open
    nxt = pd.Series(pd.to_datetime(np.r_[rt, rt[:0]], utc=True)).reindex(j).to_numpy()
    out["next_roll_utc"] = pd.to_datetime(nxt, utc=True)
    until = (out["next_roll_utc"] - ts).dt.total_seconds() / 60
    out["roll_no_entry"] = (until <= minutes_before).fillna(False).to_numpy()
    last_before = np.searchsorted(tsv, rt, side="left") - 1
    force = np.zeros(len(out), dtype=bool)
    force[last_before[last_before >= 0]] = True
    out["roll_force_exit"] = force
    return out
