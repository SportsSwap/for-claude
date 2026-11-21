"""D64: the user's QQQ noise-band options rules, tested as written on 2013-2026.

    LAB_UNLOCK=final_test python scripts/noise_band_qqq.py

QQQ is stood in for by the Nasdaq-100 CFD minutes (regular hours). Option prices are
estimated with Black-Scholes (no free options history). Rules and test design are fixed in
decisions.md D64; this file only carries them out.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from lab import final_test as ft  # noqa: E402
from lab import io  # noqa: E402
from lab.config import P, stamp  # noqa: E402
from lab.seed import rng  # noqa: E402
import run_history_test as ht  # noqa: E402

RTH = 390                  # 09:30 .. 15:59 bar opens
OR_END = 15                # bars 09:30 .. 09:44 make the opening range
CHECKS = np.arange(29, 270, 10)   # closes at 10:00, 10:10, ..., 14:00
EXIT_BAR = 344             # the bar that closes at 15:45
QQQ_RATIO = 41.0           # Nasdaq-100 / QQQ, roughly
PERIODS = {"2013-Sep 2021": (dt.date(2013, 1, 2), dt.date(2021, 9, 24)),
           "2022-Jul 2024": (dt.date(2022, 1, 3), dt.date(2024, 7, 31)),
           "Aug 2024-Nov 2026": (dt.date(2024, 8, 1), dt.date(2026, 11, 6))}

RULES = dict(band_mult=1.25, band_days=20, or_offset_atr=0.3, vwap=True, trail_trigger_atr=4.0,
             giveback=0.5, stop_atr=10.0, atr_kind="daily5", dte_days=1)


# =========================================================================== data
def load_minutes() -> pd.DataFrame:
    """All Nasdaq-100 CFD minutes, Dec 2012 .. Nov 2026, one frame (the unlock is logged)."""
    old, _ = ht.clean_bars(ROOT / "vendor_input" / "dukascopy_2013_2021" / "NQ_1m_backadjusted.parquet")
    new = io.read_table(P.clean() / "NQ_1m.parquet")
    loaded = ft.load_frames("final")
    fin = loaded["frames"]["NQ"][0]
    cols = ["ts_event", "open", "high", "low", "close", "volume"]
    m = pd.concat([old[cols], new[cols], fin[cols]], ignore_index=True)
    m["ts_event"] = pd.to_datetime(m["ts_event"], utc=True)
    return m.drop_duplicates("ts_event").sort_values("ts_event").reset_index(drop=True)


def rth_grid(m: pd.DataFrame):
    """Days x 390 minute arrays of regular-hours bars, forward-filled inside the day."""
    et = m["ts_event"].dt.tz_convert("America/New_York")
    mins = (et.dt.hour * 60 + et.dt.minute).to_numpy() - (9 * 60 + 30)
    keep = (mins >= 0) & (mins < RTH)
    d = m.loc[keep].copy()
    d["day"] = et[keep].dt.date.to_numpy()
    d["k"] = mins[keep]
    counts = d.groupby("day").size()
    first = d.groupby("day")["k"].min()
    has_exit = d[d["k"] == EXIT_BAR].groupby("day").size()
    ok = counts.index[(counts >= 370) & (first == 0)]
    ok = [x for x in ok if x in has_exit.index]
    d = d[d["day"].isin(set(ok))]
    days = np.array(sorted(ok))
    di = {x: i for i, x in enumerate(days)}
    shape = (len(days), RTH)
    A = {c: np.full(shape, np.nan) for c in ("open", "high", "low", "close", "volume")}
    r, c = d["day"].map(di).to_numpy(), d["k"].to_numpy()
    for col in A:
        A[col][r, c] = d[col].to_numpy(float)
    # forward-fill gaps inside the day; a missing bar is flat at the last close
    close = pd.DataFrame(A["close"]).ffill(axis=1).to_numpy()
    for col in ("open", "high", "low"):
        A[col] = np.where(np.isnan(A[col]), close, A[col])
    A["close"] = close
    A["volume"] = np.nan_to_num(A["volume"])
    return days, A, counts


# =========================================================================== features (prior days only)
def features(days, A):
    O, H, L, C, V = (A[k] for k in ("open", "high", "low", "close", "volume"))
    n = len(days)
    day_open = O[:, 0]
    prev_close = np.r_[np.nan, C[:-1, -1]]
    # noise band: mean over the previous 20 days of |close_m / open - 1|
    dist = np.abs(C / day_open[:, None] - 1)
    cs = np.vstack([np.zeros(RTH), np.cumsum(dist, axis=0)])
    sigma = np.full((n, RTH), np.nan)
    for k in (20,):
        idx = np.arange(n)
        okk = idx >= k
        sigma[okk] = (cs[idx[okk]] - cs[idx[okk] - k]) / k
    # daily ATR(5): simple mean of the previous 5 daily true ranges (regular hours)
    dh, dl, dc = H.max(axis=1), L.min(axis=1), C[:, -1]
    tr = np.maximum(dh, np.r_[np.nan, dc[:-1]]) - np.minimum(dl, np.r_[np.nan, dc[:-1]])
    tr[0] = dh[0] - dl[0]
    atr_daily = pd.Series(tr).rolling(5).mean().shift(1).to_numpy()
    # 1-minute ATR over the previous 5 sessions
    pc = np.concatenate([np.r_[np.nan], C.ravel()[:-1]]).reshape(n, RTH)
    tr1 = np.maximum(H, pc) - np.minimum(L, pc)
    tr1[:, 0] = H[:, 0] - L[:, 0]
    atr_min = pd.Series(np.nanmean(tr1, axis=1)).rolling(5).mean().shift(1).to_numpy()
    # VWAP from the open, typical price, tick volume
    tp = (H + L + C) / 3
    cv = np.cumsum(V, axis=1)
    vwap = np.where(cv > 0, np.cumsum(tp * V, axis=1) / np.where(cv > 0, cv, 1), np.cumsum(tp, axis=1) / np.arange(1, RTH + 1))
    orh, orl = H[:, :OR_END].max(axis=1), L[:, :OR_END].min(axis=1)
    # implied-volatility proxy: 1.1 x realised volatility of the previous 20 daily closes
    lr = np.r_[np.nan, np.diff(np.log(dc))]
    rv = pd.Series(lr).rolling(20).std().shift(1).to_numpy() * math.sqrt(252)
    iv = np.maximum(0.10, 1.1 * rv)
    return dict(day_open=day_open, prev_close=prev_close, sigma=sigma, atr_daily=atr_daily, atr_min=atr_min,
                vwap=vwap, orh=orh, orl=orl, iv=iv, close_d=dc)


# =========================================================================== signals and exits
def signals(A, F, p):
    """First check of each day that fires: (day index, check bar, side +1/-1)."""
    C = A["close"]
    atr = F["atr_daily"] if p["atr_kind"] == "daily5" else F["atr_min"]
    up_base = np.fmax(F["day_open"], F["prev_close"])
    dn_base = np.fmin(F["day_open"], F["prev_close"])
    s = F["sigma"][:, CHECKS] * p["band_mult"]
    c = C[:, CHECKS]
    ub, lb = up_base[:, None] * (1 + s), dn_base[:, None] * (1 - s)
    long_ = (c > F["orh"][:, None] + p["or_offset_atr"] * atr[:, None]) & (c > ub)
    short = (c < F["orl"][:, None] - p["or_offset_atr"] * atr[:, None]) & (c < lb)
    if p["vwap"]:
        long_ &= c > F["vwap"][:, CHECKS]
        short &= c < F["vwap"][:, CHECKS]
    valid = np.isfinite(atr) & np.isfinite(F["sigma"][:, 0]) & np.isfinite(F["prev_close"]) & np.isfinite(F["iv"])
    fire = (long_ | short) & valid[:, None]
    has = fire.any(axis=1)
    first = np.argmax(fire, axis=1)
    d = np.flatnonzero(has)
    j = first[d]
    side = np.where(long_[d, j], 1, -1)
    return d, CHECKS[j], side, atr


def exits(C, d, e, side, atr_d, p):
    """Exit bar and reason for each trade, judged on 1-minute closes."""
    n = len(d)
    xb, why = np.full(n, EXIT_BAR), np.array(["15:45"] * n, dtype=object)
    for t in range(n):
        entry = C[d[t], e[t]]
        a = atr_d[t]
        path = side[t] * (C[d[t], e[t] + 1: EXIT_BAR + 1] - entry)
        best = np.maximum.accumulate(path)
        trail = (best >= p["trail_trigger_atr"] * a) & (path <= (1 - p["giveback"]) * best)
        stop = path <= -p["stop_atr"] * a
        hit = trail | stop
        if hit.any():
            k = int(np.argmax(hit))
            xb[t] = e[t] + 1 + k
            why[t] = "stop" if stop[k] else "trail"
    return xb, why


def bs(S, K, T, sig, call):
    T = np.maximum(T, 1e-6)
    d1 = (np.log(S / K) + 0.5 * sig ** 2 * T) / (sig * np.sqrt(T))
    d2 = d1 - sig * np.sqrt(T)
    return np.where(call, S * norm.cdf(d1) - K * norm.cdf(d2), K * norm.cdf(-d2) - S * norm.cdf(-d1))


def option_pnl(S0, S1, e, x, side, iv, dte):
    """Estimated $ result for one contract, and return on the premium paid."""
    q0, q1 = S0 / QQQ_RATIO, S1 / QQQ_RATIO
    K = np.round(q0)
    T0 = ((RTH - (e + 1)) + RTH * dte) / (RTH * 252)
    T1 = ((RTH - (x + 1)) + RTH * dte) / (RTH * 252)
    call = side == 1
    buy = bs(q0, K, T0, iv, call) + 0.01
    sell = np.maximum(bs(q1, K, T1, iv, call) - 0.01, 0.0)
    dollars = (sell - buy) * 100 - 2 * 0.65
    return dollars, (sell - buy) / buy, buy


def run(days, A, F, p):
    d, e, side, atr = signals(A, F, p)
    a = atr[d]
    xb, why = exits(A["close"], d, e, side, a, p)
    C = A["close"]
    S0, S1 = C[d, e], C[d, xb]
    move = side * (S1 / S0 - 1)
    dollars, ret, prem = option_pnl(S0, S1, e, xb, side, F["iv"][d], p["dte_days"])
    hhmm = lambda b: f"{(9 * 60 + 31 + b) // 60:02d}:{(9 * 60 + 31 + b) % 60:02d}"  # noqa: E731  (bar close time)
    return pd.DataFrame({"day": days[d], "signal_time": [hhmm(b) for b in e], "side": np.where(side == 1, "call", "put"),
                         "qqq_entry": np.round(S0 / QQQ_RATIO, 2), "qqq_exit": np.round(S1 / QQQ_RATIO, 2),
                         "exit_time": [hhmm(b) for b in xb], "exit_reason": why, "atr_pts": a,
                         "qqq_move_pct": move * 100, "move_in_atr": side * (S1 - S0) / a,
                         "iv_used": F["iv"][d], "premium": prem, "option_return_pct": ret * 100, "option_dollars_1c": dollars,
                         "_d": d, "_e": e, "_x": xb, "_side": side})


# =========================================================================== reporting
def period_of(day):
    for k, (a, b) in PERIODS.items():
        if a <= day <= b:
            return k
    return None


def summarize(tr: pd.DataFrame, days) -> pd.DataFrame:
    rows = []
    tr = tr.assign(period=tr["day"].map(period_of), year=tr["day"].map(lambda x: x.year))
    for key in [("period", k) for k in PERIODS] + [("year", y) for y in sorted(tr["year"].unique())]:
        g = tr[tr[key[0]] == key[1]]
        if not len(g):
            continue
        cal = [x for x in days if (period_of(x) == key[1] if key[0] == "period" else x.year == key[1])]
        daily = g.set_index("day")["option_dollars_1c"].reindex(cal, fill_value=0.0)
        eq = daily.cumsum()
        rows.append({"span": str(key[1]), "trading_days": len(cal), "trades": len(g),
                     "calls": int((g["side"] == "call").sum()), "puts": int((g["side"] == "put").sum()),
                     "win_rate": round(float((g["option_dollars_1c"] > 0).mean()), 3),
                     "qqq_move_avg_pct": round(float(g["qqq_move_pct"].mean()), 3),
                     "qqq_move_sum_pct": round(float(g["qqq_move_pct"].sum()), 1),
                     "opt_ret_avg_pct": round(float(g["option_return_pct"].mean()), 1),
                     "opt_ret_median_pct": round(float(g["option_return_pct"].median()), 1),
                     "opt_dollars_1c": round(float(g["option_dollars_1c"].sum())),
                     "opt_sharpe": round(float(daily.mean() / daily.std(ddof=1) * math.sqrt(252)), 2) if daily.std() > 0 else 0.0,
                     "opt_max_drawdown_1c": round(float((eq.cummax().clip(lower=0) - eq).max())),
                     "exits_trail": int((g["exit_reason"] == "trail").sum()), "exits_stop": int((g["exit_reason"] == "stop").sum())})
    return pd.DataFrame(rows)


def nulls(days, A, F, p, tr, n_sets=1000):
    """(1) same trades, random direction; (2) random days/check times/directions, same count."""
    C = A["close"]
    atr = F["atr_daily"] if p["atr_kind"] == "daily5" else F["atr_min"]
    real = float(tr["qqq_move_pct"].sum())
    g = rng("noise_band_null")
    d, e = tr["_d"].to_numpy(), tr["_e"].to_numpy()
    # outcome of each trade in both directions
    out = {}
    for s in (1, -1):
        sd = np.full(len(d), s)
        xb, _ = exits(C, d, e, sd, atr[d], p)
        out[s] = s * (C[d, xb] / C[d, e] - 1) * 100
    flips = g.integers(0, 2, size=(n_sets, len(d))) * 2 - 1
    tot1 = np.where(flips == 1, out[1][None, :], out[-1][None, :]).sum(axis=1)
    # random days and times: a pool of eligible (day, check) pairs
    valid = np.flatnonzero(np.isfinite(atr) & np.isfinite(F["sigma"][:, 0]) & np.isfinite(F["prev_close"]))
    tot2 = np.empty(n_sets)
    for k in range(n_sets):
        dd = g.choice(valid, len(d), replace=False)
        ee = g.choice(CHECKS, len(d))
        ss = g.integers(0, 2, len(d)) * 2 - 1
        xb, _ = exits(C, dd, ee, ss, atr[dd], p)
        tot2[k] = (ss * (C[dd, xb] / C[dd, ee] - 1) * 100).sum()
    return {"real_qqq_move_sum_pct": round(real, 1),
            "random_direction": {"mean": round(float(tot1.mean()), 1), "p95": round(float(np.percentile(tot1, 95)), 1),
                                 "p_value": float((tot1 >= real).mean())},
            "random_days_times_directions": {"mean": round(float(tot2.mean()), 1), "p95": round(float(np.percentile(tot2, 95)), 1),
                                             "p_value": float((tot2 >= real).mean())}}


def main() -> int:
    out = P.results() / "noise_band"
    out.mkdir(parents=True, exist_ok=True)
    m = load_minutes()
    days, A, counts = rth_grid(m)
    F = features(days, A)
    yrs = pd.Series([x.year for x in days])
    print("regular-hours days kept by year:", yrs.value_counts().sort_index().to_dict(), flush=True)
    res = {"rules": RULES, "days_kept_by_year": {int(k): int(v) for k, v in yrs.value_counts().sort_index().items()}}
    for name, over in (("A_daily_atr", {}), ("B_minute_atr", {"atr_kind": "min5"}), ("A_daily_atr_3dte", {"dte_days": 3})):
        p = {**RULES, **over}
        tr = run(days, A, F, p)
        tr = tr[tr["day"].map(period_of).notna()].reset_index(drop=True)
        sm = summarize(tr, [x for x in days if period_of(x)])
        io.write_table(sm, out / f"summary_{name}.csv")
        io.write_table(tr.drop(columns=[c for c in tr.columns if c.startswith("_")]), out / f"trades_{name}.csv")
        r = {"periods": sm[sm["span"].isin(PERIODS)].to_dict(orient="records")}
        if name != "A_daily_atr_3dte":
            r["null"] = nulls(days, A, F, p, tr)
            per = sm.set_index("span")
            r["holds"] = bool(all(per.loc[k, "opt_dollars_1c"] > 0 for k in PERIODS) and r["null"]["random_direction"]["p_value"] < 0.05)
        res[name] = r
        pd.set_option("display.width", 250)
        print(f"\n=== {name}\n{sm.to_string(index=False)}", flush=True)
        if "null" in r:
            print(json.dumps(r["null"]), "holds:", r["holds"], flush=True)
    io.write_json({**res, **stamp()}, out / "summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
