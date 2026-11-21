"""D66: search the noise-band signal (2,304 versions), scored on QQQ itself and on options.

    LAB_UNLOCK=final_test python scripts/noise_band_search.py
"""
from __future__ import annotations

import itertools
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from lab import io  # noqa: E402
from lab.config import P, stamp  # noqa: E402
import noise_band_qqq as nb  # noqa: E402

GRID = {"band_mult": [1.0, 1.25, 1.5], "band_days": [14, 20], "or_offset_atr": [0.0, 0.15, 0.3, 0.5],
        "vwap": [True, False], "interval": [10, 30], "last_check": ["12:00", "14:00"],
        "exit": ["hold", "vwap_cross", "trail_0.5", "trail_1.0"], "stop_atr": [None, 0.5, 1.0]}
KEYS = list(GRID)
PER = list(nb.PERIODS)
SHORT = {PER[0]: "OLD", PER[1]: "NEW", PER[2]: "FIN"}
QQQ_COST = 0.0002            # 0.02% a round trip
INSTR = ["qqq", "opt1", "opt3"]


def sigma_for(A, F, k):
    C, O = A["close"], F["day_open"]
    dist = np.abs(C / O[:, None] - 1)
    cs = np.vstack([np.zeros(nb.RTH), np.cumsum(dist, axis=0)])
    n = len(O)
    s = np.full((n, nb.RTH), np.nan)
    idx = np.arange(k, n)
    s[idx] = (cs[idx] - cs[idx - k]) / k
    return s


def checks(interval, last):
    end = {"12:00": 149, "14:00": 269}[last]
    return np.arange(29, end + 1, interval)


def entries(A, F, sig, v):
    C = A["close"]
    atr = F["atr_daily"]
    ch = checks(v["interval"], v["last_check"])
    s = sig[:, ch] * v["band_mult"]
    c = C[:, ch]
    ub = np.fmax(F["day_open"], F["prev_close"])[:, None] * (1 + s)
    lb = np.fmin(F["day_open"], F["prev_close"])[:, None] * (1 - s)
    lo = (c > F["orh"][:, None] + v["or_offset_atr"] * atr[:, None]) & (c > ub)
    sh = (c < F["orl"][:, None] - v["or_offset_atr"] * atr[:, None]) & (c < lb)
    if v["vwap"]:
        lo &= c > F["vwap"][:, ch]
        sh &= c < F["vwap"][:, ch]
    valid = np.isfinite(atr) & np.isfinite(sig[:, 0]) & np.isfinite(F["prev_close"]) & np.isfinite(F["iv"])
    fire = (lo | sh) & valid[:, None]
    d = np.flatnonzero(fire.any(axis=1))
    j = np.argmax(fire[d], axis=1)
    return d, ch[j], np.where(lo[d, j], 1, -1)


def exits_vec(A, F, d, e, side, v):
    C = A["close"][d][:, : nb.EXIT_BAR + 1]
    W = F["vwap"][d][:, : nb.EXIT_BAR + 1]
    a = F["atr_daily"][d][:, None]
    cols = np.arange(nb.EXIT_BAR + 1)[None, :]
    live = cols > e[:, None]
    path = side[:, None] * (C - C[np.arange(len(d)), e][:, None])
    hit = np.zeros_like(live)
    if v["exit"] == "vwap_cross":
        hit |= live & (side[:, None] * (C - W) < 0)
    elif v["exit"].startswith("trail"):
        trig = float(v["exit"].split("_")[1])
        best = np.maximum.accumulate(np.where(live, path, -np.inf), axis=1)
        hit |= live & (best >= trig * a) & (path <= 0.5 * best)
    if v["stop_atr"] is not None:
        hit |= live & (path <= -v["stop_atr"] * a)
    x = np.where(hit.any(axis=1), np.argmax(hit, axis=1), nb.EXIT_BAR)
    return x


def score(days, A, F, sig, v):
    d, e, side = entries(A, F, sig, v)
    if not len(d):
        return None
    x = exits_vec(A, F, d, e, side, v)
    C = A["close"]
    S0, S1 = C[d, e], C[d, x]
    qqq = side * (S1 / S0 - 1) - QQQ_COST
    o1, _, _ = nb.option_pnl(S0, S1, e, x, side, F["iv"][d], 1)
    o3, _, _ = nb.option_pnl(S0, S1, e, x, side, F["iv"][d], 3)
    return pd.DataFrame({"day": days[d], "qqq": qqq * 100, "opt1": o1, "opt3": o3})


def stats(tr, cal):
    out = {}
    for ins in INSTR:
        daily = tr.set_index("day")[ins].reindex(cal, fill_value=0.0) if len(tr) else pd.Series(0.0, index=cal)
        sd = daily.std(ddof=1)
        eq = daily.cumsum()
        out[ins] = {"trades": int(len(tr)), "sum": float(daily.sum()),
                    "sharpe": float(daily.mean() / sd * math.sqrt(252)) if sd > 0 else 0.0,
                    "max_dd": float((eq.cummax().clip(lower=0) - eq).max()),
                    "win": float((tr[ins] > 0).mean()) if len(tr) else 0.0}
    return out


