"""D60: thousands of variations of the 15-minute breakout, three periods.

    LAB_UNLOCK=final_test python scripts/breakout_study.py [--n 30000] [--workers 4]
    python scripts/breakout_study.py --pilot 200        # open periods only, timing

Picks are made on OLD (2013-2021) and NEW (2022 to Jul 2024) only. The recent window
(Aug 2024 to Nov 2026) is scored for the picks and for summaries; its per-version
results are never written to disk (decisions.md D56, D60).
"""
from __future__ import annotations

import argparse
import itertools
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
from lab.seed import rng  # noqa: E402
import exit_study_fvg as es  # noqa: E402
import run_history_test as ht  # noqa: E402

BASE_ID = "C-breakout-00051"
VARIED = {
    "target": ["1R", "1.5R", "2R", "3R", "4R", "5R"],
    "stop_ref": ["beyond_level", "touch_wick", "last_swing"],
    "stop_buffer_atr": [0.0, 0.1, 0.25],
    "stop_mode": ["hard", "close_based"],
    "management": ["hold", "exit_on_choch"],
    "time_exit": ["flat_1600", "bars_24", "bars_96", "bars_192"],
    "swing_strength": [2, 3, 5],
    "level_min_touches": [2, 3, 4],
    "level_tol_atr": [0.1, 0.25, 0.5],
    "level_shape": ["line", "box"],
    "session": ["all", "london_ny", "ny", "ny_open"],
    "fresh_breakouts_only": ["off", "on"],
    "news": ["trade", "skip"],
    "trend_filter": ["off", "setup_chart", "daily"],
}
DIALS = list(VARIED)
DETECTOR = ["swing_strength", "level_min_touches", "level_tol_atr", "level_shape"]
OPEN = ["NQ_OLD", "ES_OLD", "NQ_NEW", "ES_NEW"]
FIN = ["NQ_FIN", "ES_FIN"]
MIN_OLD, MIN_NEW = 300, 100
_G, _SETS = {}, []


def base_version() -> dict:
    for line in open(ROOT / "results" / "funnel" / "versions.jsonl"):
        r = json.loads(line)
        if r["id"] == BASE_ID:
            return {k: x for k, x in r.items() if k not in ht.SKIP}
    raise KeyError(BASE_ID)


def draw(n: int) -> list[dict]:
    base = base_version()
    g = rng("breakout_study")
    seen = {tuple(base[d] for d in DIALS)}
    out = [dict(base)]
    while len(out) < n + 1:
        combo = tuple(VARIED[d][int(g.integers(len(VARIED[d])))] for d in DIALS)
        if combo in seen:
            continue
        seen.add(combo)
        out.append({**base, **dict(zip(DIALS, combo))})
    return out


def _work(group):
    rows = []
    for i, v in group:
        row = {"i": i, **{d: v[d] for d in DIALS}}
        for s in _SETS:
            mk = _G[s]
            try:
                tr = sg.run_version(mk, v)
                d = engine.daily_pnl(mk, tr)
                row[f"{s}_trades"] = len(tr)
                row[f"{s}_net"] = float(tr["dollars"].sum()) if len(tr) else 0.0
                row[f"{s}_sharpe"] = engine.sharpe(d)
            except Exception as e:  # noqa: BLE001
                row[f"{s}_error"] = str(e)[:160]
        rows.append(row)
    sg.clear_cache()          # one detector setting per group, so the cache is reused inside it
    return rows


def _years(v):
    by = {}
    for m in ("NQ", "ES"):
        yy = {}
        for per in ("OLD", "NEW", "FIN"):
            if f"{m}_{per}" not in _G:
                continue
            mk = _G[f"{m}_{per}"]
            d = engine.daily_pnl(mk, sg.run_version(mk, v))
            yr = np.array([x.year for x in d.index])
            for y in sorted(set(yr)):
                yy[int(y)] = yy.get(int(y), 0) + round(float(d[yr == y].sum()))
        by[m] = yy
    sg.clear_cache()
    return by


