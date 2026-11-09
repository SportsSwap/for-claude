"""The trade engine. Every fill and exit is checked on 1-minute bars.

Orders (one row per candidate, in time order):
  t        1m index at whose close the order is decided
  side     +1 long / -1 short
  limit    True: a limit at `px`; False: market at the close of bar t
  px       limit price (ignored for market orders)
  lim_end  last 1m bar a limit may fill on (window / cancel)
  stop     stop price
  target   target price (nan = none)
  close_stop  True: exit when a trigger bar closes beyond the stop
  struct_exit 1m index of a structure exit (CHoCH) to apply, or -1
              (passed as a sorted array of candidate exit bars per side)
  time_exit   1m index whose close is the time exit (-1 none)
  size     1.0, or 0.5 for half size

Rules (prompt 2):
  - one position at a time; a pending limit counts as busy
  - market entry: close of bar t + 1 tick against
  - limit fills only when a bar trades 1 tick through it, at the limit price
    (never better on a gap); targets fill the same way
  - hard stop: 1 tick worse than the stop, or than the open on a gap through
  - close stop: at the first trigger-bar close beyond the stop, 1 tick against
  - stop and target in one bar: the stop
  - structure exit: at the 1m close, 1 tick against; time and roll exits at the
    close, no slippage
  - no entry in the roll blackout; a roll forces an exit at the last bar before it
  - $4 commission per round trip (scaled by size)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

from .market import COMMISSION_RT

R_STOP, R_TARGET, R_CLOSE_STOP, R_STRUCT, R_TIME, R_ROLL, R_END = 1, 2, 3, 4, 5, 6, 7
REASONS = {1: "stop", 2: "target", 3: "close_stop", 4: "structure", 5: "time", 6: "roll", 7: "end_of_data"}


@njit(cache=True)
def _run(o, h, l, c, tick, no_entry, roll_exit, trig_close,
         t, side, limit, px, lim_end, stop, target, close_stop,
         struct_up, struct_dn, use_struct, time_exit, size, independent):
    n = len(c)
    m = len(t)
    e_idx = np.full(m, -1, np.int64)
    e_px = np.full(m, np.nan)
    x_idx = np.full(m, -1, np.int64)
    x_px = np.full(m, np.nan)
    reason = np.zeros(m, np.int64)
    busy_until = -1
    for k in range(m):
        tk = t[k]
        if (tk <= busy_until and not independent) or tk >= n - 1:
            continue
        s = side[k]
        # ---- entry
        if not limit[k]:
            if no_entry[tk]:
                continue
            ei = tk
            ep = c[tk] + s * tick
        else:
            ei = -1
            end = min(lim_end[k], n - 1)
            if time_exit[k] >= 0:
                end = min(end, time_exit[k])
            done = end
            for j in range(tk + 1, end + 1):
                fills = (s == 1 and l[j] <= px[k] - tick) or (s == -1 and h[j] >= px[k] + tick)
                stopped = (s == 1 and l[j] <= stop[k]) or (s == -1 and h[j] >= stop[k])
                if fills:
                    if no_entry[j]:
                        done = j
                        break
                    ei = j  # a fill and the stop in one bar: filled, then stopped below
                    break
                if stopped:  # the stop traded before any fill: cancel
                    done = j
                    break
            if ei < 0:
                busy_until = max(busy_until, done if done > tk else tk)
                continue
            ep = px[k]
        e_idx[k] = ei
        e_px[k] = ep
        # ---- exits
        r = np.searchsorted(roll_exit, ei)
        rx = roll_exit[r] if r < len(roll_exit) else -1
        sx = -1
        if use_struct[k]:
            arr = struct_dn if s == 1 else struct_up
            q = np.searchsorted(arr, ei + 1)
            sx = arr[q] if q < len(arr) else -1
        st = stop[k]
        tg = target[k]
        xi = -1
        xp = np.nan
        rs = 0
        # the fill bar of a limit: only the stop can hit after the fill
        if limit[k]:
            j = ei
            if not close_stop[k] and ((s == 1 and l[j] <= st) or (s == -1 and h[j] >= st)):
                xi, xp, rs = j, st - s * tick, R_STOP
        j = ei + 1
        while xi < 0 and j < n:
            if not close_stop[k]:
                gap = (s == 1 and o[j] <= st) or (s == -1 and o[j] >= st)
                hit = (s == 1 and l[j] <= st) or (s == -1 and h[j] >= st)
                if gap:
                    xi, xp, rs = j, o[j] - s * tick, R_STOP
                    break
                if hit:
                    xi, xp, rs = j, st - s * tick, R_STOP
                    break
            if tg == tg:  # not nan
                if (s == 1 and h[j] >= tg + tick) or (s == -1 and l[j] <= tg - tick):
                    xi, xp, rs = j, tg, R_TARGET
                    break
            if close_stop[k] and trig_close[j] and ((s == 1 and c[j] < st) or (s == -1 and c[j] > st)):
                xi, xp, rs = j, c[j] - s * tick, R_CLOSE_STOP
                break
            if j == sx:
                xi, xp, rs = j, c[j] - s * tick, R_STRUCT
                break
            if j == time_exit[k]:
                xi, xp, rs = j, c[j], R_TIME
                break
            if j == rx:
                xi, xp, rs = j, c[j], R_ROLL
                break
            j += 1
        if xi < 0:
            xi, xp, rs = n - 1, c[n - 1], R_END
        x_idx[k] = xi
        x_px[k] = xp
        reason[k] = rs
        busy_until = xi
    return e_idx, e_px, x_idx, x_px, reason


def run(mk, orders: dict, trig_close=None, struct_up=None, struct_dn=None,
        independent: bool = False) -> pd.DataFrame:
    """orders: dict of equal-length arrays (see module doc). Returns one row per trade.
    independent=True drops the one-position rule (random-entry and twin studies only)."""
    m = len(orders["t"])
    z = np.zeros(0, np.int64)
    order = np.argsort(orders["t"], kind="stable")
    g = {k: np.asarray(v)[order] for k, v in orders.items()}
    defaults = {"limit": np.zeros(m, bool), "px": np.full(m, np.nan), "lim_end": np.full(m, -1, np.int64),
                "target": np.full(m, np.nan), "close_stop": np.zeros(m, bool),
                "use_struct": np.zeros(m, bool), "time_exit": np.full(m, -1, np.int64),
                "size": np.ones(m)}
    for k, v in defaults.items():
        g.setdefault(k, v)
    tc = trig_close if trig_close is not None else np.ones(mk.n, bool)
    e, ep, x, xp, rs = _run(mk.o, mk.h, mk.l, mk.c, mk.tick, mk.no_entry, mk.roll_exit_idx, tc,
                            g["t"].astype(np.int64), g["side"].astype(np.int64), g["limit"].astype(bool),
                            g["px"].astype(float), g["lim_end"].astype(np.int64), g["stop"].astype(float),
                            g["target"].astype(float), g["close_stop"].astype(bool),
                            struct_up if struct_up is not None else z, struct_dn if struct_dn is not None else z,
                            g["use_struct"].astype(bool), g["time_exit"].astype(np.int64), g["size"].astype(float),
                            independent)
    ok = e >= 0
    tr = pd.DataFrame({"decided": g["t"][ok], "entry_idx": e[ok], "entry_px": ep[ok], "exit_idx": x[ok],
                       "exit_px": xp[ok], "reason": [REASONS[r] for r in rs[ok]],
                       "side": g["side"][ok], "size": g["size"][ok], "stop": g["stop"][ok],
                       "target": g["target"][ok]})
    for k in ("tag",):
        if k in g:
            tr[k] = g[k][ok]
    return costs(mk, tr)


def costs(mk, tr: pd.DataFrame) -> pd.DataFrame:
    tr["points"] = (tr["exit_px"] - tr["entry_px"]) * tr["side"]
    tr["commission"] = getattr(mk, "commission_rt", COMMISSION_RT) * tr["size"]
    tr["dollars"] = tr["points"] * mk.pv * tr["size"] - tr["commission"]
    risk = (tr["entry_px"] - tr["stop"]).abs() * mk.pv * tr["size"]
    tr["R"] = tr["dollars"] / risk.where(risk > 0)
    tr["entry_time"] = pd.to_datetime(mk.ts_ns[tr["entry_idx"]], utc=True)
    tr["exit_time"] = pd.to_datetime(mk.ts_ns[tr["exit_idx"]], utc=True) + pd.Timedelta(minutes=1)
    tr["exit_session"] = mk.sessions[mk.sess[tr["exit_idx"]]]
    tr["entry_session"] = mk.sessions[mk.sess[tr["entry_idx"]]]
    return tr


def daily_pnl(mk, tr: pd.DataFrame, sessions_mask=None) -> pd.Series:
    """P&L per session over every tradable session, zero where nothing exited."""
    mask = mk.tradable if sessions_mask is None else sessions_mask
    days = pd.Index(mk.sessions[mask], name="session")
    s = tr.groupby("exit_session")["dollars"].sum() if len(tr) else pd.Series(dtype=float)
    return s.reindex(days, fill_value=0.0).astype(float)


def sharpe(daily: pd.Series) -> float:
    sd = daily.std(ddof=1)
    return float(daily.mean() / sd * np.sqrt(252)) if sd and sd > 0 else 0.0


def metrics(mk, tr: pd.DataFrame, daily: pd.Series | None = None) -> dict:
    d = daily_pnl(mk, tr) if daily is None else daily
    n = len(tr)
    return {"trades": n, "net": float(tr["dollars"].sum()) if n else 0.0,
            "per_trade": float(tr["dollars"].mean()) if n else 0.0,
            "win_rate": float((tr["dollars"] > 0).mean()) if n else 0.0,
            "avg_R": float(tr["R"].mean()) if n else 0.0,
            "sharpe": sharpe(d), "days": int(len(d))}
