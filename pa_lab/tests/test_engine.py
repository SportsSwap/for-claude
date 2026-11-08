"""Engine checks on made-up price paths, for longs and mirrored shorts."""
import numpy as np
import pandas as pd
import pytest

from lab import engine
from lab.market import Market
from lab.sessions import session_date

T = 0.25
MIRROR = 2000.0


def make(rows, roll_at=None, start="2022-01-04 14:30"):
    """rows: (open, high, low, close) per minute from 09:30 ET on 2022-01-04."""
    ts = pd.date_range(start, periods=len(rows), freq="1min", tz="UTC")
    a = np.array(rows, float)
    df = pd.DataFrame({"ts_event": ts, "open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3],
                       "volume": 1, "contract": "X"})
    df["session"] = session_date(df["ts_event"])
    rolls = pd.DataFrame(columns=["roll_time_utc", "old_contract", "new_contract", "spread"])
    if roll_at is not None:
        rolls = pd.DataFrame({"roll_time_utc": [ts[roll_at]], "old_contract": ["A"], "new_contract": ["B"], "spread": [0.0]})
    return Market.from_frames("NQ", df, rolls)


def mirror_rows(rows):
    return [(MIRROR - o, MIRROR - l, MIRROR - h, MIRROR - c) for o, h, l, c in rows]


def mp(x):
    return np.nan if x is None or (isinstance(x, float) and np.isnan(x)) else MIRROR - x


def both(rows, order, **kw):
    """Run the order long on rows and short on mirrored rows; return both trade frames."""
    long_o = {k: np.atleast_1d(v) for k, v in order.items()}
    short_o = dict(long_o)
    short_o["side"] = -long_o["side"]
    for k in ("stop", "target", "px"):
        if k in long_o:
            short_o[k] = np.array([mp(x) for x in long_o[k]], float)
    a = engine.run(make(rows, **kw), long_o)
    b = engine.run(make(mirror_rows(rows), **kw), short_o)
    return a, b


def check_mirror(a, b):
    assert len(a) == len(b)
    assert np.allclose(a.dollars, b.dollars)
    assert a.reason.tolist() == b.reason.tolist()


FLAT = (100, 100.5, 99.5, 100)


def test_target_needs_a_tick_through():
    rows = [FLAT, (100, 104, 99.75, 103), (103, 104.25, 102, 103)]
    a, b = both(rows, dict(t=0, side=1, stop=95.0, target=104.0))
    check_mirror(a, b)
    assert a.exit_idx.iat[0] == 2 and a.exit_px.iat[0] == 104.0 and a.reason.iat[0] == "target"
    assert a.entry_px.iat[0] == 100 + T                    # market entry slips one tick
    assert np.isclose(a.dollars.iat[0], (104 - 100.25) * 20 - 4)


def test_target_never_better_on_a_gap():
    rows = [FLAT, (110, 111, 109, 110)]
    a, b = both(rows, dict(t=0, side=1, stop=95.0, target=104.0))
    check_mirror(a, b)
    assert a.exit_px.iat[0] == 104.0


def test_hard_stop_slips_a_tick_and_gaps_from_the_open():
    rows = [FLAT, (100, 100.5, 98, 99)]
    a, b = both(rows, dict(t=0, side=1, stop=98.0, target=110.0))
    check_mirror(a, b)
    assert a.exit_px.iat[0] == 98 - T and a.reason.iat[0] == "stop"
    rows = [FLAT, (96, 97, 95, 96)]
    a, b = both(rows, dict(t=0, side=1, stop=98.0, target=110.0))
    check_mirror(a, b)
    assert a.exit_px.iat[0] == 96 - T


def test_stop_first_when_both_in_one_bar():
    rows = [FLAT, (100, 110, 90, 100)]
    a, b = both(rows, dict(t=0, side=1, stop=98.0, target=104.0))
    check_mirror(a, b)
    assert a.reason.iat[0] == "stop"


def test_limit_needs_a_tick_through_and_never_fills_better():
    rows = [FLAT, (100, 100.5, 99, 100), (100, 100.5, 98.75, 100), (100, 103, 99.5, 102)]
    a, b = both(rows, dict(t=0, side=1, limit=True, px=99.0, lim_end=10, stop=95.0, target=102.0))
    check_mirror(a, b)
    assert a.entry_idx.iat[0] == 2 and a.entry_px.iat[0] == 99.0        # bar 1 only touched 99
    rows = [FLAT, (97, 98, 96.5, 97.5), (98, 101, 97, 100.5)]
    a, b = both(rows, dict(t=0, side=1, limit=True, px=99.0, lim_end=10, stop=95.0, target=100.0))
    check_mirror(a, b)
    assert a.entry_px.iat[0] == 99.0                                     # gap down: still 99, not 97


