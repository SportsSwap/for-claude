"""From a version (one value per dial) to orders and trades.

Stages, each cached so thousands of versions share the work:
  1. detectors on the setup chart          (swing strength, level/zone/gap dials)
  2. setup objects                         (bands to trade at, or break events)
  3. trigger-chart confirmations           (candidates: decision bar, side, wick)
  4. stop, target, filters, time exit      (per version, vectorized)
  5. the engine                            (one position at a time, 1m fills)

No look-ahead: a trigger bar only uses setup-chart objects known at a
setup-bar close at or before the trigger bar's open; decisions happen at a
bar close (tests/test_lookahead.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
from numba import njit

from . import detectors as det
from . import engine
from .charts import ORDER, higher, lower

LIMIT_WINDOW_TRIGGER_BARS = 12      # a limit back at the level lives this many trigger bars
BREAK_RETEST_SETUP_BARS = 12        # break setups: bars allowed for a retest confirmation
PULLBACK_ARM_SETUP_BARS = 50        # trend pullback: how long a pullback zone stays armed
LEVEL_LIFE = 500                    # setup bars a level lives after its last swing
ZONE_LIFE = 500
TRENDLINE_LIFE = 300
INVALIDATE_ATR = 0.25               # a close this far through a band ends the episode
LTF_BOS_TRIGGER_BARS = 3            # lower-chart BOS must come within this many trigger bars

CONF = {"none": 0, "close_back": 1, "rejection_wick": 2, "engulfing": 3, "either_candle": 4, "ltf_bos": 5}
TOUCH_SETUPS = {"level_bounce", "flip_zone", "trend_pullback", "supply_demand_zone", "fair_value_gap"}


# =========================================================================== stage 1: detectors (cached)
_CACHE: dict = {}


def _memo(key, fn):
    if key not in _CACHE:
        _CACHE[key] = fn()
    return _CACHE[key]


def clear_cache():
    _CACHE.clear()


def swings(mk, chart, k):
    ch = mk.charts[chart]
    return _memo((id(mk), "sw", chart, k), lambda: det.swings(ch.h, ch.l, k))


def structure(mk, chart, k):
    ch = mk.charts[chart]
    return _memo((id(mk), "st", chart, k), lambda: det.structure(ch.c, swings(mk, chart, k)))


def levels(mk, chart, k, tol, touches, shape):
    ch = mk.charts[chart]
    return _memo((id(mk), "lv", chart, k, tol, touches, shape),
                 lambda: det.levels(swings(mk, chart, k), ch.atr, tol, touches, shape, LEVEL_LIFE))


# =========================================================================== stage 2: setup objects
@dataclass
class Objects:
    """Bands on the setup chart. A touch object is live on trigger bars that
    open at or after the setup bar `known` closed, up to setup bar `end`.
    A break event (`brk`=True) is the setup-bar close at `known`."""
    known: np.ndarray
    end: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    slope: np.ndarray       # price per ns (trend lines), 0 for flat bands
    t0: np.ndarray          # ns where lo/hi apply (trend lines)
    side: np.ndarray        # required trade side, 0 = either
    first_only: np.ndarray
    brk: np.ndarray
    wick: np.ndarray        # break events: stop reference for touch_wick
    gapmid: np.ndarray      # FVG middle-candle far end
    fresh: np.ndarray


def _objects(n, **kw) -> Objects:
    base = dict(known=np.zeros(n, np.int64), end=np.zeros(n, np.int64), lo=np.zeros(n), hi=np.zeros(n),
                slope=np.zeros(n), t0=np.zeros(n, np.int64), side=np.zeros(n, np.int64),
                first_only=np.zeros(n, bool), brk=np.zeros(n, bool), wick=np.full(n, np.nan),
                gapmid=np.full(n, np.nan), fresh=np.ones(n, bool))
    base.update({k: np.broadcast_to(np.asarray(v), (n,)).copy() for k, v in kw.items()})
    return Objects(**base)


def _concat(objs: list[Objects]) -> Objects:
    objs = [o for o in objs if len(o.known)]
    if not objs:
        return _objects(0)
    return Objects(*[np.concatenate([getattr(o, f) for o in objs]) for f in Objects.__dataclass_fields__])


def level_breaks(ch, lv: det.Levels):
    """First close from one side of a level band to beyond the other side.
    Returns (level id, bar, dir, break number for that level)."""
    rows = []
    c = ch.c
    for i in range(len(lv.born)):
        a, b = lv.born[i] + 1, lv.end[i]
        if b <= a:
            continue
        seg = c[a - 1:b + 1]
        up = (seg[:-1] < lv.lo[i]) & (seg[1:] > lv.hi[i])
        dn = (seg[:-1] > lv.hi[i]) & (seg[1:] < lv.lo[i])
        bars = np.flatnonzero(up | dn)
        for nth, j in enumerate(bars):
            rows.append((i, a + j, 1 if up[j] else -1, nth))
    if not rows:
        return np.zeros((0, 4), np.int64)
    return np.array(rows, np.int64)


def sweeps(ch, lv: det.Levels, depth: float, reclaim: int):
    """Price pokes beyond a band by at most depth*ATR, then closes back inside
    within `reclaim` bars. Returns rows (level, reclaim bar, dir, sweep extreme)."""
    rows = []
    h, l, c, atr = ch.h, ch.l, ch.c, ch.atr
    for i in range(len(lv.born)):
        a, b = lv.born[i] + 1, lv.end[i]
        j = a
        while j <= b:
            if c[j - 1] > lv.hi[i] and l[j] < lv.lo[i] and lv.lo[i] - l[j] <= depth * atr[j]:
                ext = l[j]
                for r in range(j, min(j + reclaim, b + 1)):
                    ext = min(ext, l[r])
                    if c[r] > lv.lo[i]:
                        if lv.lo[i] - ext <= depth * atr[j]:
                            rows.append((i, r, 1, ext))
                        break
                j += reclaim
                continue
            if c[j - 1] < lv.lo[i] and h[j] > lv.hi[i] and h[j] - lv.hi[i] <= depth * atr[j]:
                ext = h[j]
                for r in range(j, min(j + reclaim, b + 1)):
                    ext = max(ext, h[r])
                    if c[r] < lv.hi[i]:
                        if ext - lv.hi[i] <= depth * atr[j]:
                            rows.append((i, r, -1, ext))
                        break
                j += reclaim
                continue
            j += 1
    return rows


def setup_objects(mk, setup: str, sc: str, v: dict) -> Objects:
    key = (id(mk), "obj", setup, sc) + tuple(sorted((k, v[k]) for k in _setup_keys(setup)))
    return _memo(key, lambda: _setup_objects(mk, setup, sc, v))


def _setup_keys(setup):
    lv = ["swing_strength", "level_tol_atr", "level_min_touches", "level_shape"]
    return {"level_bounce": lv, "breakout": lv, "flip_zone": lv + ["retest_window_bars"],
            "trend_pullback": ["swing_strength"],
            "trend_line": ["swing_strength", "trendline_min_touches", "trendline_tol_atr", "trendline_event"],
            "bos_continuation": ["swing_strength"], "choch_reversal": ["swing_strength"],
            "sweep_reclaim": lv + ["sweep_depth_max_atr", "reclaim_bars"],
            "supply_demand_zone": ["swing_strength", "zone_run_candles", "zone_span_atr", "zone_fresh_only"],
            "fair_value_gap": ["swing_strength", "fvg_min_gap_atr", "fvg_max_age_bars"]}[setup]


def _setup_objects(mk, setup, sc, v) -> Objects:
    ch = mk.charts[sc]
    k = v["swing_strength"]
    n = len(ch.c)
    if setup in ("level_bounce", "breakout", "flip_zone", "sweep_reclaim"):
        lv = levels(mk, sc, k, v["level_tol_atr"], v["level_min_touches"], v["level_shape"])
    if setup == "level_bounce":
        return _objects(len(lv.born), known=lv.born, end=lv.end, lo=lv.lo, hi=lv.hi)
    if setup in ("breakout", "flip_zone"):
        br = level_breaks(ch, lv)
        if not len(br):
            return _objects(0)
        li, bar, d, nth = br.T
        if setup == "breakout":
            wick = np.where(d == 1, ch.l[bar], ch.h[bar])
            return _objects(len(bar), known=bar, end=np.minimum(bar + BREAK_RETEST_SETUP_BARS, n - 1),
                            lo=lv.lo[li], hi=lv.hi[li], side=d, brk=True, wick=wick, fresh=nth == 0)
        return _objects(len(bar), known=bar, end=np.minimum(bar + v["retest_window_bars"], n - 1),
                        lo=lv.lo[li], hi=lv.hi[li], side=d, fresh=nth == 0, first_only=True)
    if setup == "sweep_reclaim":
        rows = sweeps(ch, lv, v["sweep_depth_max_atr"], v["reclaim_bars"])
        if not rows:
            return _objects(0)
        a = np.array(rows)
        li, bar, d, ext = a[:, 0].astype(int), a[:, 1].astype(int), a[:, 2].astype(int), a[:, 3]
        return _objects(len(bar), known=bar, end=np.minimum(bar + BREAK_RETEST_SETUP_BARS, n - 1),
                        lo=lv.lo[li], hi=lv.hi[li], side=d, brk=True, wick=ext)
    if setup in ("bos_continuation", "choch_reversal"):
        st = structure(mk, sc, k)
        kind = det.BOS if setup == "bos_continuation" else det.CHOCH
        m = st.ev_kind == kind
        bar, d, lev = st.ev_idx[m], st.ev_dir[m], st.ev_level[m]
        wick = np.where(d == 1, ch.l[bar], ch.h[bar])
        return _objects(len(bar), known=bar, end=np.minimum(bar + BREAK_RETEST_SETUP_BARS, n - 1),
                        lo=lev, hi=lev, side=d, brk=True, wick=wick)
    if setup == "trend_pullback":
        sw = swings(mk, sc, k)
        st = structure(mk, sc, k)
        rows = []
        for i in range(len(sw.known)):
            kb = sw.known[i]
            if kb >= n:
                continue
            tr = st.trend[kb]
            if sw.typ[i] == 1 and tr == 1 and np.isfinite(st.last_sl[kb]) and sw.price[i] > st.last_sl[kb]:
                sh, sl = sw.price[i], st.last_sl[kb]
                rows.append((kb, sl, sh - 0.382 * (sh - sl), 1))
            elif sw.typ[i] == -1 and tr == -1 and np.isfinite(st.last_sh[kb]) and sw.price[i] < st.last_sh[kb]:
                sl, sh = sw.price[i], st.last_sh[kb]
                rows.append((kb, sl + 0.382 * (sh - sl), sh, -1))
        if not rows:
            return _objects(0)
        a = np.array(rows)
        kb = a[:, 0].astype(int)
        return _objects(len(kb), known=kb, end=np.minimum(kb + PULLBACK_ARM_SETUP_BARS, n - 1), lo=a[:, 1],
                        hi=a[:, 2], side=a[:, 3].astype(int), first_only=True)
    if setup == "trend_line":
        tl = det.trend_lines(swings(mk, sc, k), ch.c, ch.atr, v["trendline_min_touches"],
                             v["trendline_tol_atr"], TRENDLINE_LIFE)
        if not len(tl.born):
            return _objects(0)
        bar_ns = np.median(np.diff(ch.open_ns))
        slope_ns = tl.slope / bar_ns
        t0 = ch.open_ns[tl.x0]
        if v["trendline_event"] == "bounce":
            return _objects(len(tl.born), known=tl.born, end=tl.end, lo=tl.y0, hi=tl.y0, slope=slope_ns,
                            t0=t0, side=tl.side)
        rows = []
        for i in range(len(tl.born)):
            for j in range(tl.born[i] + 1, tl.end[i] + 1):
                yv = tl.y0[i] + slope_ns[i] * (ch.open_ns[j] - t0[i])
                if tl.side[i] * (ch.c[j] - yv) < 0:
                    rows.append((j, yv, -tl.side[i], ch.h[j] if tl.side[i] == 1 else ch.l[j]))
                    break
        if not rows:
            return _objects(0)
        a = np.array(rows)
        bar = a[:, 0].astype(int)
        return _objects(len(bar), known=bar, end=np.minimum(bar + BREAK_RETEST_SETUP_BARS, n - 1),
                        lo=a[:, 1], hi=a[:, 1], side=a[:, 2].astype(int), brk=True, wick=a[:, 3])
    if setup == "supply_demand_zone":
        z = _memo((id(mk), "zn", sc, v["zone_run_candles"], v["zone_span_atr"]),
                  lambda: det.zones(ch.o, ch.h, ch.l, ch.c, ch.atr, v["zone_run_candles"], v["zone_span_atr"], ZONE_LIFE))
        return _objects(len(z.born), known=z.born, end=z.end, lo=z.lo, hi=z.hi, side=z.side,
                        first_only=np.full(len(z.born), v["zone_fresh_only"] == "yes"))
    if setup == "fair_value_gap":
        g = _memo((id(mk), "fvg", sc, v["fvg_min_gap_atr"], v["fvg_max_age_bars"]),
                  lambda: det.fair_value_gaps(ch.h, ch.l, ch.atr, v["fvg_min_gap_atr"], v["fvg_max_age_bars"]))
        return _objects(len(g.born), known=g.born, end=g.end, lo=g.lo, hi=g.hi, side=g.side, first_only=True,
                        gapmid=np.where(g.side == 1, g.mid_lo, g.mid_hi))
    raise ValueError(setup)


# =========================================================================== stage 3: trigger confirmations
@njit(cache=True)
def _touches(to, th, tl, tc, t_open, t_avail, j0, j1, lo, hi, slope, t0, side_req, first_only, atr,
             conf, ltf_t, ltf_dir, ltf_last1m, t_last1m, inval):
    """Episodes of trigger bars touching each band; returns candidates
    (object, 1m decision bar, side, episode wick, trigger bar)."""
    cap = 1024
    out_obj = np.empty(cap, np.int64); out_t = np.empty(cap, np.int64); out_side = np.empty(cap, np.int64)
    out_wick = np.empty(cap, np.float64); out_j = np.empty(cap, np.int64)
    m = 0
    for k in range(len(j0)):
        if j1[k] < j0[k]:
            continue
        a = atr[k]
        prev_side = 0
        j = j0[k]
        if j > 0:
            y = lo[k] + slope[k] * (t_open[j] - t0[k])
            yh = hi[k] + slope[k] * (t_open[j] - t0[k])
            prev_side = 1 if tc[j - 1] > yh else (-1 if tc[j - 1] < y else 0)
        done_obj = False
        while j <= j1[k] and not done_obj:
            dl = slope[k] * (t_open[j] - t0[k])
            blo = lo[k] + dl
            bhi = hi[k] + dl
            touch = tl[j] <= bhi and th[j] >= blo
            if touch and prev_side != 0 and (side_req[k] == 0 or side_req[k] == prev_side):
                s = prev_side
                wick = tl[j] if s == 1 else th[j]
                found = False
                jj = j
                last = min(j1[k], j + LTF_BARS if conf == 5 else j + 2)
                if conf == 0:
                    last = j
                while jj <= last:
                    dl2 = slope[k] * (t_open[jj] - t0[k])
                    blo2 = lo[k] + dl2
                    bhi2 = hi[k] + dl2
                    wick = min(wick, tl[jj]) if s == 1 else max(wick, th[jj])
                    if (s == 1 and tc[jj] < blo2 - inval * a) or (s == -1 and tc[jj] > bhi2 + inval * a):
                        break
                    body_lo = min(to[jj], tc[jj])
                    body_hi = max(to[jj], tc[jj])
                    rng = th[jj] - tl[jj]
                    cb = (s == 1 and tc[jj] > bhi2) or (s == -1 and tc[jj] < blo2)
                    rw = rng > 0 and ((s == 1 and body_lo - tl[jj] >= 0.5 * rng and tc[jj] > blo2)
                                      or (s == -1 and th[jj] - body_hi >= 0.5 * rng and tc[jj] < bhi2))
                    en = jj > 0 and ((s == 1 and tc[jj] > to[jj] and tc[jj - 1] < to[jj - 1]
                                      and tc[jj] >= to[jj - 1] and to[jj] <= tc[jj - 1])
                                     or (s == -1 and tc[jj] < to[jj] and tc[jj - 1] > to[jj - 1]
                                         and tc[jj] <= to[jj - 1] and to[jj] >= tc[jj - 1]))
                    ok = (conf == 0) or (conf == 1 and cb) or (conf == 2 and rw) or (conf == 3 and en) \
                        or (conf == 4 and (rw or en))
                    tt = -1
                    if ok:
                        tt = t_last1m[jj]
                    elif conf == 5:
                        q = np.searchsorted(ltf_t, t_open[j])
                        while q < len(ltf_t) and ltf_t[q] <= t_avail[jj]:
                            if ltf_dir[q] == s:
                                tt = ltf_last1m[q]
                                break
                            q += 1
                    if tt >= 0:
                        if m == cap:
                            cap *= 2
                            a1 = np.empty(cap, np.int64); a1[:m] = out_obj[:m]; out_obj = a1
                            a2 = np.empty(cap, np.int64); a2[:m] = out_t[:m]; out_t = a2
                            a3 = np.empty(cap, np.int64); a3[:m] = out_side[:m]; out_side = a3
                            a4 = np.empty(cap, np.float64); a4[:m] = out_wick[:m]; out_wick = a4
                            a5 = np.empty(cap, np.int64); a5[:m] = out_j[:m]; out_j = a5
                        out_obj[m] = k; out_t[m] = tt; out_side[m] = s; out_wick[m] = wick; out_j[m] = jj
                        m += 1
                        found = True
                        break
                    jj += 1
                if found or first_only[k]:
                    done_obj = first_only[k]
                # skip to the end of this episode
                j = max(jj, j) + 1
                while j <= j1[k]:
                    dl = slope[k] * (t_open[j] - t0[k])
                    if not (tl[j] <= hi[k] + dl and th[j] >= lo[k] + dl):
                        break
                    j += 1
                if j <= j1[k]:
                    dl = slope[k] * (t_open[j] - t0[k])
                    prev_side = 1 if tc[j - 1] > hi[k] + dl else (-1 if tc[j - 1] < lo[k] + dl else 0)
                continue
            if not touch:
                prev_side = 1 if tc[j] > bhi else (-1 if tc[j] < blo else prev_side)
            j += 1
    return out_obj[:m], out_t[:m], out_side[:m], out_wick[:m], out_j[:m]


LTF_BARS = LTF_BOS_TRIGGER_BARS


@dataclass
class Candidates:
    t: np.ndarray           # 1m decision bar (entry at its close or limit placed then)
    side: np.ndarray
    level: np.ndarray       # near edge of the band in trade direction (limit price)
    far: np.ndarray         # far edge (beyond-the-level stop reference)
    wick: np.ndarray
    gapmid: np.ndarray
    fresh: np.ndarray
    tj: np.ndarray          # trigger bar of the decision
    sbar: np.ndarray        # last setup bar closed at the decision
    resting: np.ndarray     # limit resting from the arm (confirmation none + limit)
    lim_end: np.ndarray     # 1m bar a resting limit lives to

    def __len__(self):
        return len(self.t)


def candidates(mk, setup, sc, tc, v) -> Candidates:
    keys = tuple(sorted((k, v[k]) for k in _setup_keys(setup)))
    key = (id(mk), "cand", setup, sc, tc, v["confirmation"], v["entry"] if v["confirmation"] == "none" else "") + keys
    return _memo(key, lambda: _candidates(mk, setup, sc, tc, v))


def _empty_cands():
    z = np.zeros(0)
    zi = z.astype(np.int64)
    return Candidates(zi, zi, z, z, z, z, z.astype(bool), zi, zi, z.astype(bool), zi)


def _band_at(ob, idx, t_ns):
    dl = ob.slope[idx] * (t_ns - ob.t0[idx])
    return ob.lo[idx] + dl, ob.hi[idx] + dl


def _candidates(mk, setup, sc, tc, v) -> Candidates:
    S, Tg = mk.charts[sc], mk.charts[tc]
    ob = setup_objects(mk, setup, sc, v)
    if not len(ob.known):
        return _empty_cands()
    conf = CONF[v["confirmation"]]
    k = v["swing_strength"]
    known_ns = S.avail_ns[ob.known]
    end_ns = S.avail_ns[ob.end]
    rows = []
    # break events entered at the break close (confirmation none)
    brk = ob.brk
    if conf == 0 and brk.any():
        bi = np.flatnonzero(brk)
        t = S.last_1m[ob.known[bi]]
        near = np.where(ob.side[bi] == 1, ob.hi[bi], ob.lo[bi])
        far = np.where(ob.side[bi] == 1, ob.lo[bi], ob.hi[bi])
        tj = np.searchsorted(Tg.avail_ns, S.avail_ns[ob.known[bi]], side="right") - 1
        resting = np.zeros(len(bi), bool)
        lim_end = np.full(len(bi), -1, np.int64)
        rows.append((t, ob.side[bi], near, far, ob.wick[bi], ob.gapmid[bi], ob.fresh[bi], tj, ob.known[bi],
                     resting, lim_end))
    # resting limits at touch bands (confirmation none + limit): placed when the object is known
    touch_idx = np.flatnonzero(~brk)
    if conf == 0 and v["entry"] == "limit_at_level" and len(touch_idx):
        ti = touch_idx
        t = S.last_1m[ob.known[ti]]
        lo, hi = _band_at(ob, ti, known_ns[ti])
        price_now = mk.c[t]
        side = np.where(ob.side[ti] != 0, ob.side[ti], np.where(price_now > hi, 1, -1))
        ok = side * (price_now - np.where(side == 1, hi, lo)) > 0
        ti, t, side, lo, hi = ti[ok], t[ok], side[ok], lo[ok], hi[ok]
        tj = np.searchsorted(Tg.avail_ns, known_ns[ti], side="right") - 1
        rows.append((t, side, np.where(side == 1, hi, lo), np.where(side == 1, lo, hi),
                     np.where(side == 1, lo, hi), ob.gapmid[ti], ob.fresh[ti], tj, ob.known[ti],
                     np.ones(len(ti), bool), S.last_1m[ob.end[ti]]))
        touch_idx = np.zeros(0, np.int64)
    # touches on the trigger chart (touch setups, and break setups waiting for a retest)
    scan = touch_idx if conf != 0 else np.zeros(0, np.int64)
    if conf != 0:
        scan = np.arange(len(ob.known))
    elif v["entry"] != "limit_at_level":
        scan = touch_idx
    if len(scan):
        j0 = np.searchsorted(Tg.open_ns, known_ns[scan], side="left")
        j1 = np.searchsorted(Tg.avail_ns, end_ns[scan], side="right") - 1
        low = lower(tc)
        if conf == 5 and low is not None:
            L = mk.charts[low]
            st = structure(mk, low, k)
            ltf_t, ltf_dir, ltf_last = L.avail_ns[st.ev_idx], st.ev_dir, L.last_1m[st.ev_idx]
        else:
            ltf_t = np.zeros(0, np.int64); ltf_dir = np.zeros(0, np.int64); ltf_last = np.zeros(0, np.int64)
        atr_k = S.atr[ob.known[scan]]
        oo, t, s, w, tj = _touches(Tg.o, Tg.h, Tg.l, Tg.c, Tg.open_ns, Tg.avail_ns, j0, j1,
                                   ob.lo[scan], ob.hi[scan], ob.slope[scan], ob.t0[scan], ob.side[scan],
                                   ob.first_only[scan], np.nan_to_num(atr_k, nan=np.inf), conf,
                                   ltf_t.astype(np.int64), ltf_dir.astype(np.int64), ltf_last.astype(np.int64),
                                   Tg.last_1m, INVALIDATE_ATR)
        if len(oo):
            oi = scan[oo]
            lo, hi = _band_at(ob, oi, Tg.open_ns[tj])
            rows.append((t, s, np.where(s == 1, hi, lo), np.where(s == 1, lo, hi), w, ob.gapmid[oi],
                         ob.fresh[oi], tj, ob.known[oi], np.zeros(len(oi), bool), np.full(len(oi), -1, np.int64)))
    if not rows:
        return _empty_cands()
    cols = [np.concatenate([r[i] for r in rows]) for i in range(11)]
    order = np.argsort(cols[0], kind="stable")
    cols = [c[order] for c in cols]
    # the last setup bar closed by each decision
    dec_ns = mk.ts_ns[cols[0]] + 60_000_000_000
    cols[8] = np.searchsorted(S.avail_ns, dec_ns, side="right") - 1
    return Candidates(cols[0].astype(np.int64), cols[1].astype(np.int64), cols[2].astype(float),
                      cols[3].astype(float), cols[4].astype(float), cols[5].astype(float), cols[6].astype(bool),
                      cols[7].astype(np.int64), cols[8].astype(np.int64), cols[9].astype(bool),
                      cols[10].astype(np.int64))


# =========================================================================== stage 4: orders
def _asof(chart, dec_ns):
    return np.searchsorted(chart.avail_ns, dec_ns, side="right") - 1


def _trend_at(mk, chart, k, dec_ns):
    ch = mk.charts[chart]
    i = _asof(ch, dec_ns)
    tr = structure(mk, chart, k).trend
    return np.where(i >= 0, tr[np.maximum(i, 0)], 0)


def daily_features(mk):
    def build():
        D = mk.charts["daily"]
        rng = D.h - D.l
        choppy = np.abs(D.c - D.o) < 0.3 * np.where(rng > 0, rng, np.inf)
        up = np.r_[False, D.c[1:] > D.c[:-1]]
        dn = np.r_[False, D.c[1:] < D.c[:-1]]
        def run(x, n):
            cs = np.r_[0, np.cumsum(x)]
            out = np.zeros(len(x), bool)
            out[n - 1:] = (cs[n:] - cs[:-n]) == n
            return out
        return dict(choppy=choppy, up3=run(up, 3), dn3=run(dn, 3), up5=run(up, 5), dn5=run(dn, 5))
    return _memo((id(mk), "dailyf"), build)


SESSION_WINDOWS = {"all": None, "london_ny": (180, 960), "ny": (480, 960), "ny_open": (570, 660)}


def orders(mk, version: dict) -> tuple[dict, dict]:
    """Version -> engine orders (+ engine extras)."""
    v = version
    setup, sc, tc = v["setup"], v["setup_chart"], v["trigger_chart"]
    cd = candidates(mk, setup, sc, tc, v)
    S, Tg = mk.charts[sc], mk.charts[tc]
    k = v["swing_strength"]
    if not len(cd):
        return None, None
    side = cd.side
    t = cd.t
    keep = mk.tradable[mk.sess[t]]
    if v["direction"] == "long":
        keep &= side == 1
    elif v["direction"] == "short":
        keep &= side == -1
    limit = cd.resting | (v["entry"] == "limit_at_level")
    entry_ref = np.where(limit, cd.level, mk.c[t])
    sb = np.maximum(cd.sbar, 0)
    atr = S.atr[sb]
    keep &= np.isfinite(atr)
    buf = v["stop_buffer_atr"] * np.nan_to_num(atr)
    st = structure(mk, sc, k)
    ref = {"beyond_level": cd.far, "touch_wick": cd.wick,
           "last_swing": np.where(side == 1, st.last_sl[sb], st.last_sh[sb]),
           "gap_middle": cd.gapmid}[v["stop_ref"]]
    stop = ref - side * buf
    risk = side * (entry_ref - stop)
    keep &= np.isfinite(risk) & (risk >= mk.tick)
    tgt = v["target"]
    if tgt == "next_swing":
        nxt = np.where(side == 1, st.last_sh[sb], st.last_sl[sb])
        target = nxt
        keep &= np.isfinite(nxt) & (side * (nxt - entry_ref) >= risk)
    else:
        target = entry_ref + side * float(tgt[:-1]) * risk
    dec_ns = mk.ts_ns[t] + 60_000_000_000
    # ---- filters
    tf = v["trend_filter"]
    if tf != "off":
        chart = {"setup_chart": sc, "one_up": higher(sc), "daily": "daily"}[tf]
        keep &= _trend_at(mk, chart, k, dec_ns) == side
    if v["skip_choppy"] == "on" or v["skip_run"] != "off":
        D = mk.charts["daily"]
        di = _asof(D, dec_ns)
        f = daily_features(mk)
        ok = di >= 0
        dd = np.maximum(di, 0)
        if v["skip_choppy"] == "on":
            keep &= ~(ok & f["choppy"][dd])
        if v["skip_run"] != "off":
            nn = v["skip_run"][0]
            keep &= ~(ok & (((side == 1) & f[f"up{nn}"][dd]) | ((side == -1) & f[f"dn{nn}"][dd])))
    if v["fresh_breakouts_only"] == "on":
        keep &= cd.fresh
    notional = getattr(mk, "notional", 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        base = np.where(entry_ref > 0, notional / (mk.pv * entry_ref), 0.0) if notional else np.ones(len(t))
    size = base.copy()                   # 1 contract, or a fixed dollar amount of shares (ETFs)
    news = mk.news[mk.sess[t]]
    if v["news"] == "skip":
        keep &= ~news
    elif v["news"] == "half":
        size = np.where(news, 0.5 * base, base)
    w = SESSION_WINDOWS[v["session"]]
    if w:
        m = (mk.et_min[t] + 1) % 1440
        keep &= (m >= w[0]) & (m <= w[1])
    if v["pullback_depth"] != "any":
        leg = st.last_sh[sb] - st.last_sl[sb]
        depth = np.where(side == 1, st.last_sh[sb] - entry_ref, entry_ref - st.last_sl[sb]) / np.where(leg > 0, leg, np.nan)
        keep &= (depth < 0.5) if v["pullback_depth"] == "shallow" else ((depth >= 0.5) & (depth <= 1.0))
    if v["gap_confluence"] == "on":
        g = _memo((id(mk), "fvg", sc, 0.0, 96),
                  lambda: det.fair_value_gaps(S.h, S.l, S.atr, 0.0, 96))
        conf = np.zeros(len(t), bool)
        for i in np.flatnonzero(keep):
            a = np.searchsorted(g.born, sb[i] - 96)
            b = np.searchsorted(g.born, sb[i], side="right")
            if a < b:
                sel = slice(a, b)
                conf[i] = ((g.side[sel] == side[i]) & (g.lo[sel] <= entry_ref[i]) & (g.hi[sel] >= entry_ref[i])).any()
        keep &= conf
    # ---- time exit
    te = v["time_exit"]
    if te == "flat_1600":
        time_exit = mk.flat1600_idx[mk.sess[t]]
        keep &= t < time_exit
    else:
        nbar = int(te.split("_")[1])
        time_exit = Tg.last_1m[np.minimum(cd.tj + nbar, len(Tg.c) - 1)]
    lim_end = np.where(cd.resting, cd.lim_end,
                       Tg.last_1m[np.minimum(cd.tj + LIMIT_WINDOW_TRIGGER_BARS, len(Tg.c) - 1)])
    o = dict(t=t, side=side, limit=limit, px=entry_ref, lim_end=lim_end, stop=stop, target=target,
             close_stop=np.full(len(t), v["stop_mode"] == "close_based"),
             use_struct=np.full(len(t), v["management"] == "exit_on_choch"),
             time_exit=time_exit, size=size)
    o = {kk: np.asarray(vv)[keep] for kk, vv in o.items()}
    extra = {}
    if v["stop_mode"] == "close_based":
        mark = np.zeros(mk.n, bool)
        mark[Tg.last_1m[Tg.last_1m >= 0]] = True
        extra["trig_close"] = _memo((id(mk), "tmark", tc), lambda: mark)
    if v["management"] == "exit_on_choch":
        def ch_exits():
            s2 = structure(mk, tc, k)
            m = s2.ev_kind == det.CHOCH
            up = np.sort(Tg.last_1m[s2.ev_idx[m & (s2.ev_dir == 1)]])
            dn = np.sort(Tg.last_1m[s2.ev_idx[m & (s2.ev_dir == -1)]])
            return up, dn
        extra["struct_up"], extra["struct_dn"] = _memo((id(mk), "chx", tc, k), ch_exits)
    return o, extra


def signals(mk, version) -> int:
    o, _ = orders(mk, version)
    return 0 if o is None else len(o["t"])


def run_version(mk, version) -> pd.DataFrame:
    o, extra = orders(mk, version)
    if o is None or not len(o["t"]):
        return engine.costs(mk, pd.DataFrame({c: pd.Series(dtype=float) for c in
                                              ["entry_idx", "exit_idx", "entry_px", "exit_px", "side", "size", "stop"]})
                            .astype({"entry_idx": np.int64, "exit_idx": np.int64}))
    return engine.run(mk, o, **extra)
