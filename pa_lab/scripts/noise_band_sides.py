"""D74: long and short trades apart, and a long-only / short-only search of the noise band.

    LAB_UNLOCK=final_test python scripts/noise_band_sides.py
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from lab import io  # noqa: E402
from lab.config import P, stamp  # noqa: E402
import noise_band_qqq as nb  # noqa: E402
import noise_band_search as ns  # noqa: E402
import noise_band_years as ny  # noqa: E402

PER = list(nb.PERIODS)
SHORT = dict(zip(PER, ["OLD", "NEW", "FIN"]))


def entries_side(A, F, sig, v, only):
    """As ns.entries, but each day takes the first signal of one side only (+1 long, -1 short, 0 both)."""
    C = A["close"]
    atr = F["atr_daily"]
    ch = ns.checks(v["interval"], v["last_check"])
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
    fire = {1: lo, -1: sh, 0: lo | sh}[only] & valid[:, None]
    d = np.flatnonzero(fire.any(axis=1))
    j = np.argmax(fire[d], axis=1)
    side = np.full(len(d), only) if only else np.where(lo[d, j], 1, -1)
    return d, ch[j], side


def trades(days, A, F, sig, v, only):
    d, e, side = entries_side(A, F, sig, v, only)
    x = ns.exits_vec(A, F, d, e, side, v)
    C = A["close"]
    r = (side * (C[d, x] / C[d, e] - 1) - ns.QQQ_COST) * 100
    return pd.DataFrame({"day": days[d], "side": side, "qqq": r})


def stats(tr, cal):
    daily = tr.groupby("day")["qqq"].sum().reindex(cal, fill_value=0.0)
    sd = daily.std(ddof=1)
    eq = daily.cumsum()
    return {"trades": int(len(tr)), "sum": round(float(daily.sum()), 2),
            "sharpe": round(float(daily.mean() / sd * math.sqrt(252)), 2) if sd > 0 else 0.0,
            "max_dd": round(float((eq.cummax().clip(lower=0) - eq).max()), 2),
            "win": round(float((tr["qqq"] > 0).mean()), 3) if len(tr) else 0.0}


def by_period(tr, cal):
    per = tr["day"].map(nb.period_of)
    return {SHORT[k]: stats(tr[per == k], cal[k]) for k in PER}


def main() -> int:
    out = P.results() / "noise_band"
    m = nb.load_minutes()
    days, A, _ = nb.rth_grid(m)
    F = nb.features(days, A)
    sig = {k: ns.sigma_for(A, F, k) for k in (14, 20)}
    cal = {k: [x for x in days if nb.period_of(x) == k] for k in PER}
    res = {"split": {}}
    # (a) the two issued versions, both sides, split
    for name, v in ny.VERSIONS.items():
        tr = trades(days, A, F, sig[v["band_days"]], v, 0)
        tr = tr[tr["day"].map(nb.period_of).notna()]
        res["split"][name] = {"long": by_period(tr[tr.side == 1], cal), "short": by_period(tr[tr.side == -1], cal),
                              "both": by_period(tr, cal)}
    # (b) one-side searches
    for only, label in ((1, "long_only"), (-1, "short_only")):
        rows, fin = [], {}
        for i, combo in enumerate(itertools.product(*ns.GRID.values())):
            v = dict(zip(ns.KEYS, combo))
            tr = trades(days, A, F, sig[v["band_days"]], v, only)
            tr = tr[tr["day"].map(nb.period_of).notna()]
            st = by_period(tr, cal)
            rows.append({"i": i, **{k: str(x) for k, x in v.items()},
                         **{f"{p}_{m_}": st[p][m_] for p in ("OLD", "NEW") for m_ in st[p]}})
            fin[i] = st["FIN"]
        df = pd.DataFrame(rows)
        io.write_table(df, out / f"search_{label}_open_periods.parquet")
        el = df[(df["OLD_trades"] >= 150) & (df["NEW_trades"] >= 40)].copy()
        el["worst"] = el[["OLD_sharpe", "NEW_sharpe"]].min(axis=1)
        picks = {"best_on_OLD": el.sort_values("OLD_sharpe", ascending=False).iloc[0],
                 "best_on_NEW": el.sort_values("NEW_sharpe", ascending=False).iloc[0],
                 "steadiest": el.sort_values("worst", ascending=False).iloc[0]}
        fs = pd.DataFrame.from_dict(fin, orient="index")
        r = {"share_profitable": {"OLD": round(float((df.OLD_sum > 0).mean()), 3), "NEW": round(float((df.NEW_sum > 0).mean()), 3),
                                  "FIN": round(float((fs["sum"] > 0).mean()), 3)},
             "median_sharpe": {"OLD": float(df.OLD_sharpe.median()), "NEW": float(df.NEW_sharpe.median()),
                               "FIN": float(fs["sharpe"].median())}, "picks": {}}
        for name, row in picks.items():
            i = int(row["i"])
            r["picks"][name] = {"settings": {k: row[k] for k in ns.KEYS},
                                "OLD": {m_: row[f"OLD_{m_}"] for m_ in ("trades", "sum", "sharpe", "max_dd", "win")},
                                "NEW": {m_: row[f"NEW_{m_}"] for m_ in ("trades", "sum", "sharpe", "max_dd", "win")},
                                "FIN": fin[i]}
        o = r["picks"]["best_on_OLD"]
        r["issue"] = bool(o["NEW"]["sharpe"] >= 0.5 and o["FIN"]["sharpe"] >= 0.5)
        res[label] = r
    io.write_json({**res, **stamp()}, out / "sides.json")
    print(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
