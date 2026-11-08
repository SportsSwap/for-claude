import datetime as dt

import numpy as np
import pandas as pd

from lab import charts
from lab.atr import atr_prior, true_range
from lab.rolls import add_roll_flags
from lab.sessions import session_bounds, session_date


def full_session(day="2022-01-04", seed=0):
    b = session_bounds([dt.date.fromisoformat(day)])
    ts = pd.date_range(b.open_utc.iat[0], b.close_utc.iat[0], freq="1min", inclusive="left")
    g = np.random.default_rng(seed)
    c = 100 + np.cumsum(g.normal(0, 1, len(ts)))
    o = np.r_[100, c[:-1]]
    df = pd.DataFrame({"ts_event": ts, "open": o, "high": np.maximum(o, c) + 0.5,
                       "low": np.minimum(o, c) - 0.5, "close": c, "volume": 1, "contract": "X"})
    df["session"] = session_date(df["ts_event"])
    return df


def test_five_minute_bars_count_from_1800_open():
    m = full_session()
    b5 = charts.build(m, "5m")
    assert len(b5) == 23 * 12
    first = b5.iloc[0]
    assert first.ts_open.tz_convert("America/New_York").strftime("%H:%M") == "18:00"
    assert first.open == m.open.iat[0] and first.close == m.close.iat[4]
    assert first.high == m.high.iloc[:5].max() and first.n_1m == 5
    assert first.ts_avail == first.ts_open + pd.Timedelta(minutes=5)


def test_four_hour_buckets():
    b4 = charts.build(full_session(), "4h")
    starts = [t.tz_convert("America/New_York").strftime("%H") for t in b4.ts_open]
    ends = [t.tz_convert("America/New_York").strftime("%H") for t in b4.ts_avail]
    assert starts == ["18", "22", "02", "06", "10", "14"]
    assert ends == ["22", "02", "06", "10", "14", "17"]
    assert b4.n_1m.tolist() == [240, 240, 240, 240, 240, 180]


def test_daily_bar_is_whole_session_and_usable_at_close():
    m = full_session()
    d = charts.build(m, "daily")
    assert len(d) == 1 and d.n_1m.iat[0] == 1380
    assert d.ts_avail.iat[0].tz_convert("America/New_York").strftime("%H:%M") == "17:00"
    assert d.high.iat[0] == m.high.max() and d.close.iat[0] == m.close.iat[-1]


def test_gaps_are_not_filled():
    m = full_session().drop(index=range(10, 13)).reset_index(drop=True)
    b5 = charts.build(m, "5m")
    assert b5.n_1m.iat[2] == 2 and len(b5) == 23 * 12


def test_higher_chart_only_visible_from_its_close():
    m = full_session()
    m15 = charts.build(m, "15m")
    h1 = charts.build(m, "1h")
    al = charts.align(m15, h1, ["close"], "1h")
    assert al["close_1h"].iloc[:3].isna().all()          # 18:00-18:45 bars: no 1h bar closed yet
    assert al["close_1h"].iat[3] == h1.close.iat[0]       # 18:45 bar closes 19:00 = 1h close
    seen = al.dropna(subset=["ts_avail_1h"])
    assert (seen["ts_avail_1h"] <= seen["ts_avail"]).all()


def test_atr_uses_only_prior_bars():
    m = full_session()
    a = atr_prior(m, 14)
    assert a.iloc[:14].isna().all() and not np.isnan(a.iat[14])
    bumped = m.copy()
    bumped.loc[100, "high"] += 50
    b = atr_prior(bumped, 14)
    assert a.iat[100] == b.iat[100] and b.iat[101] > a.iat[101]
    # matches a plain Wilder loop
    tr = true_range(m.high, m.low, m.close)
    w = tr[:14].mean()
    for i in range(14, 200):
        assert np.isclose(a.iat[i], w)
        w = (w * 13 + tr[i]) / 14


def test_roll_blackout_and_forced_exit():
    m = full_session()
    roll = m.ts_event.iat[600]
    rolls = pd.DataFrame({"roll_time_utc": [roll], "old_contract": ["A"], "new_contract": ["B"], "spread": [1.0]})
    f = add_roll_flags(m, rolls, 60)
    assert f.roll_no_entry.iloc[540:600].all() and not f.roll_no_entry.iat[539]
    assert not f.roll_no_entry.iat[600]
    assert f.index[f.roll_force_exit].tolist() == [599]
