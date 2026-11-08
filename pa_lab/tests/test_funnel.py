"""Prompt 3 funnel: set generation, greedy spread fill, stages, twins, hashing."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lab import dials, engine
from lab import funnel as fn
from lab.market import Market
from lab.seed import rng
from lab.sessions import session_date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def test_targets_are_shares_per_dial():
    sp = fn.Space.build("flip_zone")
    for d in sp.dials:
        idx = [i for i, (dd, _) in enumerate(sp.slots) if dd == d]
        assert np.isclose(sp.target[idx].sum(), 1.0), d
    # an excluded value has a lower target than uniform: gap_middle never appears outside FVG
    gm = sp.slots.index(("stop_ref", "gap_middle"))
    assert sp.target[gm] == 0.0


def test_random_draws_are_valid():
    for s in fn.SETUPS:
        sp = fn.Space.build(s)
        for row in sp.draw(rng("test:draw"), 50):
            assert dials.is_valid(fn.SPEC, sp.to_version(row))


def test_greedy_fill_hits_target_shares():
    sp = fn.Space.build("level_bounce")
    pool = sp.draw(rng("test:pool"), 6000)
    pick = fn.greedy_fill(sp, pool, 500, rng("test:greedy"), batch=400)
    assert len(set(pick.tolist())) == 500
    got = sp.shares(pool[pick])
    rand = sp.shares(pool[:500])
    err_g = np.abs(got - sp.target).max()
    err_r = np.abs(rand - sp.target).max()
    assert err_g < 0.02 and err_g < err_r


def test_sampled_mix_and_no_duplicates():
    sp = fn.Space.build("breakout")
    vs = fn.sampled_versions(sp, 200, rng("test:sampled"), set())
    keys = [fn.key_of(v) for v in vs]
    assert len(set(keys)) == 200
    nf = [sum(v[f] != off for f, off in fn.FILTER_OFF.items()) for v in vs]
    assert nf.count(0) == 80 and nf.count(1) == 80 and nf.count(2) == 40
    assert all(dials.is_valid(fn.SPEC, v) for v in vs)


def test_one_touch_box_and_line_are_one_version():
    sp = fn.Space.build("level_bounce")
    v = sp.to_version(sp.draw(rng("test:dup"), 1)[0])
    v["level_min_touches"] = 1
    a, b = dict(v, level_shape="line"), dict(v, level_shape="box")
    assert fn.key_of(a) == fn.key_of(b)
    assert fn.key_of(dict(a, level_min_touches=2)) != fn.key_of(dict(b, level_min_touches=2))


def test_common_and_named_sets():
    cm = fn.common_versions()
    keys = {fn.key_of(v) for v in cm}
    assert len(keys) == len(cm) > 10000
    for v in cm:
        assert v["swing_strength"] == 3 and v["direction"] == "both" and v["time_exit"] == "bars_96"
        assert v["trigger_chart"] == (v["setup_chart"] if v["setup_chart"] != "daily" else "1h")
        assert sum(v[f] != off for f, off in fn.FILTER_OFF.items()) <= 1
    assert len(fn.NAMED) == 6
    for _, v in fn.NAMED.values():
        assert dials.is_valid(fn.SPEC, v)


def test_stage_logic():
    nq = pd.DataFrame({"id": list("abcdef"), "trades": [10, 50, 50, 50, 50, 50],
                       "net": [100, -1, 100, 100, 100, 100], "sharpe": [1, 1, 0.4, 0.9, 0.9, 0.9],
                       "net_era1": [1] * 6, "net_era2": [1, 1, 1, 1, 1, -1]})
    es = pd.DataFrame({"id": list("abcdef"), "net": [1, 1, 1, 1, 1, 1], "sharpe": [1, 1, 1, 1, 0.2, 1],
                       "trades": [1] * 6})
    tw = pd.DataFrame({"id": ["d", "e", "f"], "twin_p": [0.01, 0.01, 0.01]})
    df = fn.apply_stages(nq, es, tw).set_index("id")
    assert df.s1.tolist() == [False, True, True, True, True, True]
    assert df.s2.tolist() == [False, False, True, True, True, True]
    assert df.s3.tolist() == [False, False, False, True, True, True]
    assert df.s4.tolist() == [False, False, False, True, True, True]
    assert df.candidate.tolist() == [False, False, False, True, False, False]   # e fails ES, f fails era 2


@pytest.fixture(scope="module")
def tiny():
    import make_synthetic
    adj, _, rolls = make_synthetic.make_market("NQ", "2021-10-01", "2021-12-31", False)
    adj["session"] = session_date(adj["ts_event"])
    return Market.from_frames("NQ", adj, rolls)


def _trades(mk, peek, stream="test:twin_orders"):
    g = rng(stream)
    ch = mk.charts["5m"]
    t = np.sort(g.choice(np.arange(5000, mk.n - 500), 150, replace=False))
    i5 = np.searchsorted(ch.avail_ns, mk.ts_ns[t] + 60_000_000_000, side="right") - 1
    a = ch.atr[i5]
    side = np.where(mk.c[t + 60] > mk.c[t], 1, -1) if peek else g.choice([-1, 1], len(t))
    px = mk.c[t]
    return engine.run(mk, dict(t=t, side=side, stop=px - side * a, target=px + side * 2 * a,
                               time_exit=t + 120), independent=True)


def test_twins_detect_a_planted_edge_and_not_noise(tiny):
    v = {"setup_chart": "5m"}
    edge = fn.twin_test(tiny, v, _trades(tiny, True), 2000, 40, "test:twins:edge")
    assert edge["p"] < 0.05
    # random directions: p-values spread out; one lucky draw is allowed, a pattern is not
    ps = [fn.twin_test(tiny, v, _trades(tiny, False, f"test:noise:{i}"), 2000, 40, f"test:twins:noise:{i}")["p"]
          for i in range(8)]
    assert sum(p < 0.05 for p in ps) <= 1 and np.median(ps) > 0.2


def test_run_refuses_changed_versions(tmp_path, monkeypatch):
    import run_funnel
    monkeypatch.setenv("LAB_ROOT", str(tmp_path))
    d = run_funnel.out_dir()
    body = b'{"id": "x"}\n'
    (d / "versions.jsonl").write_bytes(body)
    (d / "versions.sha256").write_text(fn.sha256_bytes(body) + "  versions.jsonl\n")
    st = json.dumps(fn.STAGES).encode()
    (d / "stages.json").write_bytes(st)
    (d / "stages.sha256").write_text(fn.sha256_bytes(st) + "\n")
    assert run_funnel.load_versions()[0]["id"] == "x"
    (d / "versions.jsonl").write_bytes(body + b'{"id": "y"}\n')
    with pytest.raises(SystemExit, match="changed"):
        run_funnel.load_versions()