def main() -> int:
    out = P.results() / "noise_band"
    t0 = time.time()
    m = nb.load_minutes()
    days, A, _ = nb.rth_grid(m)
    F = nb.features(days, A)
    sigmas = {k: sigma_for(A, F, k) for k in GRID["band_days"]}
    cal = {k: [x for x in days if nb.period_of(x) == k] for k in PER}
    print(f"data ready ({time.time() - t0:.0f}s)", flush=True)
    rows, fin = [], {}
    combos = list(itertools.product(*GRID.values()))
    for i, combo in enumerate(combos):
        v = dict(zip(KEYS, combo))
        tr = score(days, A, F, sigmas[v["band_days"]], v)
        if tr is None:
            continue
        per = tr["day"].map(nb.period_of)
        row = {"i": i, **{k: str(x) for k, x in v.items()}}
        for k in PER:
            st = stats(tr[per == k], cal[k])
            for ins in INSTR:
                for mname, val in st[ins].items():
                    if SHORT[k] == "FIN":
                        fin.setdefault(i, {})[f"{ins}_{mname}"] = val
                    else:
                        row[f"{SHORT[k]}_{ins}_{mname}"] = val
        rows.append(row)
        if i % 400 == 399:
            print(f"  {i + 1}/{len(combos)} ({time.time() - t0:.0f}s)", flush=True)
    df = pd.DataFrame(rows)
    io.write_table(df, out / "search_open_periods.parquet")
    fdf = pd.DataFrame.from_dict(fin, orient="index")          # in memory only (D56, D66)
    res = {"versions": int(len(df))}
    as_written = df[(df.band_mult == "1.25") & (df.band_days == "20") & (df.or_offset_atr == "0.3") & (df.vwap == "True")
                    & (df.interval == "10") & (df.last_check == "14:00") & (df.exit == "hold") & (df.stop_atr == "None")]
    for ins in INSTR:
        el = df[(df[f"OLD_{ins}_trades"] >= 200) & (df[f"NEW_{ins}_trades"] >= 60)].copy()
        el["worst"] = el[[f"OLD_{ins}_sharpe", f"NEW_{ins}_sharpe"]].min(axis=1)
        picks = {"as_written": as_written, "best_on_OLD": el.sort_values(f"OLD_{ins}_sharpe", ascending=False).iloc[:1],
                 "best_on_NEW": el.sort_values(f"NEW_{ins}_sharpe", ascending=False).iloc[:1],
                 "steadiest": el.sort_values("worst", ascending=False).iloc[:1],
                 "steadiest_top10": el.sort_values("worst", ascending=False).iloc[:10]}
        r = {"share_positive": {p_: round(float((df[f"{p_}_{ins}_sum"] > 0).mean()), 3) for p_ in ("OLD", "NEW")} |
             {"FIN": round(float((fdf[f"{ins}_sum"] > 0).mean()), 3)},
             "rank_corr_sharpe": {"OLD_NEW": round(float(df[f"OLD_{ins}_sharpe"].rank().corr(df[f"NEW_{ins}_sharpe"].rank())), 2),
                                  "OLD_FIN": round(float(df.set_index("i")[f"OLD_{ins}_sharpe"].rank().corr(fdf[f"{ins}_sharpe"].rank())), 2),
                                  "NEW_FIN": round(float(df.set_index("i")[f"NEW_{ins}_sharpe"].rank().corr(fdf[f"{ins}_sharpe"].rank())), 2)},
             "picks": {}}
        for name, g in picks.items():
            ids = g["i"].tolist()
            f = fdf.loc[ids]
            pr = {"n": len(ids)}
            if len(ids) == 1:
                pr["settings"] = {k: g[k].iloc[0] for k in KEYS}
            for p_ in ("OLD", "NEW"):
                pr[p_] = {m_: round(float(g[f"{p_}_{ins}_{m_}"].mean()), 2) for m_ in ("trades", "sum", "sharpe", "max_dd", "win")}
            pr["FIN"] = {m_: round(float(f[f"{ins}_{m_}"].mean()), 2) for m_ in ("trades", "sum", "sharpe", "max_dd", "win")}
            pr["FIN"]["percentile_by_sharpe"] = round(float((fdf[f"{ins}_sharpe"] < f[f"{ins}_sharpe"].mean()).mean() * 100))
            r["picks"][name] = pr
        old, new = r["picks"]["best_on_OLD"], r["picks"]["best_on_NEW"]
        r["replacement"] = bool(old["NEW"]["sharpe"] >= 0.5 and old["FIN"]["sharpe"] >= 0.5
                                and new["OLD"]["sharpe"] >= 0.5 and new["FIN"]["sharpe"] >= 0.5)
        res[ins] = r
    io.write_json({**res, "grid": GRID, "qqq_cost_round_trip": QQQ_COST, "wall_seconds": round(time.time() - t0), **stamp()},
                  out / "search_summary.json")
    print(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