def main(argv=None) -> int:
    global _SETS
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--pilot", type=int, default=0)
    a = ap.parse_args(argv)
    out = P.results() / "breakout_study"
    out.mkdir(parents=True, exist_ok=True)
    vs = draw(a.pilot or a.n)
    t0 = time.time()
    _G.update(es.load_markets())
    _SETS = list(OPEN)
    if not a.pilot:
        loaded = ft.load_frames("final")             # the logged unlock opens and closes in here
        _, start, end = ft.window_for("final")
        for m in ("NQ", "ES"):
            bars, rolls = loaded["frames"][m]
            _G[f"{m}_FIN"], _ = ft.build_market(m, bars, rolls, start)
        _SETS = OPEN + FIN
    print(f"{len(vs)} versions x {len(_SETS)} sets; markets loaded ({time.time() - t0:.0f}s)", flush=True)
    key = lambda iv: tuple(iv[1][d] for d in DETECTOR)  # noqa: E731
    items = sorted(enumerate(vs), key=key)
    groups = []
    for _, g in itertools.groupby(items, key=key):
        g = list(g)
        groups += [g[k:k + 150] for k in range(0, len(g), 150)]
    rows, done = [], 0
    with mp.get_context("fork").Pool(a.workers) as pool:
        for r in pool.imap_unordered(_work, groups):
            rows += r
            if (done + len(r)) // 2500 > done // 2500:
                print(f"  {done + len(r)}/{len(vs)} ({time.time() - t0:.0f}s)", flush=True)
            done += len(r)
    df = pd.DataFrame(rows).sort_values("i").reset_index(drop=True)
    errs = int(df.filter(like="_error").notna().sum().sum()) if df.filter(like="_error").shape[1] else 0
    print(f"ran {len(df)} versions, {errs} errors ({time.time() - t0:.0f}s)", flush=True)
    if a.pilot:
        print(df[[f"{s}_{m}" for s in OPEN for m in ("trades", "sharpe")]].describe().round(2).to_string())
        return 0
    open_cols = ["i"] + DIALS + [c for c in df.columns if c.split("_")[1:2] in (["OLD"], ["NEW"])]
    io.write_table(df[open_cols], out / "open_periods.parquet")       # recent-window columns stay in memory
    ALL = OPEN + FIN
    # ---- picks, on OLD and NEW only
    ok = (df["NQ_OLD_trades"] >= MIN_OLD) & (df["NQ_NEW_trades"] >= MIN_NEW)
    el = df[ok].copy()
    el["worst"] = el[[f"{s}_sharpe" for s in OPEN]].min(axis=1)
    old = el[el["ES_OLD_net"] > 0].sort_values("NQ_OLD_sharpe", ascending=False)
    new = el[el["ES_NEW_net"] > 0].sort_values("NQ_NEW_sharpe", ascending=False)
    st = el.sort_values("worst", ascending=False)
    pk = {"current": df[df["i"] == 0], "best_on_OLD": old.iloc[:1], "best_on_OLD_top10": old.iloc[:10],
          "best_on_NEW": new.iloc[:1], "best_on_NEW_top10": new.iloc[:10], "steadiest": st.iloc[:1], "steadiest_top10": st.iloc[:10]}
    res = {}
    for name, g in pk.items():
        r = {"n": int(len(g)), "dials": {d: (g[d].iloc[0].item() if hasattr(g[d].iloc[0], "item") else g[d].iloc[0]) for d in DIALS} if len(g) == 1 else "average of 10"}
        for s in ALL:
            r[s] = {"trades": round(float(g[f"{s}_trades"].mean()), 1), "net": round(float(g[f"{s}_net"].mean())), "sharpe": round(float(g[f"{s}_sharpe"].mean()), 2)}
        for s in FIN:
            r[s]["percentile_in_grid_by_sharpe"] = round(float((df[f"{s}_sharpe"] < g[f"{s}_sharpe"].mean()).mean()) * 100)
        r["holds_recent"] = bool(r["NQ_FIN"]["net"] > 0 and r["NQ_FIN"]["sharpe"] >= 0.5 and r["ES_FIN"]["net"] > 0)
        if len(g) == 1:
            r["by_year"] = _years(vs[int(g["i"].iloc[0])])
        res[name] = r
    passes = {"best_on_OLD_on_NEW": bool(res["best_on_OLD"]["NQ_NEW"]["sharpe"] >= 0.5 and res["best_on_OLD"]["ES_NEW"]["net"] > 0),
              "best_on_NEW_on_OLD": bool(res["best_on_NEW"]["NQ_OLD"]["sharpe"] >= 0.5 and res["best_on_NEW"]["ES_OLD"]["net"] > 0)}
    # ---- effect of each setting (averages), all three periods
    eff = []
    for d in DIALS:
        for val, g in df.groupby(d):
            eff.append({"dial": d, "value": val, "versions": int(len(g)),
                        **{f"{s}_{m}": round(float(g[f"{s}_{m}"].mean()), 3 if m == "sharpe" else 0) for s in ALL for m in ("sharpe", "net")},
                        "NQ_OLD_trades": round(float(g["NQ_OLD_trades"].mean()))})
    eff = pd.DataFrame(eff)
    io.write_table(eff, out / "dial_effects.csv")
    cur = df[df["i"] == 0].iloc[0]
    summary = {"versions": int(len(df)), "errors": errs, "recent_window": [str(start), str(end)],
               "check_current": {s: {"trades": int(cur[f"{s}_trades"]), "net": round(float(cur[f"{s}_net"])), "sharpe": round(float(cur[f"{s}_sharpe"]), 2)} for s in ALL},
               "eligible_for_picks": int(ok.sum()),
               "share_profitable": {s: round(float((df[f"{s}_net"] > 0).mean()), 3) for s in ALL},
               "median_sharpe": {s: round(float(df[f"{s}_sharpe"].median()), 2) for s in ALL},
               "sharpe_p90": {s: round(float(df[f"{s}_sharpe"].quantile(0.9)), 2) for s in ALL},
               "max_sharpe_open": {s: round(float(el[f"{s}_sharpe"].max()), 2) for s in OPEN},
               "share_profitable_on_all_four_open": round(float(np.logical_and.reduce([df[f"{s}_net"] > 0 for s in OPEN]).mean()), 4),
               "nq_sharpe_0p5_both_open_periods_and_es_profitable_both": int(((el.NQ_OLD_sharpe >= .5) & (el.NQ_NEW_sharpe >= .5) & (el.ES_OLD_net > 0) & (el.ES_NEW_net > 0)).sum()),
               "rank_correlation_nq": {"OLD_vs_NEW": round(float(el["NQ_OLD_sharpe"].rank().corr(el["NQ_NEW_sharpe"].rank())), 2),
                                       "OLD_vs_recent": round(float(el["NQ_OLD_sharpe"].rank().corr(el["NQ_FIN_sharpe"].rank())), 2),
                                       "NEW_vs_recent": round(float(el["NQ_NEW_sharpe"].rank().corr(el["NQ_FIN_sharpe"].rank())), 2)},
               "replacement_rule": passes, "replacement_issued": bool(all(passes.values())),
               "picks": res, "wall_seconds": round(time.time() - t0), **stamp()}
    io.write_json(summary, out / "summary.json")
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    print(eff.to_string(index=False))
    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