def test_limit_window_expires_and_cancels_on_stop():
    rows = [FLAT] * 3 + [(100, 100.5, 98, 99)]
    a, b = both(rows, dict(t=0, side=1, limit=True, px=98.5, lim_end=2, stop=95.0, target=110.0))
    assert len(a) == 0 and len(b) == 0                                   # window over before the dip
    rows = [FLAT, (100, 100.5, 96, 97), (97, 99, 90, 92)]
    a, b = both(rows, dict(t=0, side=1, limit=True, px=95.0, lim_end=10, stop=96.0, target=110.0))
    assert len(a) == 0 and len(b) == 0                                   # stop traded before the fill


def test_close_based_stop_waits_for_a_close():
    rows = [FLAT, (100, 100.5, 97, 99), (99, 99.5, 97.5, 97.75), FLAT]
    order = dict(t=0, side=1, stop=98.0, target=110.0, close_stop=True)
    a, b = both(rows, order)
    check_mirror(a, b)
    assert a.exit_idx.iat[0] == 2 and a.exit_px.iat[0] == 97.75 - T and a.reason.iat[0] == "close_stop"


def test_time_exit_at_close_without_slippage():
    rows = [FLAT, FLAT, (100, 101, 99.5, 100.75), FLAT]
    a, b = both(rows, dict(t=0, side=1, stop=95.0, target=110.0, time_exit=2))
    check_mirror(a, b)
    assert a.exit_idx.iat[0] == 2 and a.exit_px.iat[0] == 100.75 and a.reason.iat[0] == "time"


def test_roll_blackout_and_roll_exit():
    rows = [FLAT] * 120
    a, b = both(rows, dict(t=np.array([10, 70]), side=np.array([1, 1]), stop=np.array([90.0, 90.0]),
                           target=np.array([np.nan, np.nan])), roll_at=100)
    check_mirror(a, b)
    assert len(a) == 1 and a.decided.iat[0] == 10                         # t=70 is inside the hour before the roll
    assert a.exit_idx.iat[0] == 99 and a.reason.iat[0] == "roll" and a.exit_px.iat[0] == 100.0


def test_one_position_at_a_time():
    rows = [FLAT] * 10 + [(100, 106, 99.5, 105)] + [FLAT] * 5
    a, b = both(rows, dict(t=np.array([0, 3, 12]), side=np.array([1, 1, 1]),
                           stop=np.array([95.0, 95.0, 95.0]), target=np.array([105.0, 105.0, np.nan])))
    check_mirror(a, b)
    assert a.decided.tolist() == [0, 12]


def test_half_size_halves_everything():
    rows = [FLAT, (100, 104.5, 99.75, 104)]
    full, _ = both(rows, dict(t=0, side=1, stop=95.0, target=104.0))
    half, hb = both(rows, dict(t=0, side=1, stop=95.0, target=104.0, size=0.5))
    check_mirror(half, hb)
    assert np.isclose(half.dollars.iat[0], full.dollars.iat[0] / 2)
    assert np.isclose(half.R.iat[0], full.R.iat[0])


def test_structure_exit_slips():
    rows = [FLAT, FLAT, (100, 100.5, 99.5, 100.5), FLAT]
    mk = make(rows)
    tr = engine.run(mk, dict(t=np.array([0]), side=np.array([1]), stop=np.array([95.0]),
                             target=np.array([np.nan]), use_struct=np.array([True])),
                    struct_up=np.zeros(0, np.int64), struct_dn=np.array([2]))
    assert tr.reason.iat[0] == "structure" and tr.exit_px.iat[0] == 100.5 - T


def test_daily_pnl_and_sharpe():
    mk = make([FLAT, (100, 104.5, 99.75, 104)])
    tr = engine.run(mk, dict(t=np.array([0]), side=np.array([1]), stop=np.array([95.0]), target=np.array([104.0])))
    d = engine.daily_pnl(mk, tr)
    assert len(d) == 1 and np.isclose(d.iat[0], tr.dollars.sum())
    assert engine.sharpe(pd.Series([1.0, -1.0, 1.0, -1.0])) == 0.0
    assert np.isclose(engine.sharpe(pd.Series([1.0, 2.0, 3.0])), 2.0 / 1.0 * np.sqrt(252))


def test_timestamps_are_nanoseconds():
    mk = make([FLAT, FLAT])
    assert mk.ts_ns[1] - mk.ts_ns[0] == 60_000_000_000
    ch = mk.charts["5m"]
    assert ch.avail_ns[0] - ch.open_ns[0] == 5 * 60_000_000_000


def test_independent_orders_ignore_one_position():
    rows = [FLAT] * 10 + [(100, 106, 99.5, 105)] + [FLAT] * 5
    o = dict(t=np.array([0, 3]), side=np.array([1, 1]), stop=np.array([95.0, 95.0]), target=np.array([105.0, 105.0]))
    assert len(engine.run(make(rows), o)) == 1
    assert len(engine.run(make(rows), o, independent=True)) == 2
