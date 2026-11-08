"""Price-action detectors. Every output carries the bar index at which it
became known (`known`), and nothing uses a bar after that index, so the
results on data cut at any bar equal the full run up to the cut
(tests/test_lookahead.py proves it).

All inputs are one chart's arrays: o, h, l, c, atr (atr[i] uses bars < i).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit

UP, DOWN = 1, -1
BOS, CHOCH, RANGE_BREAK = 1, 2, 0


# --------------------------------------------------------------------------- swings
@njit(cache=True)
def _swings(h, l, k):
    n = len(h)
    idx = np.empty(2 * n, np.int64); conf = np.empty(2 * n, np.int64)
    price = np.empty(2 * n, np.float64); typ = np.empty(2 * n, np.int64)
    m = 0
    for i in range(k, n - k):
        hi = True
        lo = True
        for j in range(1, k + 1):
            if not (h[i] > h[i - j]) or not (h[i] >= h[i + j]):
                hi = False
            if not (l[i] < l[i - j]) or not (l[i] <= l[i + j]):
                lo = False
        if hi:
            idx[m] = i; conf[m] = i + k; price[m] = h[i]; typ[m] = 1; m += 1
        if lo:
            idx[m] = i; conf[m] = i + k; price[m] = l[i]; typ[m] = -1; m += 1
    return idx[:m], conf[:m], price[:m], typ[:m]


@dataclass
class Swings:
    idx: np.ndarray     # bar of the swing
    known: np.ndarray   # bar at whose close it is confirmed (idx + strength)
    price: np.ndarray
    typ: np.ndarray     # +1 high, -1 low


def swings(h, l, k: int) -> Swings:
    i, c, p, t = _swings(np.asarray(h, float), np.asarray(l, float), k)
    order = np.argsort(c, kind="stable")
    return Swings(i[order], c[order], p[order], t[order])


# --------------------------------------------------------------------------- trend and structure
@njit(cache=True)
def _structure(c, s_known, s_price, s_typ):
    n = len(c)
    trend = np.zeros(n, np.int64)
    last_sh = np.full(n, np.nan)
    last_sl = np.full(n, np.nan)
    ev_idx = np.empty(2 * n, np.int64); ev_dir = np.empty(2 * n, np.int64)
    ev_kind = np.empty(2 * n, np.int64); ev_level = np.empty(2 * n, np.float64)
    m = 0
    sh1 = np.nan; sh2 = np.nan; sl1 = np.nan; sl2 = np.nan
    cur_sh = np.nan; cur_sl = np.nan
    sh_broken = True; sl_broken = True
    p = 0
    tr = 0
    for i in range(n):
        prev_tr = tr
        while p < len(s_known) and s_known[p] <= i:
            if s_typ[p] == 1:
                sh1 = sh2; sh2 = s_price[p]; cur_sh = s_price[p]; sh_broken = False
            else:
                sl1 = sl2; sl2 = s_price[p]; cur_sl = s_price[p]; sl_broken = False
            p += 1
        # break of the last confirmed swing by this bar's close
        if not sh_broken and c[i] > cur_sh:
            sh_broken = True
            ev_idx[m] = i; ev_dir[m] = 1; ev_level[m] = cur_sh
            ev_kind[m] = 1 if prev_tr == 1 else (2 if prev_tr == -1 else 0)
            m += 1
        if not sl_broken and c[i] < cur_sl:
            sl_broken = True
            ev_idx[m] = i; ev_dir[m] = -1; ev_level[m] = cur_sl
            ev_kind[m] = 1 if prev_tr == -1 else (2 if prev_tr == 1 else 0)
            m += 1
        if sh2 > sh1 and sl2 > sl1:
            tr = 1
        elif sh2 < sh1 and sl2 < sl1:
            tr = -1
        else:
            tr = 0
        trend[i] = tr
        last_sh[i] = cur_sh
        last_sl[i] = cur_sl
    return trend, last_sh, last_sl, ev_idx[:m], ev_dir[:m], ev_kind[:m], ev_level[:m]


@dataclass
class Structure:
    trend: np.ndarray       # trend as of each bar's close (+1/-1/0)
    last_sh: np.ndarray     # last confirmed swing-high price as of each close
    last_sl: np.ndarray
    ev_idx: np.ndarray      # break bar (known at its close)
    ev_dir: np.ndarray
    ev_kind: np.ndarray     # 1 BOS (with trend), 2 CHoCH (against), 0 break out of a range
    ev_level: np.ndarray


def structure(c, sw: Swings) -> Structure:
    return Structure(*_structure(np.asarray(c, float), sw.known, sw.price, sw.typ))


# --------------------------------------------------------------------------- levels
@dataclass
class Levels:
    born: np.ndarray        # bar at which the cluster reached min touches
    end: np.ndarray         # last bar the level is live (last swing + life)
    price: np.ndarray
    lo: np.ndarray          # band (equal to price for a line)
    hi: np.ndarray
    n_swings: np.ndarray    # swings in the cluster when it was born


def levels(sw: Swings, atr, tol: float, min_touches: int, shape: str = "line",
           life: int = 500) -> Levels:
    """Cluster confirmed swings (highs and lows together) within tol*ATR.
    A cluster becomes a level when its min_touches-th swing is confirmed; it is
    frozen then (later swings start a new cluster) so its price never moves after birth."""
    n_bars = len(atr)
    open_cl: list[list] = []   # [sum, n, lo, hi, last_known]
    out = []
    for k, p in zip(sw.known, sw.price):
        a = atr[min(k, n_bars - 1)]
        if not np.isfinite(a):
            continue
        best, bd = -1, np.inf
        for j, cl in enumerate(open_cl):
            if k - cl[4] > life:
                continue
            d = abs(p - cl[0] / cl[1])
            if d <= tol * a and d < bd:
                best, bd = j, d
        if best < 0:
            open_cl.append([p, 1, p, p, k])
            best = len(open_cl) - 1
        else:
            cl = open_cl[best]
            cl[0] += p; cl[1] += 1; cl[2] = min(cl[2], p); cl[3] = max(cl[3], p); cl[4] = k
        cl = open_cl[best]
        if cl[1] >= min_touches:
            m = cl[0] / cl[1]
            lo, hi = (cl[2], cl[3]) if shape == "box" else (m, m)
            out.append((k, min(k + life, n_bars - 1), m, lo, hi, cl[1]))
            open_cl.pop(best)
        open_cl = [c for c in open_cl if k - c[4] <= life]
    if not out:
        z = np.zeros(0)
        return Levels(z.astype(np.int64), z.astype(np.int64), z, z, z, z.astype(np.int64))
    a = np.array(out)
    return Levels(a[:, 0].astype(np.int64), a[:, 1].astype(np.int64), a[:, 2], a[:, 3], a[:, 4],
                  a[:, 5].astype(np.int64))


# --------------------------------------------------------------------------- trend lines
@dataclass
class TrendLines:
    born: np.ndarray        # bar the line was confirmed
    end: np.ndarray
    x0: np.ndarray          # anchor bar
    y0: np.ndarray
    slope: np.ndarray       # price per bar
    side: np.ndarray        # +1 rising support (under price), -1 falling resistance
    touches: np.ndarray


def trend_lines(sw: Swings, c, atr, min_touches: int, tol: float, life: int = 300,
                lookback: int = 6) -> TrendLines:
    """Lines through swing lows (rising support) or swing highs (falling
    resistance). A line through anchor swing A and latest swing B counts every
    swing of the same type between them within tol*ATR as a touch, and is
    rejected if any close between A and B sits more than tol*ATR beyond it."""
    out = []
    n = len(c)
    for typ, side in ((-1, 1), (1, -1)):
        m = sw.typ == typ
        si, sk, sp = sw.idx[m], sw.known[m], sw.price[m]
        for b in range(1, len(si)):
            a_tol = atr[min(sk[b], n - 1)]
            if not np.isfinite(a_tol):
                continue
            best = None
            for a in range(max(0, b - lookback), b):
                if si[b] == si[a]:
                    continue
                slope = (sp[b] - sp[a]) / (si[b] - si[a])
                if side * slope <= 0:
                    continue
                line = lambda x: sp[a] + slope * (x - si[a])  # noqa: E731
                seg = np.arange(si[a], si[b] + 1)
                if (side * (line(seg) - c[seg]) > tol * a_tol).any():
                    continue
                between = range(a + 1, b)
                t = 2 + sum(1 for j in between if abs(sp[j] - line(si[j])) <= tol * a_tol)
                if t >= min_touches and (best is None or t > best[3]):
                    best = (si[a], sp[a], slope, t)
            if best:
                out.append((sk[b], min(sk[b] + life, n - 1), best[0], best[1], best[2], side, best[3]))
    if not out:
        z = np.zeros(0)
        return TrendLines(*(z.astype(np.int64),) * 3, z, z, z.astype(np.int64), z.astype(np.int64))
    a = np.array(sorted(out))
    return TrendLines(a[:, 0].astype(np.int64), a[:, 1].astype(np.int64), a[:, 2].astype(np.int64),
                      a[:, 3], a[:, 4], a[:, 5].astype(np.int64), a[:, 6].astype(np.int64))


# --------------------------------------------------------------------------- supply / demand zones
@dataclass
class Zones:
    born: np.ndarray        # last candle of the run
    end: np.ndarray
    lo: np.ndarray          # base candle range
    hi: np.ndarray
    side: np.ndarray        # +1 demand (run up), -1 supply (run down)


def zones(o, h, l, c, atr, run: int, span: float, life: int = 500) -> Zones:
    n = len(c)
    up = (c > o).astype(np.int64)
    dn = (c < o).astype(np.int64)
    out = []
    for side, d in ((1, up), (-1, dn)):
        cs = np.r_[0, np.cumsum(d)]
        for i in range(run, n):
            s = i - run + 1
            if cs[i + 1] - cs[s] != run or d[s - 1] == 1:
                continue
            a = atr[s]
            if not np.isfinite(a) or side * (c[i] - o[s]) < span * a:
                continue
            base = s - 1
            out.append((i, min(i + life, n - 1), l[base], h[base], side))
    if not out:
        z = np.zeros(0)
        return Zones(z.astype(np.int64), z.astype(np.int64), z, z, z.astype(np.int64))
    a = np.array(sorted(out))
    return Zones(a[:, 0].astype(np.int64), a[:, 1].astype(np.int64), a[:, 2], a[:, 3], a[:, 4].astype(np.int64))


# --------------------------------------------------------------------------- fair value gaps
@dataclass
class Gaps:
    born: np.ndarray        # third candle
    end: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    side: np.ndarray        # +1 bullish gap (support), -1 bearish
    mid_lo: np.ndarray      # middle candle low / high (stop reference)
    mid_hi: np.ndarray


def fair_value_gaps(h, l, atr, min_gap: float, life: int = 96) -> Gaps:
    h, l, atr = map(np.asarray, (h, l, atr))
    n = len(h)
    i = np.arange(2, n)
    a = atr[i]
    ok = np.isfinite(a)
    a = np.where(ok, a, 0.0)
    bull = ok & (l[i] > h[i - 2]) & (l[i] - h[i - 2] >= min_gap * a)
    bear = ok & (h[i] < l[i - 2]) & (l[i - 2] - h[i] >= min_gap * a)
    b, s = i[bull], i[bear]
    born = np.r_[b, s]
    lo = np.r_[h[b - 2], h[s]]
    hi = np.r_[l[b], l[s - 2]]
    side = np.r_[np.ones(len(b), np.int64), -np.ones(len(s), np.int64)]
    order = np.argsort(born, kind="stable")
    born = born[order]
    return Gaps(born, np.minimum(born + life, n - 1), lo[order], hi[order], side[order],
                l[born - 1], h[born - 1])
