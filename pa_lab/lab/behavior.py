"""Behavior tests: does price respect levels, flips, breaks, sweeps, gaps and
zones more than a random stand-in?

Each test builds two groups of events (A = the real thing, B = its stand-in
or its counterpart), measures a per-event value, and reports mean(A) - mean(B)
on NQ discovery (the claim) and ES discovery (the replication), on the 5m,
15m, 1h, 4h and daily charts alone and pooled, with 95% intervals from 2,000
bootstrap resamples of whole sessions, and the same point in each era.

Scoring a touch: it holds if price moves 1 ATR away before any close more
than 0.25 ATR through the level; it breaks if that close comes first; it is
unresolved (dropped) after 50 bars.

Random lines: each real level moved up or down by 1-3 ATR (rounded to whole
ticks, so stand-ins sit on the same price grid as real levels), at least 0.5 ATR
from any live real level, same lifetime and touch label. The same for trend
lines, zones and gaps. Random moments: 20 random bars from the same chart,
the same 30 minutes of the day and the same direction.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numba import njit

from . import detectors as det
from . import strategy as sg
from .seed import rng

CHARTS = ["5m", "15m", "1h", "4h", "daily"]
K = 3
TOL = 0.25
HOLD_ATR, THROUGH_ATR, MAX_BARS = 1.0, 0.25, 50
N_BOOT = 2000
N_RANDOM_MOMENTS = 20


# =========================================================================== event machinery
@njit(cache=True)
def episodes(h, l, c, t_open, j0, j1, lo, hi, slope, t0):
    """First bar of every touch of each band, the side price came from, and the touch number."""
    cap = 1024
    ob = np.empty(cap, np.int64); jj = np.empty(cap, np.int64)
    sd = np.empty(cap, np.int64); nth = np.empty(cap, np.int64)
    m = 0
    for k in range(len(j0)):
        if j1[k] < j0[k] or j0[k] < 1:
            continue
        dl = slope[k] * (t_open[j0[k]] - t0[k])
        prev = 1 if c[j0[k] - 1] > hi[k] + dl else (-1 if c[j0[k] - 1] < lo[k] + dl else 0)
        inside = False
        cnt = 0
        for j in range(j0[k], j1[k] + 1):
            dl = slope[k] * (t_open[j] - t0[k])
            blo = lo[k] + dl
            bhi = hi[k] + dl
            touch = l[j] <= bhi and h[j] >= blo
            if touch and not inside and prev != 0:
                cnt += 1
                if m == cap:
                    cap *= 2
                    a = np.empty(cap, np.int64); a[:m] = ob[:m]; ob = a
                    a = np.empty(cap, np.int64); a[:m] = jj[:m]; jj = a
                    a = np.empty(cap, np.int64); a[:m] = sd[:m]; sd = a
                    a = np.empty(cap, np.int64); a[:m] = nth[:m]; nth = a
                ob[m] = k; jj[m] = j; sd[m] = prev; nth[m] = cnt
                m += 1
            inside = touch
            if not touch:
                prev = 1 if c[j] > bhi else (-1 if c[j] < blo else prev)
    return ob[:m], jj[:m], sd[:m], nth[:m]


@njit(cache=True)
def score_touches(h, l, c, atr, j, side, lo, hi, hold_atr, through_atr, max_bars):
    """+1 hold, -1 break, 0 unresolved. lo/hi are the band at the touch."""
    n = len(c)
    out = np.zeros(len(j), np.int64)
    for k in range(len(j)):
        a = atr[j[k]]
        if not (a > 0):
            continue
        s = side[k]
        tgt = hi[k] + hold_atr * a if s == 1 else lo[k] - hold_atr * a
        thr = lo[k] - through_atr * a if s == 1 else hi[k] + through_atr * a
        if (s == 1 and c[j[k]] < thr) or (s == -1 and c[j[k]] > thr):
            out[k] = -1
            continue
        for q in range(j[k] + 1, min(j[k] + max_bars + 1, n)):
            if (s == 1 and h[q] >= tgt) or (s == -1 and l[q] <= tgt):
                out[k] = 1
                break
            if (s == 1 and c[q] < thr) or (s == -1 and c[q] > thr):
                out[k] = -1
                break
    return out


def fwd_return(ch, idx, side, horizon):
    """Signed move from the event close to the close `horizon` bars later, in ATR."""
    idx = np.asarray(idx, np.int64)
    ok = idx + horizon < len(ch.c)
    out = np.full(len(idx), np.nan)
    i = idx[ok]
    a = ch.atr[i]
    out[ok] = np.asarray(side)[ok] * (ch.c[i + horizon] - ch.c[i]) / np.where(a > 0, a, np.nan)
    return out


def tod_bucket(ch, idx):
    et = pd.to_datetime(ch.open_ns[idx], utc=True).tz_convert("America/New_York")
    return ((et.hour * 60 + et.minute) // 30).to_numpy()


@dataclass
class Group:
    value: np.ndarray       # per event (1/0 for rates, ATR for returns)
    sess: np.ndarray        # session ordinal
    chart: np.ndarray       # chart name per event

    @staticmethod
    def make(value, sess, chart):
        value = np.asarray(value, float)
        ok = np.isfinite(value)
        return Group(value[ok], np.asarray(sess)[ok], np.full(ok.sum(), chart, dtype=object))

    @staticmethod
    def cat(gs):
        gs = [g for g in gs if g is not None and len(g.value)]
        if not gs:
            return Group(np.zeros(0), np.zeros(0, np.int64), np.zeros(0, dtype=object))
        return Group(np.concatenate([g.value for g in gs]), np.concatenate([g.sess for g in gs]),
                     np.concatenate([g.chart for g in gs]))


# =========================================================================== bootstrap and verdicts
def boot_weights(n_sess: int, stream: str) -> np.ndarray:
    g = rng(stream)
    return g.multinomial(n_sess, np.full(n_sess, 1.0 / n_sess), size=N_BOOT).astype(np.float64)


def diff_stats(A: Group, B: Group, W: np.ndarray, era: np.ndarray) -> dict:
    S = W.shape[1]
    def sums(G):
        s = np.bincount(G.sess, weights=G.value, minlength=S)
        n = np.bincount(G.sess, minlength=S).astype(float)
        return s, n
    sa, na = sums(A)
    sb, nb = sums(B)
    if na.sum() == 0 or nb.sum() == 0:
        return dict(n_a=int(na.sum()), n_b=int(nb.sum()), mean_a=np.nan, mean_b=np.nan, point=np.nan,
                    lo=np.nan, hi=np.nan, era1=np.nan, era2=np.nan)
    point = sa.sum() / na.sum() - sb.sum() / nb.sum()
    with np.errstate(invalid="ignore", divide="ignore"):
        bs = (W @ sa) / (W @ na) - (W @ sb) / (W @ nb)
    bs = bs[np.isfinite(bs)]
    out = dict(n_a=int(na.sum()), n_b=int(nb.sum()), mean_a=sa.sum() / na.sum(), mean_b=sb.sum() / nb.sum(),
               point=point, lo=float(np.percentile(bs, 2.5)), hi=float(np.percentile(bs, 97.5)))
    for e in (1, 2):
        m = era == e
        a_n, b_n = na[m].sum(), nb[m].sum()
        out[f"era{e}"] = (sa[m].sum() / a_n - sb[m].sum() / b_n) if a_n and b_n else np.nan
    return out


def verdict(nq: dict, es: dict, claim: int = 1) -> tuple[str, str]:
    c1 = np.isfinite(nq["point"]) and claim * nq["point"] > 0 and (claim * nq["lo"] > 0 if claim > 0 else claim * nq["hi"] > 0)
    c2 = np.isfinite(es["point"]) and claim * es["point"] > 0
    c3 = all(np.isfinite(nq[e]) and claim * nq[e] > 0 for e in ("era1", "era2"))
    if c1 and c2 and c3:
        return "true", "NQ pooled points the claimed way with an interval excluding zero; ES agrees; both eras agree."
    if c1:
        miss = [x for x, ok in (("ES has the opposite sign", c2), ("the eras disagree", c3)) if not ok]
        return "split", "NQ pooled holds, but " + " and ".join(miss) + "."
    why = "points the other way" if np.isfinite(nq["point"]) and claim * nq["point"] <= 0 else "has an interval that includes zero"
    return "false", f"NQ pooled {why}."


# =========================================================================== objects on one chart
class ChartLab:
    """Detectors and real/random stand-ins on one chart of one market."""

    def __init__(self, mk, chart: str, stream: str):
        self.mk, self.name = mk, chart
        self.ch = mk.charts[chart]
        self.g = rng(f"behavior:{stream}:{mk.name}:{chart}")
        ch = self.ch
        self.sw = sg.swings(mk, chart, K)
        self.st = sg.structure(mk, chart, K)
        self.lv = {shape: sg.levels(mk, chart, K, TOL, 1, shape) for shape in ("line", "box")}
        self.trad = mk.tradable[ch.session]
        self.tod = tod_bucket(ch, np.arange(len(ch.c)))

    # ---------------------------------------------------- bands -> touches -> scores
    def touches(self, known, end, lo, hi, slope=None, t0=None, side_req=None):
        ch = self.ch
        n = len(known)
        slope = np.zeros(n) if slope is None else slope
        t0 = np.zeros(n, np.int64) if t0 is None else t0
        j0 = np.asarray(known, np.int64) + 1
        ob, j, sd, nth = episodes(ch.h, ch.l, ch.c, ch.open_ns, j0, np.asarray(end, np.int64),
                                  np.asarray(lo, float), np.asarray(hi, float), slope, t0)
        dl = slope[ob] * (ch.open_ns[j] - t0[ob])
        blo, bhi = np.asarray(lo)[ob] + dl, np.asarray(hi)[ob] + dl
        score = score_touches(ch.h, ch.l, ch.c, ch.atr, j, sd, blo, bhi, HOLD_ATR, THROUGH_ATR, MAX_BARS)
        df = pd.DataFrame({"obj": ob, "j": j, "side": sd, "nth": nth, "lo": blo, "hi": bhi, "score": score})
        if side_req is not None:
            df = df[np.asarray(side_req)[df.obj] * df.side >= 0]
        df = df[self.trad[df.j.to_numpy()]]
        return df

    def hold_group(self, df) -> Group:
        r = df[df.score != 0]
        return Group.make((r.score == 1).astype(float), self.ch.session[r.j.to_numpy()], self.name)

    def shift_bands(self, born, lo, hi, real_prices_at, atr_at):
        """Move each band 1-3 ATR up or down, at least 0.5 ATR from any live real level."""
        n = len(born)
        out_lo, out_hi = np.empty(n), np.empty(n)
        for i in range(n):
            a = atr_at[i] if np.isfinite(atr_at[i]) else 0.0
            live = real_prices_at(born[i])
            for _ in range(50):
                d = self.g.choice([-1, 1]) * self.g.uniform(1, 3) * a
                d = np.round(d / self.mk.tick) * self.mk.tick   # stay on the tick grid like real levels
                mid = (lo[i] + hi[i]) / 2 + d
                if len(live) == 0 or np.min(np.abs(live - mid)) >= 0.5 * a:
                    break
            out_lo[i], out_hi[i] = lo[i] + d, hi[i] + d
        return out_lo, out_hi

    def random_levels(self, lv: det.Levels):
        born, end = lv.born, lv.end
        order = np.argsort(born)
        def live(t):
            m = (born <= t) & (end >= t)
            return lv.price[m]
        lo, hi = self.shift_bands(born, lv.lo, lv.hi, live, self.ch.atr[np.minimum(born, len(self.ch.c) - 1)])
        return det.Levels(born, end, (lo + hi) / 2, lo, hi, lv.n_swings)

    def random_moments(self, idx, side, horizon) -> Group:
        """20 random bars per event: same chart, same 30-minute bucket, same direction."""
        ch = self.ch
        pool = {}
        ok_all = self.trad & np.isfinite(ch.atr)
        ok_all[len(ch.c) - horizon - 1:] = False
        vals, sess = [], []
        for i, s in zip(idx, side):
            b = self.tod[i]
            if b not in pool:
                pool[b] = np.flatnonzero(ok_all & (self.tod == b))
            p = pool[b]
            if not len(p):
                continue
            r = self.g.choice(p, N_RANDOM_MOMENTS)
            v = fwd_return(ch, r, np.full(len(r), s), horizon)
            vals.append(v)
            sess.append(ch.session[r])
        if not vals:
            return Group.make([], [], self.name)
        return Group.make(np.concatenate(vals), np.concatenate(sess), self.name)

    def event_group(self, idx, side, horizon) -> Group:
        idx = np.asarray(idx, np.int64)
        m = self.trad[idx]
        return Group.make(fwd_return(self.ch, idx[m], np.asarray(side)[m], horizon), self.ch.session[idx[m]], self.name)


# =========================================================================== the tests
def _lvl_touch_df(cl: ChartLab, lv):
    return cl.touches(lv.born, lv.end, lv.lo, lv.hi)


def t_levels_vs_random(cl):
    lv = cl.lv["line"]
    return cl.hold_group(_lvl_touch_df(cl, lv)), cl.hold_group(_lvl_touch_df(cl, cl.random_levels(lv)))


def t_hold_by_touch_count(cl):
    df = _lvl_touch_df(cl, cl.lv["line"])
    return cl.hold_group(df[df.nth >= 3]), cl.hold_group(df[df.nth == 1])


def t_wall_or_target(cl):
    lv = cl.lv["line"]
    a = _lvl_touch_df(cl, lv)
    b = _lvl_touch_df(cl, cl.random_levels(lv))
    return cl.hold_group(a[a.nth >= 3]), cl.hold_group(b[b.nth >= 3])


def t_shrinking_bounces(cl):
    """Break rate at a touch after the last two bounces shrank, against touches where they did not."""
    ch = cl.ch
    df = _lvl_touch_df(cl, cl.lv["line"]).sort_values(["obj", "j"])
    shrink = np.zeros(len(df), bool)
    valid = np.zeros(len(df), bool)
    obj, j, side, hi, lo = (df[c].to_numpy() for c in ("obj", "j", "side", "hi", "lo"))
    for i in range(2, len(df)):
        if obj[i] != obj[i - 1] or obj[i] != obj[i - 2]:
            continue
        def bounce(a, b, s, k):
            seg = slice(j[a], j[b])
            return (ch.h[seg].max() - hi[k]) if s == 1 else (lo[k] - ch.l[seg].min())
        if side[i] != side[i - 1] or side[i] != side[i - 2]:
            continue
        b1 = bounce(i - 2, i - 1, side[i], i)
        b2 = bounce(i - 1, i, side[i], i)
        valid[i] = True
        shrink[i] = b2 < b1
    r = df[(df.score != 0).to_numpy() & valid]
    s = shrink[(df.score != 0).to_numpy() & valid]
    brk = (r.score == -1).astype(float).to_numpy()
    sess = ch.session[r.j.to_numpy()]
    return Group.make(brk[s], sess[s], cl.name), Group.make(brk[~s], sess[~s], cl.name)


def t_line_vs_box(cl):
    """Two-touch levels: a one-swing box has no width and equals its line."""
    box = sg.levels(cl.mk, cl.name, K, TOL, 2, "box")
    line = sg.levels(cl.mk, cl.name, K, TOL, 2, "line")
    return cl.hold_group(_lvl_touch_df(cl, box)), cl.hold_group(_lvl_touch_df(cl, line))


def t_wick_vs_close(cl):
    """20-bar move in the level's defence direction after a wick through it vs a close through it."""
    ch = cl.ch
    df = _lvl_touch_df(cl, cl.lv["line"])
    j, s, lo, hi = df.j.to_numpy(), df.side.to_numpy(), df.lo.to_numpy(), df.hi.to_numpy()
    wick = np.where(s == 1, (ch.l[j] < lo) & (ch.c[j] >= lo), (ch.h[j] > hi) & (ch.c[j] <= hi))
    close = np.where(s == 1, ch.c[j] < lo, ch.c[j] > hi)
    return cl.event_group(j[wick], s[wick], 20), cl.event_group(j[close], s[close], 20)


