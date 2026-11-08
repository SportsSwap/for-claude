"""Prompt 3: the funnel.

Version sets (spread, named, common, sampled) -> every version run on NQ and
ES discovery -> five stages on NQ -> final-test candidates, plus a judgment
of each setup as a whole. Every threshold is fixed in stages.json and every
configuration in versions.jsonl, both hashed before the first P&L is computed.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import dials, engine
from . import strategy as sg
from .seed import rng

SPEC = dials.build_spec()
SETUPS = list(SPEC["setups"])
PAIRS = [tuple(p) for p in SPEC["chart_pairs"]]

FILTER_OFF = {"trend_filter": "off", "skip_choppy": "off", "skip_run": "off", "fresh_breakouts_only": "off",
              "news": "trade", "session": "all", "pullback_depth": "any", "gap_confluence": "off"}

STAGES = {
    "min_signals_to_grade": 40,
    "stage1_min_trades": 30,
    "stage2_min_net_dollars_exclusive": 0.0,
    "stage3_min_sharpe": 0.5,
    "stage4_twin_sets": 10000,
    "stage4_twins_per_trade": 100,
    "stage4_max_twin_sims_per_version": 200000,
    "stage4_min_twins_per_trade": 20,
    "stage4_max_share_of_sets_as_good": 0.05,
    "stage5_es_min_net_dollars_exclusive": 0.0,
    "stage5_es_min_sharpe": 0.3,
    "candidate_rule": "stages 1-4 on NQ, net > 0 in era 1 (2022) and era 2 (2023-01-01..2024-07-31) on NQ, and stage 5 on ES",
    "setup_works_rule": "equal-weight average daily P&L of all graded versions of a setup on one chart and market: "
                        "net > 0 in every calendar year, Sharpe >= 0.5, net > 0 in era 1 and in era 2",
    "setup_min_sharpe": 0.5,
    "sharpe": "mean / std of daily P&L over every tradable discovery session (zero days included) x sqrt(252)",
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical(v: dict) -> str:
    return json.dumps({k: v[k] for k in sorted(v)}, sort_keys=True, default=str)


def dial_keys(setup: str) -> list[str]:
    return dials.setup_dials(SPEC, setup)


def config_of(v: dict) -> dict:
    """Only the dials (no id/set/name)."""
    keys = ["setup", "setup_chart", "trigger_chart"] + dial_keys(v["setup"])
    return {k: v[k] for k in keys}


LEVEL_SETUPS = {"level_bounce", "breakout", "flip_zone", "sweep_reclaim"}


def key_of(v: dict) -> str:
    """Identity for the no-duplicates rule. A one-swing level has lo == hi, so for
    level setups with level_min_touches == 1 the box and the line are the same version."""
    c = config_of(v)
    if c["setup"] in LEVEL_SETUPS and c.get("level_min_touches") == 1:
        c["level_shape"] = "line"
    return canonical(c)


# =========================================================================== random draws and targets
@dataclass
class Space:
    """Valid values of every dial in every chart pair of one setup, as slot indices."""
    setup: str
    dials: list            # dial names, plus "pair" first
    slots: list            # (dial, value) per slot
    table: dict            # dial -> int array [pair, k] of slot ids (-1 pad)
    lens: dict             # dial -> int array [pair] number of valid values
    target: np.ndarray     # target share per slot

    @staticmethod
    def build(setup: str) -> "Space":
        ds = dial_keys(setup)
        slots = [("pair", p) for p in range(len(PAIRS))]
        table, lens = {}, {}
        table["pair"] = np.arange(len(PAIRS)).reshape(1, -1)
        for d in ds:
            allv = [x["value"] for x in SPEC["dials"][d]["values"]]
            base = len(slots)
            slots += [(d, x) for x in allv]
            rows, ln = [], []
            for sc, tc in PAIRS:
                vv = dials.valid_values(SPEC, {"setup": setup, "setup_chart": sc, "trigger_chart": tc}, d)
                rows.append([base + allv.index(x) for x in vv])
                ln.append(len(vv))
            w = max(ln)
            table[d] = np.array([r + [-1] * (w - len(r)) for r in rows])
            lens[d] = np.array(ln)
        # target share = what uniform random draws give: pair uniform, each dial uniform over its valid values
        target = np.zeros(len(slots))
        target[: len(PAIRS)] = 1.0 / len(PAIRS)
        for d in ds:
            for p in range(len(PAIRS)):
                for s in table[d][p][: lens[d][p]]:
                    target[s] += 1.0 / lens[d][p] / len(PAIRS)
        return Space(setup, ["pair"] + ds, slots, table, lens, target)

    def draw(self, g: np.random.Generator, n: int) -> np.ndarray:
        """n uniform random valid draws as slot-id matrix [n, n_dials]."""
        p = g.integers(0, len(PAIRS), n)
        out = np.empty((n, len(self.dials)), np.int64)
        out[:, 0] = p
        for j, d in enumerate(self.dials[1:], 1):
            k = (g.random(n) * self.lens[d][p]).astype(np.int64)
            out[:, j] = self.table[d][p, k]
        return out

    def to_version(self, row) -> dict:
        sc, tc = PAIRS[int(row[0])]
        v = {"setup": self.setup, "setup_chart": sc, "trigger_chart": tc}
        for j, d in enumerate(self.dials[1:], 1):
            v[d] = self.slots[int(row[j])][1]
        return v

    def rows_of(self, versions) -> np.ndarray:
        idx = {s: i for i, s in enumerate(self.slots)}
        out = np.empty((len(versions), len(self.dials)), np.int64)
        for i, v in enumerate(versions):
            out[i, 0] = PAIRS.index((v["setup_chart"], v["trigger_chart"]))
            for j, d in enumerate(self.dials[1:], 1):
                out[i, j] = idx[(d, v[d])]
        return out

    def shares(self, rows: np.ndarray) -> np.ndarray:
        c = np.bincount(rows.ravel(), minlength=len(self.slots)).astype(float)
        c[: len(PAIRS)] = np.bincount(rows[:, 0], minlength=len(PAIRS))
        return c / max(len(rows), 1)


def greedy_fill(space: Space, pool: np.ndarray, n: int, g: np.random.Generator, batch: int = 400) -> np.ndarray:
    """Add versions one at a time: draw `batch` unused candidates from the pool and
    add the one that brings the dial shares closest to target (sum of squared gaps)."""
    S = len(space.slots)
    counts = np.zeros(S)
    chosen = []
    unused = np.ones(len(pool), bool)
    n = min(n, len(pool))
    onehot_cols = pool.copy()
    for step in range(n):
        free = np.flatnonzero(unused)
        cand = free if len(free) <= batch else g.choice(free, batch, replace=False)
        m = step + 1
        new = np.repeat(counts[None, :], len(cand), axis=0)
        r = np.arange(len(cand))[:, None]
        np.add.at(new, (r, onehot_cols[cand]), 1.0)
        # pair slots also live in column 0 and are counted once
        dist = ((new / m - space.target) ** 2).sum(axis=1)
        best = cand[int(np.argmin(dist))]
        chosen.append(best)
        unused[best] = False
        counts[onehot_cols[best]] += 1.0
    return np.array(chosen, np.int64)


# =========================================================================== the four sets
FILTERS = list(FILTER_OFF)


def filter_choices(setup, sc, tc):
    ctx = {"setup": setup, "setup_chart": sc, "trigger_chart": tc}
    out = {}
    for f, off in FILTER_OFF.items():
        vals = [x for x in dials.valid_values(SPEC, ctx, f) if x != off]
        if vals:
            out[f] = vals
    return out


def sampled_versions(space: Space, n: int, g: np.random.Generator, exclude: set) -> list[dict]:
    """As people trade them: 40% no filter, 40% one, 20% two; other dials random; no duplicates."""
    out, seen = [], set(exclude)
    n0, n1 = int(round(0.4 * n)), int(round(0.4 * n))
    plan = [0] * n0 + [1] * n1 + [2] * (n - n0 - n1)
    tries = 0
    for nf in plan:
        while True:
            tries += 1
            if tries > 200 * n:
                raise RuntimeError("could not draw enough distinct sampled versions")
            v = space.to_version(space.draw(g, 1)[0])
            v.update(FILTER_OFF)
            ch = filter_choices(v["setup"], v["setup_chart"], v["trigger_chart"])
            if len(ch) < nf:
                continue
            for f in g.choice(sorted(ch), nf, replace=False) if nf else []:
                v[f] = ch[f][int(g.integers(len(ch[f])))]
            k = key_of(v)
            if k in seen or not dials.is_valid(SPEC, v):
                continue
            seen.add(k)
            out.append(v)
            break
    return out


BREAK_SETUPS = {"breakout", "bos_continuation", "choch_reversal", "sweep_reclaim"}
USUAL = dict(swing_strength=3, direction="both", stop_mode="hard", stop_buffer_atr=0.1, management="hold",
             time_exit="bars_96", **FILTER_OFF,
             level_tol_atr=0.25, level_min_touches=2, level_shape="line", retest_window_bars=12,
             sweep_depth_max_atr=0.5, reclaim_bars=2, trendline_min_touches=3, trendline_tol_atr=0.25,
             trendline_event="bounce", zone_run_candles=3, zone_span_atr=2.0, zone_fresh_only="yes",
             fvg_min_gap_atr=0.1, fvg_max_age_bars=24)
VARIANTS = {
    "level_bounce": [dict(level_min_touches=t, level_shape=s) for t in (2, 3) for s in ("line", "box")],
    "breakout": [dict(level_min_touches=t, level_shape=s) for t in (2, 3) for s in ("line", "box")],
    "flip_zone": [dict(level_min_touches=t, retest_window_bars=w) for t in (2, 3) for w in (12, 24)],
    "trend_pullback": [{}],
    "trend_line": [dict(trendline_event=e, trendline_min_touches=t) for e in ("bounce", "break") for t in (2, 3)],
    "bos_continuation": [{}],
    "choch_reversal": [{}],
    "sweep_reclaim": [dict(sweep_depth_max_atr=d, reclaim_bars=r) for d in (0.25, 0.5) for r in (1, 2)],
    "supply_demand_zone": [dict(zone_run_candles=r, zone_fresh_only=f) for r in (2, 3) for f in ("yes", "no")],
    "fair_value_gap": [dict(fvg_min_gap_atr=m, fvg_max_age_bars=a) for m in (0.1, 0.25) for a in (24, 96)],
}
TOUCH_ENTRIES = [("limit_at_level", "none"), ("close", "close_back"), ("close", "either_candle")]
BREAK_ENTRIES = [("close", "none"), ("limit_at_level", "none")]
COMMON_FILTERS = [{}, {"trend_filter": "setup_chart"}, {"session": "ny"}, {"news": "skip"}]


def twins_per_trade(n_trades: int, st: dict = STAGES) -> int:
    """100 twins per trade, fewer for very active versions so a version costs at most
    `stage4_max_twin_sims_per_version` simulations (never fewer than the minimum)."""
    cap = st["stage4_max_twin_sims_per_version"] // max(n_trades, 1)
    return int(max(st["stage4_min_twins_per_trade"], min(st["stage4_twins_per_trade"], cap)))


def common_cell(v: dict) -> tuple:
    """A cell of the common grid: everything but stop, target and the one filter."""
    return (v["setup"], v["setup_chart"], v["entry"], v["confirmation"]) + tuple(
        str(v[k]) for k in sg._setup_keys(v["setup"]))


def common_versions() -> list[dict]:
    out = []
    for setup in SETUPS:
        keys = dial_keys(setup)
        for sc in dials.CHARTS:
            tc = "1h" if sc == "daily" else sc
            for var in VARIANTS[setup]:
                is_break = setup in BREAK_SETUPS or var.get("trendline_event") == "break"
                for (entry, conf), stop, tgt, flt in itertools.product(
                        BREAK_ENTRIES if is_break else TOUCH_ENTRIES, ("beyond_level", "last_swing"),
                        ("1R", "2R", "3R", "next_swing"), COMMON_FILTERS):
                    v = {"setup": setup, "setup_chart": sc, "trigger_chart": tc, **USUAL, **var,
                         "entry": entry, "confirmation": conf, "stop_ref": stop, "target": tgt, **flt}
                    v = {k: v[k] for k in ["setup", "setup_chart", "trigger_chart"] + keys}
                    assert dials.is_valid(SPEC, v), v
                    out.append(v)
    return out


def _named(setup, sc, tc, **kw):
    v = {"setup": setup, "setup_chart": sc, "trigger_chart": tc, **USUAL, **kw}
    v = {k: v[k] for k in ["setup", "setup_chart", "trigger_chart"] + dial_keys(setup)}
    assert dials.is_valid(SPEC, v), v
    return v


NAMED = {
    "Bare Minimum": ("Support and resistance only: a 2-touch level on 15m, a resting limit at the level, "
                     "stop just beyond it, 2R target, no confirmation and no filters.",
                     _named("level_bounce", "15m", "15m", entry="limit_at_level", confirmation="none",
                            stop_ref="beyond_level", target="2R")),
    "Daily Version": ("Daily levels traded from the 1h chart: a close back on 1h, stop beyond the level with "
                      "0.25 ATR room, target the next swing, daily trend must agree.",
                      _named("level_bounce", "daily", "1h", entry="close", confirmation="close_back",
                             stop_ref="beyond_level", stop_buffer_atr=0.25, target="next_swing",
                             trend_filter="setup_chart")),
    "Checklist": ("Trend pullback on 1h with a 15m trigger and every box ticked: 4h trend agrees, an engulfing or "
                  "rejection candle, New York hours only, no news days, stop beyond the last swing, 2R.",
                  _named("trend_pullback", "1h", "15m", entry="close", confirmation="either_candle",
                         stop_ref="last_swing", target="2R", trend_filter="one_up", session="ny", news="skip")),
    "Sweep System": ("Liquidity sweep on 15m, lower-chart break of structure on 1m as the trigger (5m trigger, 1m BOS), "
                     "stop beyond the sweep wick, target the next swing, New York open only, no news days.",
                     _named("sweep_reclaim", "15m", "5m", entry="close", confirmation="ltf_bos",
                            stop_ref="touch_wick", target="next_swing", session="ny_open", news="skip")),
    "Zone System": ("Fresh supply and demand zones on 1h: a resting limit at the zone edge, stop beyond the zone, "
                    "3R target, 4h trend agrees.",
                    _named("supply_demand_zone", "1h", "1h", entry="limit_at_level", confirmation="none",
                           stop_ref="beyond_level", target="3R", trend_filter="one_up")),
    "Entry Model": ("Fair value gap entry on 5m triggered on 1m: a resting limit at the gap edge, stop beyond the "
                    "gap's middle candle, 2R, New York open only, 15m trend agrees.",
                    _named("fair_value_gap", "5m", "1m", entry="limit_at_level", confirmation="none",
                           stop_ref="gap_middle", stop_buffer_atr=0.0, target="2R", session="ny_open",
                           trend_filter="one_up")),
}


# =========================================================================== metrics
def version_metrics(mk, tr: pd.DataFrame) -> tuple[dict, pd.Series]:
    d = engine.daily_pnl(mk, tr)
    era = mk.era[mk.tradable]
    years = pd.Index(d.index).map(lambda x: x.year).to_numpy()
    out = engine.metrics(mk, tr, d)
    for e in (1, 2):
        de = d[era == e]
        out[f"net_era{e}"] = float(de.sum())
        out[f"sharpe_era{e}"] = engine.sharpe(de)
    for y in sorted(set(years)):
        out[f"net_{y}"] = float(d[years == y].sum())
    return out, d


# =========================================================================== matched random twins
def twin_test(mk, v: dict, tr: pd.DataFrame, n_sets: int, per_trade: int, stream: str) -> dict:
    """Each real trade gets twins: same direction, a random entry minute in the same
    30 minutes of the day (tradable discovery sessions, outside roll blackouts), the
    same stop and target distances in setup-chart ATR, the same holding-time cap and
    the same costs. `per_trade` twins are simulated per trade; each of the `n_sets`
    sets picks one of them per trade at random. p = share of sets making >= the real net."""
    if not len(tr):
        return {"p": 1.0, "real_net": 0.0, "twin_mean": np.nan}
    g = rng(stream)
    S = mk.charts[v["setup_chart"]]
    ent = tr["entry_idx"].to_numpy()
    side = tr["side"].to_numpy()
    def atr_at(t):
        i = np.searchsorted(S.avail_ns, mk.ts_ns[t] + 60_000_000_000, side="right") - 1
        a = S.atr[np.maximum(i, 0)]
        return np.where((i >= 0) & np.isfinite(a) & (a > 0), a, np.nan)
    a0 = atr_at(ent)
    stop_atr = np.abs(tr["entry_px"].to_numpy() - tr["stop"].to_numpy()) / a0
    tgt = tr["target"].to_numpy()
    tgt_atr = np.abs(tgt - tr["entry_px"].to_numpy()) / a0
    hold = np.maximum(tr["exit_idx"].to_numpy() - ent, 1)
    size = tr["size"].to_numpy()
    limit_entry = ~np.isclose(tr["entry_px"].to_numpy() - side * mk.tick, mk.c[ent]) if "entry_px" in tr else np.zeros(len(tr), bool)
    bucket = mk.et_min // 30
    ok = mk.tradable[mk.sess] & ~mk.no_entry
    ok[-2:] = False
    pools = {}
    T = len(tr)
    t_all = np.empty((T, per_trade), np.int64)
    for i in range(T):
        b = bucket[ent[i]]
        if b not in pools:
            pools[b] = np.flatnonzero(ok & (bucket == b))
        t_all[i] = g.choice(pools[b], per_trade)
    t_flat = t_all.ravel()
    a_t = atr_at(t_flat)
    sd = np.repeat(side, per_trade)
    px = mk.c[t_flat]
    so = np.repeat(stop_atr, per_trade) * a_t
    to = np.repeat(tgt_atr, per_trade) * a_t
    good = np.isfinite(so) & (so > 0)
    orders = dict(t=t_flat, side=sd, stop=px - sd * np.where(good, so, 1.0),
                  target=np.where(np.isfinite(to), px + sd * to, np.nan),
                  time_exit=np.minimum(t_flat + np.repeat(hold, per_trade), mk.n - 1),
                  size=np.repeat(size, per_trade), tag=np.arange(len(t_flat)))
    tw = engine.run(mk, orders, independent=True)
    pnl = np.full(len(t_flat), np.nan)
    adj = np.where(np.repeat(limit_entry, per_trade), mk.tick * mk.pv * np.repeat(size, per_trade), 0.0)
    pnl[tw["tag"].to_numpy()] = tw["dollars"].to_numpy() + adj[tw["tag"].to_numpy()]
    pnl[~good] = np.nan
    pnl = pnl.reshape(T, per_trade)
    # fill missing twins (blackout or no ATR) with another twin of the same trade
    for i in np.flatnonzero(np.isnan(pnl).any(axis=1)):
        okk = np.isfinite(pnl[i])
        pnl[i, ~okk] = g.choice(pnl[i, okk], (~okk).sum()) if okk.any() else 0.0
    real = float(tr["dollars"].sum())
    totals = np.zeros(n_sets)
    for start in range(0, n_sets, 500):
        k = min(500, n_sets - start)
        pick = g.integers(0, per_trade, (k, T))
        totals[start:start + k] = pnl[np.arange(T)[None, :], pick].sum(axis=1)
    return {"p": float((totals >= real).mean()), "real_net": real, "twin_mean": float(totals.mean()),
            "twin_p95": float(np.percentile(totals, 95))}


# =========================================================================== stage logic
def apply_stages(nq: pd.DataFrame, es: pd.DataFrame, twins: pd.DataFrame, st: dict = STAGES) -> pd.DataFrame:
    df = nq.set_index("id").add_prefix("nq_").join(es.set_index("id").add_prefix("es_"), how="left")
    df = df.join(twins.set_index("id"), how="left")
    df["s1"] = df["nq_trades"] >= st["stage1_min_trades"]
    df["s2"] = df["s1"] & (df["nq_net"] > st["stage2_min_net_dollars_exclusive"])
    df["s3"] = df["s2"] & (df["nq_sharpe"] >= st["stage3_min_sharpe"])
    df["s4"] = df["s3"] & (df["twin_p"] < st["stage4_max_share_of_sets_as_good"])
    df["s5"] = (df["es_net"] > st["stage5_es_min_net_dollars_exclusive"]) & (df["es_sharpe"] >= st["stage5_es_min_sharpe"])
    df["both_eras"] = (df["nq_net_era1"] > 0) & (df["nq_net_era2"] > 0)
    df["candidate"] = df["s4"] & df["both_eras"] & df["s5"]
    for c in ("s1", "s2", "s3", "s4", "s5", "both_eras", "candidate"):
        df[c] = df[c].fillna(False).astype(bool)
    return df.reset_index()


def judge_setups(daily_avg: dict, era_of: dict, st: dict = STAGES) -> pd.DataFrame:
    """daily_avg[(setup, chart, market)] = equal-weight average daily P&L (pd.Series by session)."""
    rows = []
    for (setup, chart, market), d in sorted(daily_avg.items()):
        yrs = pd.Index(d.index).map(lambda x: x.year)
        by_year = d.groupby(yrs).sum()
        era = np.array([era_of[market].get(s, 0) for s in d.index])
        e1, e2 = float(d[era == 1].sum()), float(d[era == 2].sum())
        sh = engine.sharpe(d)
        works = bool((by_year > 0).all() and sh >= st["setup_min_sharpe"] and e1 > 0 and e2 > 0)
        rows.append({"setup": setup, "chart": chart, "market": market, "net": float(d.sum()), "sharpe": sh,
                     **{f"net_{y}": float(v) for y, v in by_year.items()}, "net_era1": e1, "net_era2": e2,
                     "works": works})
    return pd.DataFrame(rows)
