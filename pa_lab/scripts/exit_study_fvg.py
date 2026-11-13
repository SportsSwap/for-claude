"""D51: is 3R the best take profit for the daily fair value gap? ~8,000 variations, two periods.

    python scripts/exit_study_fvg.py run [--workers 4] [--limit N]
    python scripts/exit_study_fvg.py report

OLD = 2013-01..2021-09 (vendor_input/dukascopy_2013_2021), NEW = warm-up + discovery
(data/clean, 2022-01..2024-07). The sealed window is never read. What counts as "better" was
fixed in decisions.md D51 before any result existed.
"""
from __future__ import annotations

import argparse
import datetime as dt
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
from lab import dials, engine, ingest, io  # noqa: E402
from lab import strategy as sg  # noqa: E402
from lab.config import P, stamp  # noqa: E402
from lab.market import Market  # noqa: E402
from lab.news import load_calendar  # noqa: E402
import run_history_test as ht  # noqa: E402

BASE_ID = "C-fair_value_gap-00364"
GRID = ["target", "stop_ref", "stop_buffer_atr", "stop_mode", "time_exit", "management",
        "fvg_min_gap_atr", "fvg_max_age_bars", "news"]
NEWS_VALUES = ["trade", "skip"]
SETS = ["NQ_OLD", "ES_OLD", "NQ_NEW", "ES_NEW"]
_G = {}


def base_version() -> dict:
    for line in open(ROOT / "results" / "funnel" / "versions.jsonl"):
        r = json.loads(line)
        if r["id"] == BASE_ID:
            return {k: x for k, x in r.items() if k not in ht.SKIP}
    raise KeyError(BASE_ID)


def grid(targets=None) -> list[dict]:
    spec, base = dials.build_spec(), base_version()
    vals = []
    for d in GRID:
        v = NEWS_VALUES if d == "news" else dials.valid_values(spec, base, d)
        if d == "target" and targets:
            v = targets       # D53: targets outside the locked rulebook, side study only
        vals.append(v)
    out = []
    for combo in itertools.product(*vals):
        v = {**base, **dict(zip(GRID, combo))}
        if dials.is_valid(spec, v):
            out.append(v)
    return out


def load_markets() -> dict:
    news = set(load_calendar()["date"])
    news |= set(io.read_table(P.news() / "fomc_history.csv", parse_dates=["date"])["date"].dt.date)
    no_rolls = pd.DataFrame(columns=ingest.ROLL_COLS)
    mk = {}
    for m in ("NQ", "ES"):
        m1, _ = ht.clean_bars(ROOT / "vendor_input" / "dukascopy_2013_2021" / f"{m}_1m_backadjusted.parquet")
        mk[f"{m}_OLD"] = Market.from_frames(m, m1, no_rolls, frozenset(news), dt.date(2012, 12, 31), None)
        mk[f"{m}_NEW"] = Market.load(m)
    return mk


def _work(item):
    i, v = item
    row = {"i": i, **{d: v[d] for d in GRID}}
    for s in SETS:
        mk = _G[s]
        try:
            tr = sg.run_version(mk, v)
            d = engine.daily_pnl(mk, tr)
            n = len(tr)
            row.update({f"{s}_trades": n, f"{s}_net": float(tr["dollars"].sum()) if n else 0.0,
                        f"{s}_sharpe": engine.sharpe(d), f"{s}_avgR": float(tr["R"].mean()) if n else np.nan,
                        f"{s}_win": float((tr["dollars"] > 0).mean()) if n else np.nan})
        except Exception as e:  # noqa: BLE001
            row[f"{s}_error"] = str(e)[:200]
    if i % 50 == 0:
        sg.clear_cache()
    return row