def t_flip_zones(cl):
    """First touch from the far side after a level is broken, against random-line touches."""
    lv = cl.lv["line"]
    df = _lvl_touch_df(cl, lv).sort_values(["obj", "j"])
    first_side = df.groupby("obj")["side"].transform("first")
    flips = df[df.side != first_side].groupby("obj").head(1)
    rnd = _lvl_touch_df(cl, cl.random_levels(lv))
    return cl.hold_group(flips), cl.hold_group(rnd)


def _structure_events(cl, kind):
    st = cl.st
    m = st.ev_kind == kind
    return st.ev_idx[m], st.ev_dir[m]


def make_follow(kind, horizon):
    def t(cl):
        idx, d = _structure_events(cl, kind)
        m = cl.trad[idx]
        return cl.event_group(idx, d, horizon), cl.random_moments(idx[m], d[m], horizon)
    return t


def _sweep_events(cl):
    rows = sg.sweeps(cl.ch, cl.lv["line"], 0.5, 2)
    if not rows:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    a = np.array(rows)
    return a[:, 1].astype(np.int64), a[:, 2].astype(np.int64)


def t_sweeps_vs_closes(cl):
    """20-bar move in the reclaim direction after a sweep, against the same
    direction after a close through the level (the move a sweep claims to reverse)."""
    si, sd = _sweep_events(cl)
    br = sg.level_breaks(cl.ch, cl.lv["line"])
    bi, bd = (br[:, 1], br[:, 2]) if len(br) else (np.zeros(0, np.int64),) * 2
    return cl.event_group(si, sd, 20), cl.event_group(bi, -bd, 20)


