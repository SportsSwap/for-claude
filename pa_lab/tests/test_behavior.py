import numpy as np
import pytest

from lab import behavior as bh


def arr(*x):
    return np.array(x, float)


def test_touch_holds_breaks_and_unresolved():
    # support at 100, ATR 2: hold = high >= 102 first; break = close < 99.5 first
    h = arr(101, 100.5, 101, 102.5, 101)
    l = arr(100.2, 100, 99.8, 100, 100)
    c = arr(100.8, 100.2, 100.5, 102, 100.5)
    atr = np.full(5, 2.0)
    out = bh.score_touches(h, l, c, atr, np.array([1]), np.array([1]), arr(100), arr(100), 1.0, 0.25, 50)
    assert out[0] == 1
    c2 = c.copy(); c2[2] = 99.4
    assert bh.score_touches(h, l, c2, atr, np.array([1]), np.array([1]), arr(100), arr(100), 1.0, 0.25, 50)[0] == -1
    assert bh.score_touches(h, l, c, atr, np.array([1]), np.array([1]), arr(100), arr(100), 1.0, 0.25, 1)[0] == 0
    # same bar reaches the target intrabar and closes through: the high came first -> hold
    h3 = arr(101, 100.5, 102.5); l3 = arr(100.5, 100, 99); c3 = arr(100.8, 100.2, 99.0)
    assert bh.score_touches(h3, l3, c3, np.full(3, 2.0), np.array([1]), np.array([1]), arr(100), arr(100), 1.0, 0.25, 50)[0] == 1


def test_short_side_mirrors():
    h = 200 - arr(100.2, 100, 99.8, 100, 100)
    l = 200 - arr(101, 100.5, 101, 102.5, 101)
    c = 200 - arr(100.8, 100.2, 100.5, 102, 100.5)
    out = bh.score_touches(h, l, c, np.full(5, 2.0), np.array([1]), np.array([-1]), arr(100), arr(100), 1.0, 0.25, 50)
    assert out[0] == 1


def test_episodes_count_touches_and_sides():
    # band 100; price above, touches twice, closes through, touches from below
    c = arr(102, 100.5, 102, 100.4, 98, 97, 99.8, 97)
    h = c + 0.5
    l = c - 0.6
    t = np.arange(8, dtype=np.int64)
    ob, j, sd, nth = bh.episodes(h, l, c, t, np.array([1]), np.array([7]), arr(100), arr(100), arr(0), np.array([0]))
    assert j.tolist() == [1, 3, 6] and sd.tolist() == [1, 1, -1] and nth.tolist() == [1, 2, 3]


def test_bootstrap_interval_and_eras():
    g = np.random.default_rng(0)
    S = 200
    sess = np.repeat(np.arange(S), 20)
    A = bh.Group(g.binomial(1, 0.6, len(sess)).astype(float), sess, np.full(len(sess), "x", dtype=object))
    B = bh.Group(g.binomial(1, 0.5, len(sess)).astype(float), sess, np.full(len(sess), "x", dtype=object))
    era = np.where(np.arange(S) < 100, 1, 2)
    st = bh.diff_stats(A, B, bh.boot_weights(S, "t"), era)
    assert st["lo"] < st["point"] < st["hi"] and st["lo"] > 0
    assert st["era1"] > 0 and st["era2"] > 0


def test_verdict_rule():
    nq = dict(point=0.05, lo=0.01, hi=0.09, era1=0.04, era2=0.06)
    assert bh.verdict(nq, dict(point=0.02))[0] == "true"
    assert bh.verdict(nq, dict(point=-0.02))[0] == "split"
    assert bh.verdict(dict(nq, era2=-0.01), dict(point=0.02))[0] == "split"
    assert bh.verdict(dict(nq, lo=-0.01), dict(point=0.02))[0] == "false"
    assert bh.verdict(dict(nq, point=-0.05, lo=-0.09, hi=-0.01), dict(point=0.02))[0] == "false"


def test_difference_of_differences():
    S = 50
    sess = np.repeat(np.arange(S), 10)
    mk = lambda v: bh.Group(np.full(len(sess), v), sess, np.full(len(sess), "x", dtype=object))  # noqa: E731
    st = bh.diff_stats(mk(0.7), mk(0.6), bh.boot_weights(S, "d"), np.ones(S, int), mk(0.5), mk(0.45))
    assert np.isclose(st["point"], (0.7 - 0.6) - (0.5 - 0.45))
    assert np.isclose(st["lo"], st["point"]) and np.isclose(st["hi"], st["point"])
