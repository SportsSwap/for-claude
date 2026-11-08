"""No look-ahead: every detector and every setup's signals, run on data cut at
a random bar, equal the full run up to the cut."""
import itertools

import numpy as np
import pandas as pd
import pytest

from lab import detectors as det
from lab import dials, strategy
from lab.market import Market
from lab.seed import rng
from lab.sessions import session_date

N_CUTS = 3


@pytest.fixture(scope="module")
def full():
    import make_synthetic
    adj, _, rolls = make_synthetic.make_market("NQ", "2021-10-01", "2022-01-31", False)
    adj["session"] = session_date(adj["ts_event"])
    return Market.from_frames("NQ", adj, rolls)


@pytest.fixture(scope="module")
def cuts(full):
    g = rng("test:lookahead_cuts")
    pts = sorted(g.integers(full.n // 3, full.n - 1000, N_CUTS).tolist())
    return [(n, full.cut(n)) for n in pts]


def _eq(a, b):
    a, b = np.asarray(a), np.asarray(b)
    assert a.shape == b.shape, (a.shape, b.shape)
    if a.dtype.kind == "f":
        assert np.allclose(a, b, equal_nan=True)
    else:
        assert (a == b).all()


def _sel(obj, mask, fields):
    return {f: np.asarray(getattr(obj, f))[mask] for f in fields}


@pytest.mark.parametrize("chart", ["1m", "5m", "15m", "1h", "4h", "daily"])
def test_detectors(full, cuts, chart):
    for n_cut, cm in cuts:
        F, C = full.charts[chart], cm.charts[chart]
        N = len(C.c) - 1  # the last cut bar may be partial
        _eq(F.atr[:N], C.atr[:N])
        for k in (2, 3, 5, 8):
            sf, sc = det.swings(F.h, F.l, k), det.swings(C.h, C.l, k)
            fields = ["idx", "known", "price", "typ"]
            for f, c in zip(_sel(sf, sf.known < N, fields).values(), _sel(sc, sc.known < N, fields).values()):
                _eq(f, c)
            tf, tc = det.structure(F.c, sf), det.structure(C.c, sc)
            _eq(tf.trend[:N], tc.trend[:N]); _eq(tf.last_sh[:N], tc.last_sh[:N])
            ev = ["ev_idx", "ev_dir", "ev_kind", "ev_level"]
            for f, c in zip(_sel(tf, tf.ev_idx < N, ev).values(), _sel(tc, tc.ev_idx < N, ev).values()):
                _eq(f, c)
            for tol, touches, shape in [(0.1, 1, "line"), (0.25, 2, "box"), (0.5, 3, "line")]:
                lf, lc = det.levels(sf, F.atr, tol, touches, shape), det.levels(sc, C.atr, tol, touches, shape)
                fl = ["born", "price", "lo", "hi", "n_swings"]
                for f, c in zip(_sel(lf, lf.born < N, fl).values(), _sel(lc, lc.born < N, fl).values()):
                    _eq(f, c)
            for touches, tol in [(2, 0.25), (3, 0.5)]:
                a, b = det.trend_lines(sf, F.c, F.atr, touches, tol), det.trend_lines(sc, C.c, C.atr, touches, tol)
                fl = ["born", "x0", "y0", "slope", "side", "touches"]
                for f, c in zip(_sel(a, a.born < N, fl).values(), _sel(b, b.born < N, fl).values()):
                    _eq(f, c)
        for run, span in [(2, 1.5), (3, 2.0), (5, 3.0)]:
            a, b = det.zones(F.o, F.h, F.l, F.c, F.atr, run, span), det.zones(C.o, C.h, C.l, C.c, C.atr, run, span)
            fl = ["born", "lo", "hi", "side"]
            for f, c in zip(_sel(a, a.born < N, fl).values(), _sel(b, b.born < N, fl).values()):
                _eq(f, c)
        for g in (0.0, 0.25):
            a, b = det.fair_value_gaps(F.h, F.l, F.atr, g), det.fair_value_gaps(C.h, C.l, C.atr, g)
            fl = ["born", "lo", "hi", "side", "mid_lo", "mid_hi"]
            for f, c in zip(_sel(a, a.born < N, fl).values(), _sel(b, b.born < N, fl).values()):
                _eq(f, c)


BASE = dict(swing_strength=3, direction="both", entry="close", stop_mode="hard", stop_ref="beyond_level",
            stop_buffer_atr=0.1, target="2R", management="hold", time_exit="bars_96", trend_filter="setup_chart",
            skip_choppy="on", skip_run="3d", fresh_breakouts_only="off", news="trade", session="all",
            pullback_depth="any", gap_confluence="off", level_tol_atr=0.25, level_min_touches=2, level_shape="box",
            retest_window_bars=12, sweep_depth_max_atr=0.5, reclaim_bars=2, trendline_min_touches=2,
            trendline_tol_atr=0.25, trendline_event="bounce", zone_run_candles=2, zone_span_atr=1.5,
            zone_fresh_only="no", fvg_min_gap_atr=0.0, fvg_max_age_bars=24)
PAIRS = [("5m", "5m"), ("15m", "5m"), ("1h", "15m")]
CONFS = list(strategy.CONF)
EXTRA = {"trend_line": [{"trendline_event": "break"}], "fair_value_gap": [{"stop_ref": "gap_middle"}]}


def _versions():
    for setup in dials.SETUPS:
        for (sc, tc), conf, entry in itertools.product(PAIRS, CONFS, ["close", "limit_at_level"]):
            for extra in [{}] + EXTRA.get(setup, []):
                yield dict(BASE, setup=setup, setup_chart=sc, trigger_chart=tc, confirmation=conf, entry=entry, **extra)


@pytest.mark.parametrize("setup", list(dials.SETUPS))
def test_setup_signals(full, cuts, setup):
    strategy.clear_cache()
    seen = 0
    for v in (x for x in _versions() if x["setup"] == setup):
        cf = strategy.candidates(full, setup, v["setup_chart"], v["trigger_chart"], v)
        of, _ = strategy.orders(full, v)
        for n_cut, cm in cuts:
            cc = strategy.candidates(cm, setup, v["setup_chart"], v["trigger_chart"], v)
            mf, mc = cf.t < n_cut - 1, cc.t < n_cut - 1
            for f in ("t", "side", "level", "far", "wick", "gapmid", "fresh", "tj", "sbar", "resting"):
                _eq(getattr(cf, f)[mf], getattr(cc, f)[mc])
            oc, _ = strategy.orders(cm, v)
            if of is None:
                assert oc is None or not (oc["t"] < n_cut - 1).any()
                continue
            a, b = of["t"] < n_cut - 1, (oc["t"] < n_cut - 1) if oc is not None else None
            for f in ("t", "side", "limit", "px", "stop", "target", "size", "close_stop", "use_struct"):
                _eq(of[f][a], oc[f][b] if oc is not None else np.zeros(0))
            seen += int(a.sum())
    assert seen > 0, f"{setup} produced no signals to compare"