def t_trend_start_sweep(cl):
    """CHoCH preceded within 10 bars by a sweep in its direction, against CHoCH without one."""
    ci, cd = _structure_events(cl, det.CHOCH)
    si, sd = _sweep_events(cl)
    with_sweep = np.zeros(len(ci), bool)
    for k in range(len(ci)):
        m = (si <= ci[k]) & (si >= ci[k] - 10) & (sd == cd[k])
        with_sweep[k] = m.any()
    return (cl.event_group(ci[with_sweep], cd[with_sweep], 20),
            cl.event_group(ci[~with_sweep], cd[~with_sweep], 20))


def t_trend_lines(cl):
    ch = cl.ch
    tl = det.trend_lines(cl.sw, ch.c, ch.atr, 2, TOL)
    if not len(tl.born):
        return Group.cat([]), Group.cat([])
    bar_ns = np.median(np.diff(ch.open_ns))
    slope = tl.slope / bar_ns
    t0 = ch.open_ns[tl.x0]
    a = cl.touches(tl.born, tl.end, tl.y0, tl.y0, slope, t0, tl.side)
    atr = ch.atr[np.minimum(tl.born, len(ch.c) - 1)]
    def live(t):
        m = (tl.born <= t) & (tl.end >= t)
        return (tl.y0 + slope * (ch.open_ns[t] - t0))[m]
    lo, hi = cl.shift_bands(tl.born, tl.y0, tl.y0, live, atr)
    b = cl.touches(tl.born, tl.end, lo, hi, slope, t0, tl.side)
    return cl.hold_group(a), cl.hold_group(b)