def run(a) -> int:
    out = P.results() / "exit_study_fvg"
    out.mkdir(parents=True, exist_ok=True)
    targets = [t.strip() for t in a.targets.split(",")] if a.targets else None
    vs = grid(targets)
    if a.limit:
        vs = vs[:: max(1, len(vs) // a.limit)][: a.limit]
    print(f"{len(vs)} versions x {len(SETS)} sets", flush=True)
    t0 = time.time()
    _G.update(load_markets())
    print(f"markets loaded ({time.time() - t0:.0f}s)", flush=True)
    rows = []
    with mp.get_context("fork").Pool(a.workers) as pool:
        for k, r in enumerate(pool.imap_unordered(_work, list(enumerate(vs)), chunksize=16)):
            rows.append(r)
            if k % 500 == 499:
                print(f"  {k + 1}/{len(vs)} ({time.time() - t0:.0f}s)", flush=True)
    df = pd.DataFrame(rows).sort_values("i").reset_index(drop=True)
    for c in ("stop_buffer_atr", "fvg_min_gap_atr"):
        df[c] = df[c].astype(float)
    io.write_table(df, out / ("pilot.parquet" if a.limit else f"all_{a.tag}.parquet" if a.tag else "all.parquet"))
    io.write_json({"versions": len(df), "sets": SETS, "grid": GRID, "wall_seconds": round(time.time() - t0),
                   "errors": int(df.filter(like="_error").notna().sum().sum()) if df.filter(like="_error").shape[1] else 0,
                   **stamp()}, out / (f"run_meta_{a.tag}.json" if a.tag else "run_meta.json"))
    print(f"done: {len(df)} versions ({time.time() - t0:.0f}s)", flush=True)
    return 0


def _pick(df, on, min_trades):
    ok = df[(df[f"NQ_{on}_trades"] >= min_trades) & (df[f"ES_{on}_net"] > 0)]
    return ok.sort_values(f"NQ_{on}_sharpe", ascending=False)


def report(a) -> int:
    out = P.results() / "exit_study_fvg"
    df = io.read_table(out / "all.parquet")
    others = [d for d in GRID if d != "target"]
    # ---- (c) target effect, matched on every other dial
    wide = {}
    for s in SETS:
        for metric in ("avgR", "sharpe", "net", "trades", "win"):
            wide[(s, metric)] = df.pivot_table(index=others, columns="target", values=f"{s}_{metric}", aggfunc="first")
    rows = []
    for t in wide[("NQ_OLD", "avgR")].columns:
        r = {"target": t, "matched_groups": int(len(wide[("NQ_OLD", "avgR")]))}
        for s in SETS:
            r[f"{s}_avgR"] = round(float(wide[(s, "avgR")][t].mean()), 3)
            r[f"{s}_sharpe"] = round(float(wide[(s, "sharpe")][t].mean()), 2)
            r[f"{s}_net"] = round(float(wide[(s, "net")][t].mean()))
            r[f"{s}_trades"] = round(float(wide[(s, "trades")][t].mean()), 1)
            r[f"{s}_win"] = round(float(wide[(s, "win")][t].mean()), 3)
            if t != "3R":
                r[f"{s}_beats_3R_share"] = round(float((wide[(s, "avgR")][t] > wide[(s, "avgR")]["3R"]).mean()), 3)
        rows.append(r)
    tgt = pd.DataFrame(rows)
    io.write_table(tgt, out / "target_effect.csv")
    better = []
    for r in rows:
        if r["target"] == "3R":
            continue
        b = tgt.set_index("target").loc["3R"]
        if (r["NQ_OLD_avgR"] > b["NQ_OLD_avgR"] and r["NQ_NEW_avgR"] > b["NQ_NEW_avgR"]
                and r["ES_OLD_avgR"] >= b["ES_OLD_avgR"] and r["ES_NEW_avgR"] >= b["ES_NEW_avgR"]):
            better.append(r["target"])
    # ---- the same for every other dial (one line each, for the record)
    eff = []
    for d in GRID:
        for val, g in df.groupby(d):
            eff.append({"dial": d, "value": val, "versions": len(g),
                        **{f"{s}_{m}": round(float(g[f"{s}_{m}"].mean()), 3) for s in SETS for m in ("avgR", "sharpe")}})
    io.write_table(pd.DataFrame(eff), out / "dial_effects.csv")
    # ---- (d) walk-forward both ways
    wf = {}
    for on, other, mt in (("OLD", "NEW", 100), ("NEW", "OLD", 30)):
        ranked = _pick(df, on, mt)
        best, top10 = ranked.iloc[0], ranked.iloc[:10]
        wf[f"picked_on_{on}"] = {
            "eligible": int(len(ranked)),
            "best": {**{d: (best[d].item() if hasattr(best[d], "item") else best[d]) for d in GRID},
                     f"NQ_{on}_sharpe": round(float(best[f"NQ_{on}_sharpe"]), 2), f"NQ_{on}_net": round(float(best[f"NQ_{on}_net"])),
                     f"NQ_{other}_sharpe": round(float(best[f"NQ_{other}_sharpe"]), 2), f"NQ_{other}_net": round(float(best[f"NQ_{other}_net"])),
                     f"NQ_{other}_trades": int(best[f"NQ_{other}_trades"]),
                     f"ES_{other}_sharpe": round(float(best[f"ES_{other}_sharpe"]), 2), f"ES_{other}_net": round(float(best[f"ES_{other}_net"]))},
            "top10_mean": {f"NQ_{on}_sharpe": round(float(top10[f"NQ_{on}_sharpe"].mean()), 2),
                           f"NQ_{other}_sharpe": round(float(top10[f"NQ_{other}_sharpe"].mean()), 2),
                           f"NQ_{other}_net": round(float(top10[f"NQ_{other}_net"].mean())),
                           f"ES_{other}_sharpe": round(float(top10[f"ES_{other}_sharpe"].mean()), 2),
                           f"ES_{other}_net": round(float(top10[f"ES_{other}_net"].mean()))},
            "passes": bool(best[f"NQ_{other}_sharpe"] >= 0.5 and best[f"ES_{other}_net"] > 0)}
    both = df[(df["NQ_OLD_trades"] >= 100) & (df["NQ_NEW_trades"] >= 30)]
    rho = float(both["NQ_OLD_sharpe"].rank().corr(both["NQ_NEW_sharpe"].rank()))
    rho_es = float(both["ES_OLD_sharpe"].rank().corr(both["ES_NEW_sharpe"].rank()))
    base = base_version()
    cur = df[np.logical_and.reduce([df[d].astype(str) == str(float(base[d]) if d in ("stop_buffer_atr", "fvg_min_gap_atr") else base[d]) for d in GRID])]
    summary = {"versions": int(len(df)),
               "share_profitable": {s: round(float((df[f"{s}_net"] > 0).mean()), 3) for s in SETS},
               "median_sharpe": {s: round(float(df[f"{s}_sharpe"].median()), 2) for s in SETS},
               "share_profitable_on_all_four": round(float(np.logical_and.reduce([df[f"{s}_net"] > 0 for s in SETS]).mean()), 3),
               "targets_better_than_3R_by_the_declared_rule": better,
               "walk_forward": wf, "rank_correlation_old_vs_new": {"NQ": round(rho, 2), "ES": round(rho_es, 2)},
               "current_version_rows": int(len(cur)),
               "current_version": {s: {"sharpe": round(float(cur[f"{s}_sharpe"].iloc[0]), 2), "net": round(float(cur[f"{s}_net"].iloc[0])),
                                       "trades": int(cur[f"{s}_trades"].iloc[0])} for s in SETS} if len(cur) == 1 else None,
               "replacement_issued": bool(wf["picked_on_OLD"]["passes"] and wf["picked_on_NEW"]["passes"]),
               **stamp()}
    io.write_json(summary, out / "summary.json")
    pd.set_option("display.width", 250)
    print(tgt.to_string(index=False))
    print(json.dumps(summary, indent=1, default=str))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report", "count"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="pilot: run about this many versions, evenly spaced")
    ap.add_argument("--targets", default="", help="comma list of targets to use instead of the rulebook's, e.g. 6R,7R")
    ap.add_argument("--tag", default="", help="suffix for the output file when --targets is used")
    a = ap.parse_args(argv)
    if a.cmd == "count":
        vs = grid()
        spec, base = dials.build_spec(), base_version()
        print(len(vs), {d: (NEWS_VALUES if d == "news" else dials.valid_values(spec, base, d)) for d in GRID})
        return 0
    return run(a) if a.cmd == "run" else report(a)


if __name__ == "__main__":
    sys.exit(main())
