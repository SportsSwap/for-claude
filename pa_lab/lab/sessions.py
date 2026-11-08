"""Session dating in America/New_York.

A session runs 18:00 -> 17:00 ET and is dated by the day it ends, so Sunday
evening belongs to Monday. Bars in the 17:00 halt hour belong to no session.
Because CME DST changes happen at 02:00 ET on a Sunday, while the market is
closed, no session ever spans a clock change.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from .config import TZ


def to_et(ts_utc: pd.Series) -> pd.Series:
    return pd.to_datetime(ts_utc, utc=True).dt.tz_convert(TZ)


def session_date(ts_utc: pd.Series) -> pd.Series:
    """Date of the session a UTC bar-open time belongs to (wall-clock + 6h)."""
    wall = to_et(ts_utc).dt.tz_localize(None)
    return (wall + pd.Timedelta(hours=6)).dt.normalize().dt.date


def in_halt_hour(ts_utc: pd.Series, halt_hour: int = 17) -> pd.Series:
    return to_et(ts_utc).dt.hour == halt_hour


def _localize(wall: pd.Series) -> pd.Series:
    return wall.dt.tz_localize(TZ, nonexistent="shift_forward", ambiguous="raise").dt.tz_convert("UTC")


def session_bounds(sessions) -> pd.DataFrame:
    """UTC open (18:00 ET the evening before) and close (17:00 ET) per session."""
    s = pd.to_datetime(pd.Series(sorted(set(sessions))))
    out = pd.DataFrame({"session": s.dt.date})
    out["open_utc"] = _localize(s - pd.Timedelta(hours=6)).array
    out["close_utc"] = _localize(s + pd.Timedelta(hours=17)).array
    return out


def wall_boundaries(sessions, starts_et: list[str], end_et: str = "17:00") -> pd.DataFrame:
    """Fixed wall-clock bucket starts per session (used for 4h bars).

    starts_et are in session order; a start earlier than 18:00 belongs to the
    session's own calendar day, 18:00 and later to the evening before.
    """
    rows = []
    for d in sorted(set(sessions)):
        d = pd.Timestamp(d)
        walls = []
        for hhmm in starts_et + [end_et]:
            h, m = map(int, hhmm.split(":"))
            day = d - pd.Timedelta(days=1) if h >= 18 else d
            walls.append(day + pd.Timedelta(hours=h, minutes=m))
        for i in range(len(starts_et)):
            rows.append((d.date(), i, walls[i], walls[i + 1]))
    df = pd.DataFrame(rows, columns=["session", "bucket", "start_wall", "end_wall"])
    df["start_utc"] = _localize(df["start_wall"])
    df["end_utc"] = _localize(df["end_wall"])
    return df.drop(columns=["start_wall", "end_wall"])


def weekday_sessions(start: dt.date, end: dt.date) -> list[dt.date]:
    days = pd.bdate_range(start, end)
    return [d.date() for d in days]


def is_weekend(dates: pd.Series) -> np.ndarray:
    return pd.to_datetime(pd.Series(dates)).dt.day_of_week.to_numpy() >= 5