def _gaps(cl):
    ch = cl.ch
    return det.fair_value_gaps(ch.h, ch.l, ch.atr, 0.0, MAX_BARS)


def _random_bands(cl, born, end, lo, hi):
    atr = cl.ch.atr[np.minimum(born, len(cl.ch.c) - 1)]
    mids = (lo + hi) / 2
    def live(t):
        m = (born <= t) & (end >= t)
        return mids[m]
    return cl.shift_bands(born, lo, hi, live, atr)


def t_fvg_hold(cl):
    g = _gaps(cl)
    a = cl.touches(g.born, g.end, g.lo, g.hi, side_req=g.side)
    a = a.sort_values(["obj", "j"]).groupby("obj").head(1)
    lo, hi = _random_bands(cl, g.born, g.end, g.lo, g.hi)
    b = cl.touches(g.born, g.end, lo, hi).sort_values(["obj", "j"]).groupby("obj").head(1)
    return cl.hold_group(a), cl.hold_group(b)


def t_fvg_fill(cl):
    """Share of gaps price trades back into within 50 bars, against random bands of the same size."""
    ch = cl.ch
    g = _gaps(cl)
    m = cl.trad[g.born]
    lo, hi = _random_bands(cl, g.born, g.end, g.lo, g.hi)
    def filled(lo_, hi_):
        out = np.zeros(len(g.born))
        for i in range(len(g.born)):
            seg = slice(g.born[i] + 1, min(g.born[i] + MAX_BARS + 1, len(ch.c)))
            out[i] = float(((ch.l[seg] <= hi_[i]) & (ch.h[seg] >= lo_[i])).any())
        return out
    s = ch.session[g.born]
    return Group.make(filled(g.lo, g.hi)[m], s[m], cl.name), Group.make(filled(lo, hi)[m], s[m], cl.name)


