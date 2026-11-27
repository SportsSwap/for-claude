import numpy as np
import pandas as pd
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from engine import backtest as B, metrics as M


def synth(n=600, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2010-01-01", periods=n)
    c = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
    o = c * np.exp(rng.normal(0, 0.004, n))
    return pd.Series(o, idx), pd.Series(c, idx)


def test_buy_and_hold_close_mode_matches_asset():
    o, c = synth()
    s = pd.Series(1.0, index=c.index)
    r = B.run(o, c, s, mode="close", cost_bps=0).returns
    asset = c.pct_change().loc[r.index].fillna(0)
    assert np.allclose(r.iloc[1:], asset.iloc[1:], atol=1e-12)


def test_open_mode_starts_at_next_open():
    o, c = synth()
    s = pd.Series(0.0, index=c.index); s.iloc[10:] = 1.0
    res = B.run(o, c, s, mode="open", cost_bps=0)
    d = c.index[11]
    # first day held: only the open->close piece of day 11
    assert abs(res.returns.loc[d] - (c.iloc[11] / o.iloc[11] - 1)) < 1e-12
    assert abs(res.returns.loc[c.index[10]]) < 1e-12


def test_no_lookahead_perfect_foresight_signal_is_impossible():
    # a signal built from TODAY's return must not earn TODAY's return
    o, c = synth()
    today_up = (c.pct_change() > 0).astype(float)
    r = B.run(o, c, today_up, mode="close", cost_bps=0).returns
    assert M.summary(r)["Sharpe"] < 2  # a look-ahead bug would give Sharpe > 10


def test_costs_charged_per_side():
    o, c = synth()
    s = pd.Series(0.0, index=c.index); s.iloc[100:200] = 1.0
    g = B.run(o, c, s, mode="close", cost_bps=0).returns
    n = B.run(o, c, s, mode="close", cost_bps=10).returns
    diff = (1 + g).prod() / (1 + n).prod()
    assert 1.0015 < diff < 1.0025  # two sides x 10 bps


def test_overnight_mode():
    o, c = synth()
    s = pd.Series(1.0, index=c.index)
    r = B.run(o, c, s, mode="overnight", cost_bps=0).returns
    gap = (o / c.shift(1) - 1).loc[r.index].fillna(0)
    assert np.allclose(r.iloc[1:], gap.iloc[1:])


def test_pbo_random_strategies_near_half():
    rng = np.random.default_rng(1)
    X = pd.DataFrame(rng.normal(0, 0.01, (2000, 20)))
    p = M.pbo(X, blocks=10)["PBO"]
    assert 0.25 < p < 0.75
