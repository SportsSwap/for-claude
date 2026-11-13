"""D58: the current daily fair value gap version at every time limit from 96 to 960 hours
and every target from 1R to 15R.

    LAB_UNLOCK=final_test python scripts/time_limit_scan_fvg.py [--workers 4]

Picks are made on OLD (2013-2021) and NEW (2022 to Jul 2024) only; the recent window
(Aug 2024 to Nov 2026) is scored for the picks and for banded summaries, and its
per-version results are never written to disk (decisions.md D56, D58).
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from lab import engine, io  # noqa: E402
from lab import final_test as ft  # noqa: E402
from lab import strategy as sg  # noqa: E402
from lab.config import P, stamp  # noqa: E402
import exit_study_fvg as es  # noqa: E402

HOURS = list(range(96, 961))
TARGETS = ["1R", "1.5R", "2R"] + [f"{k}R" for k in range(3, 16)]
OPEN = ["NQ_OLD", "ES_OLD", "NQ_NEW", "ES_NEW"]
FIN = ["NQ_FIN", "ES_FIN"]
ALL = OPEN + FIN
BANDS = [(96, 96), (97, 119), (120, 167), (168, 239), (240, 335), (336, 479), (480, 719), (720, 960)]
_G = {}


def _work(item):
    i, v = item
    row = {"i": i, "hours": int(v["time_exit"].split("_")[1]), "target": v["target"]}
    for s in ALL:
        mk = _G[s]
        tr = sg.run_version(mk, v)
        d = engine.daily_pnl(mk, tr)
        row[f"{s}_trades"] = len(tr)
        row[f"{s}_net"] = float(tr["dollars"].sum()) if len(tr) else 0.0
        row[f"{s}_sharpe"] = engine.sharpe(d)
    if i % 50 == 0:
        sg.clear_cache()
    return row


def band_of(h):
    for a, b in BANDS:
        if a <= h <= b:
            return f"{a}" if a == b else f"{a}-{b}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    out = P.results() / "time_limit_scan_fvg"
    out.mkdir(parents=True, exist_ok=True)
    base = es.base_version()
    vs = [{**base, "time_exit": f"bars_{h}", "target": t} for h in HOURS for t in TARGETS]
    t0 = time.time()
    _G.update(es.load_markets())
    loaded = ft.load_frames("final")                 # the logged unlock opens and closes in here
    _, start, end = ft.window_for("final")
    for m in ("NQ", "ES"):
        bars, rolls = loaded["frames"][m]
        _G[f"{m}_FIN"], _ = ft.build_market(m, bars, rolls, start)
    print(f"{len(vs)} versions x {len(ALL)} sets; markets loaded ({time.time() - t0:.0f}s)", flush=True)
    rows = []
    with mp.get_context("fork").Pool(a.workers) as pool:
        for k, r in enumerate(pool.imap_unordered(_work, list(enumerate(vs)), chunksize=16)):
            rows.append(r)
            if k % 2000 == 1999:
                print(f"  {k + 1}/{len(vs)} ({time.time() - t0:.0f}s)", flush=True)
    df = pd.DataFrame(rows).sort_values("i").reset_index(drop=True)
    open_cols = ["i", "hours", "target"] + [c for c in df.columns if c.split("_")[1:2] in (["OLD"], ["NEW"])]
    io.write_table(df[open_cols], out / "open_periods.parquet")          # recent-window columns stay in memory

    # ---- picks, on OLD and NEW only
    df["worst"] = df[[f"{s}_sharpe" for s in OPEN]].min(axis=1)
    ok = (df["NQ_OLD_trades"] >= 100) & (df["NQ_NEW_trades"] >= 30)
    surf = df.assign(w=df["worst"].where(ok)).pivot(index="hours", columns="target", values="w")[TARGETS]
    smooth = surf.rolling(25, center=True, min_periods=13).mean().T.rolling(3, center=True, min_periods=2).mean().T
    bh, bt = surf.stack().idxmax()
    ph, pt = smooth.stack().idxmax()
    picks = {"best_single_cell": (int(bh), bt), "plateau_pick": (int(ph), pt), "current": (96, "3R")}
    cell = df.set_index(["hours", "target"])
    res = {}
    for name, (h, t) in picks.items():
        r = cell.loc[(h, t)]
        v = {**base, "time_exit": f"bars_{h}", "target": t}
        by = {}
        for m in ("NQ", "ES"):
            yy = {}
            for per in ("OLD", "NEW", "FIN"):
                d = engine.daily_pnl(_G[f"{m}_{per}"], sg.run_version(_G[f"{m}_{per}"], v))
                for y in sorted({x.year for x in d.index}):
                    yy[y] = yy.get(y, 0) + round(float(d[[x.year == y for x in d.index]].sum()))
            by[m] = yy
        res[name] = {"hours": h, "target": t,
                     **{s: {"trades": int(r[f"{s}_trades"]), "net": round(float(r[f"{s}_net"])), "sharpe": round(float(r[f"{s}_sharpe"]), 2)} for s in ALL},
                     "worst_open_sharpe": round(float(r["worst"]), 2),
                     "smoothed_worst_open_sharpe": round(float(smooth.loc[h, t]), 2) if np.isfinite(smooth.loc[h, t]) else None,
                     "recent_percentile_nq": round(float((df["NQ_FIN_sharpe"] < r["NQ_FIN_sharpe"]).mean()) * 100),
                     "by_year": by}
    # neighbours of the best single cell: how much one hour changes things (open periods)
    nb = {int(h): {s: round(float(cell.loc[(h, bt)][f"{s}_net"])) for s in ("NQ_OLD", "NQ_NEW")}
          for h in range(max(96, bh - 3), min(960, bh + 3) + 1)}
    # ---- banded summaries (means), all three periods
    df["band"] = df["hours"].map(band_of)
    order = [band_of(a_) for a_, _ in BANDS]
    band = df.groupby("band")[[f"{s}_{m}" for s in ALL for m in ("net", "sharpe")]].mean().reindex(order).round(2)
    band3 = df[df["target"] == "3R"].groupby("band")[[f"{s}_net" for s in ALL]].mean().reindex(order).round(0)
    tgt = df.groupby("target")[[f"{s}_{m}" for s in ALL for m in ("net", "sharpe")]].mean().reindex(TARGETS).round(2)
    io.write_table(band.reset_index(), out / "by_time_band.csv")
    io.write_table(band3.reset_index(), out / "by_time_band_3R.csv")
    io.write_table(tgt.reset_index(), out / "by_target.csv")
    # hour-to-hour jitter at 3R on the open periods: typical change in net from one extra hour
    h3 = df[df["target"] == "3R"].set_index("hours")
    jitter = {s: round(float(h3[f"{s}_net"].diff().abs().median())) for s in ("NQ_OLD", "NQ_NEW")}
    summary = {"versions": int(len(df)), "recent_window": [str(start), str(end)],
               "share_profitable": {s: round(float((df[f"{s}_net"] > 0).mean()), 3) for s in ALL},
               "share_beating_current_nq_net": {s: round(float((df[f"{s}_net"] > cell.loc[(96, "3R")][f"{s}_net"]).mean()), 3) for s in ("NQ_OLD", "NQ_NEW", "NQ_FIN")},
               "share_beating_current_in_all_three_nq": round(float(np.logical_and.reduce(
                   [df[f"{s}_net"] > cell.loc[(96, "3R")][f"{s}_net"] for s in ("NQ_OLD", "NQ_NEW", "NQ_FIN")]).mean()), 4),
               "rank_correlation_nq": {"OLD_vs_NEW": round(float(df["NQ_OLD_sharpe"].rank().corr(df["NQ_NEW_sharpe"].rank())), 2),
                                       "OLD_vs_FIN": round(float(df["NQ_OLD_sharpe"].rank().corr(df["NQ_FIN_sharpe"].rank())), 2),
                                       "NEW_vs_FIN": round(float(df["NQ_NEW_sharpe"].rank().corr(df["NQ_FIN_sharpe"].rank())), 2)},
               "median_change_in_net_from_one_more_hour_at_3R": jitter,
               "neighbours_of_best_single_cell": {"target": bt, "net_by_hours": nb},
               "picks": res, "wall_seconds": round(time.time() - t0), **stamp()}
    io.write_json(summary, out / "summary.json")
    pd.set_option("display.width", 250)
    print(band.to_string()); print(band3.to_string()); print(tgt.to_string())
    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