def _zones(cl):
    ch = cl.ch
    return det.zones(ch.o, ch.h, ch.l, ch.c, ch.atr, 3, 2.0, sg.ZONE_LIFE)


def t_zones_first_vs_later(cl):
    z = _zones(cl)
    df = cl.touches(z.born, z.end, z.lo, z.hi, side_req=z.side)
    return cl.hold_group(df[df.nth == 1]), cl.hold_group(df[df.nth > 1])


def t_zones_vs_random(cl):
    z = _zones(cl)
    a = cl.touches(z.born, z.end, z.lo, z.hi, side_req=z.side)
    lo, hi = _random_bands(cl, z.born, z.end, z.lo, z.hi)
    b = cl.touches(z.born, z.end, lo, hi)
    return cl.hold_group(a[a.nth == 1]), cl.hold_group(b[b.nth == 1])


def t_pullback_depth(cl):
    """20-bar follow-through after a BOS whose preceding pullback was shallow (<50% of the
    leg) against one whose pullback was deep (50-100%)."""
    sw, st = cl.sw, cl.st
    idx, d = _structure_events(cl, det.BOS)
    depth = np.full(len(idx), np.nan)
    for k in range(len(idx)):
        m = sw.known <= idx[k]
        if m.sum() < 3:
            continue
        p, t = sw.price[m][-3:], sw.typ[m][-3:]
        if d[k] == 1 and list(t[-2:]) == [1, -1]:      # ... low, high, pullback low
            leg = p[-2] - (p[-3] if t[-3] == -1 else np.nan)
            depth[k] = (p[-2] - p[-1]) / leg if leg and leg > 0 else np.nan
        if d[k] == -1 and list(t[-2:]) == [-1, 1]:
            leg = (p[-3] if t[-3] == 1 else np.nan) - p[-2]
            depth[k] = (p[-1] - p[-2]) / leg if leg and leg > 0 else np.nan
    sh = depth < 0.5
    dp = (depth >= 0.5) & (depth <= 1.0)
    return cl.event_group(idx[sh], d[sh], 20), cl.event_group(idx[dp], d[dp], 20)


def make_candle_at_levels(kind):
    def t(cl):
        ch = cl.ch
        df = _lvl_touch_df(cl, cl.lv["line"])
        j, s = df.j.to_numpy(), df.side.to_numpy()
        o, h, l, c = ch.o, ch.h, ch.l, ch.c
        rng_ = h[j] - l[j]
        if kind == "rejection":
            hit = np.where(s == 1, (np.minimum(o[j], c[j]) - l[j]) >= 0.5 * rng_,
                           (h[j] - np.maximum(o[j], c[j])) >= 0.5 * rng_) & (rng_ > 0)
        else:
            pj = np.maximum(j - 1, 0)
            hit = np.where(s == 1, (c[j] > o[j]) & (c[pj] < o[pj]) & (c[j] >= o[pj]) & (o[j] <= c[pj]),
                           (c[j] < o[j]) & (c[pj] > o[pj]) & (c[j] <= o[pj]) & (o[j] >= c[pj]))
        jj, ss = j[hit], s[hit]
        # stand-in: the same candle shape at random moments of the same chart, time of day and direction
        allj = np.arange(1, len(c))
        if kind == "rejection":
            up = (np.minimum(o[allj], c[allj]) - l[allj]) >= 0.5 * (h[allj] - l[allj])
            dn = (h[allj] - np.maximum(o[allj], c[allj])) >= 0.5 * (h[allj] - l[allj])
        else:
            p = allj - 1
            up = (c[allj] > o[allj]) & (c[p] < o[p]) & (c[allj] >= o[p]) & (o[allj] <= c[p])
            dn = (c[allj] < o[allj]) & (c[p] > o[p]) & (c[allj] <= o[p]) & (o[allj] >= c[p])
        trad = cl.trad[allj] & np.isfinite(ch.atr[allj])
        vals, sess = [], []
        for i, sd in zip(jj, ss):
            pool = allj[(up if sd == 1 else dn) & trad & (cl.tod[allj] == cl.tod[i])]
            pool = pool[pool < len(c) - 21]
            if not len(pool):
                continue
            r = cl.g.choice(pool, N_RANDOM_MOMENTS)
            vals.append(fwd_return(ch, r, np.full(len(r), sd), 20))
            sess.append(ch.session[r])
        b = Group.make(np.concatenate(vals) if vals else [], np.concatenate(sess) if sess else [], cl.name)
        return cl.event_group(jj, ss, 20), b
    return t


TESTS = {
    # name: (function, claim sign, metric, one-line claim)
    "levels_vs_random": (t_levels_vs_random, 1, "hold rate", "Real levels hold more often than random lines."),
    "hold_by_touch_count": (t_hold_by_touch_count, 1, "hold rate", "A level's 3rd+ touch holds more often than its 1st."),
    "wall_or_target": (t_wall_or_target, 1, "hold rate", "A level touched 3+ times acts as a wall (holds more than a random line touched as often), not a target."),
    "shrinking_bounces": (t_shrinking_bounces, 1, "break rate", "After two shrinking bounces, the next touch breaks more often."),
    "line_vs_box": (t_line_vs_box, 1, "hold rate", "A level drawn as a box holds more often than one drawn as a line."),
    "wick_vs_close_through": (t_wick_vs_close, 1, "20-bar move (ATR)", "A wick through a level is followed by more move in the level's favour than a close through it."),
    "flip_zones": (t_flip_zones, 1, "hold rate", "A broken level holds from the other side more often than a random line."),
    "bos_follow_10": (make_follow(det.BOS, 10), 1, "10-bar move (ATR)", "A break of structure is followed by more move its way than random bars, at 10 bars."),
    "bos_follow_20": (make_follow(det.BOS, 20), 1, "20-bar move (ATR)", "The same at 20 bars."),
    "bos_follow_50": (make_follow(det.BOS, 50), 1, "50-bar move (ATR)", "The same at 50 bars."),
    "choch_follow_10": (make_follow(det.CHOCH, 10), 1, "10-bar move (ATR)", "A change of character is followed by more move its way than random bars, at 10 bars."),
    "choch_follow_20": (make_follow(det.CHOCH, 20), 1, "20-bar move (ATR)", "The same at 20 bars."),
    "choch_follow_50": (make_follow(det.CHOCH, 50), 1, "50-bar move (ATR)", "The same at 50 bars."),
    "sweeps_vs_closes": (t_sweeps_vs_closes, 1, "20-bar move (ATR)", "A sweep reverses more than a close through the level does."),
    "trend_start_sweep": (t_trend_start_sweep, 1, "20-bar move (ATR)", "A change of character that starts with a sweep follows through more."),
    "trend_lines": (t_trend_lines, 1, "hold rate", "Real trend lines hold more often than shifted lines."),
    "fvg_hold": (t_fvg_hold, 1, "hold rate", "A fair value gap holds on its first return more often than a random band."),
    "fvg_fill": (t_fvg_fill, 1, "fill rate", "Price returns into a fair value gap within 50 bars more often than into a random band."),
    "zones_first_vs_later": (t_zones_first_vs_later, 1, "hold rate", "A supply/demand zone holds better on its first return than on later ones."),
    "zones_vs_random": (t_zones_vs_random, 1, "hold rate", "A supply/demand zone holds better than a random band on first return."),
    "pullback_depth": (t_pullback_depth, 1, "20-bar move (ATR)", "A break after a shallow pullback follows through more than after a deep one."),
    "engulfing_at_levels": (make_candle_at_levels("engulfing"), 1, "20-bar move (ATR)", "An engulfing candle at a level moves more its way than the same candle at random."),
    "rejection_at_levels": (make_candle_at_levels("rejection"), 1, "20-bar move (ATR)", "A rejection candle at a level moves more its way than the same candle at random."),
}


def run_test(name, markets: dict, charts=CHARTS):
    fn, claim, metric, text = TESTS[name]
    rows = {}
    for mname, mk in markets.items():
        W = boot_weights(len(mk.sessions), f"boot:{name}:{mname}")
        As, Bs = [], []
        for chart in charts:
            cl = ChartLab(mk, chart, name)
            A, B = fn(cl)
            As.append(A); Bs.append(B)
            rows[(mname, chart)] = diff_stats(A, B, W, mk.era)
        rows[(mname, "pooled")] = diff_stats(Group.cat(As), Group.cat(Bs), W, mk.era)
    table = pd.DataFrame([{"market": m, "chart": c, **v} for (m, c), v in rows.items()])
    v, why = verdict(rows[("NQ", "pooled")], rows[("ES", "pooled")], claim)
    return table, {"test": name, "claim": text, "metric": f"{metric}: A minus B", "verdict": v, "why": why,
                   "nq_point": rows[("NQ", "pooled")]["point"], "nq_lo": rows[("NQ", "pooled")]["lo"],
                   "nq_hi": rows[("NQ", "pooled")]["hi"], "es_point": rows[("ES", "pooled")]["point"],
                   "nq_era1": rows[("NQ", "pooled")]["era1"], "nq_era2": rows[("NQ", "pooled")]["era2"]}
