"""D61: four checks on the current 15-minute breakout (C-breakout-00051), three periods.

    LAB_UNLOCK=final_test python scripts/breakout_checks.py

(1) risk units by year, (2) real trades against random twins, (3) longs and shorts apart,
(4) one volatility gate fixed in advance. Pass rules are in decisions.md D61.
"""
from __future__ import annotations

import json
import sys
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
import breakout_study as bs  # noqa: E402
import exit_study_fvg as es  # noqa: E402

PERIODS = ["OLD", "NEW", "FIN"]
LABEL = {"OLD": "2013-2021", "NEW": "2022-Jul 2024", "FIN": "Aug 2024-Nov 2026"}


def gate_series(mks: dict, m: str) -> pd.Series:
    """True when the mean daily range (% of close) of the previous 20 sessions is above its
    median over the previous 252 sessions (at least 126). Prior sessions only."""
    parts = []
    for per in PERIODS:
        ch = mks[f"{m}_{per}"].charts["daily"]
        parts.append(pd.DataFrame({"session": mks[f"{m}_{per}"].sessions[ch.session], "h": ch.h, "l": ch.l, "c": ch.c}))
    d = pd.concat(parts).drop_duplicates("session", keep="last").sort_values("session").set_index("session")
    rng_pct = (d["h"] - d["l"]) / d["c"] * 100
    avg20 = rng_pct.rolling(20).mean().shift(1)                       # sessions t-20 .. t-1
    med = avg20.shift(1).rolling(252, min_periods=126).median()        # earlier values of the same measure
    g = (avg20 > med).astype(float)
    g[avg20.isna() | med.isna()] = np.nan
    return g


def stats(tr: pd.DataFrame) -> dict:
    n = len(tr)
    return {"trades": int(n), "net": round(float(tr["dollars"].sum())) if n else 0,
            "total_R": round(float(tr["R"].sum()), 1) if n else 0.0,
            "avg_R": round(float(tr["R"].mean()), 4) if n else None,
            "win_rate": round(float((tr["dollars"] > 0).mean()), 3) if n else None}


def main() -> int:
    out = P.results() / "breakout_checks"
    out.mkdir(parents=True, exist_ok=True)
    v = bs.base_version()
    mks = es.load_markets()
    loaded = ft.load_frames("final")                 # the logged unlock opens and closes in here
    _, start, _ = ft.window_for("final")
    for m in ("NQ", "ES"):
        bars, rolls = loaded["frames"][m]
        mks[f"{m}_FIN"], _ = ft.build_market(m, bars, rolls, start)
    res = {"version": bs.BASE_ID, "periods": LABEL}
    year_rows = []
    for m in ("NQ", "ES"):
        gate = gate_series(mks, m)
        for per in PERIODS:
            key = f"{m}_{per}"
            mk = mks[key]
            sg.clear_cache()
            o, extra = sg.orders(mk, v)
            tr = engine.run(mk, o, **extra)
            r = {"all": stats(tr)}
            # (1) risk units by year
            yr = tr["exit_session"].map(lambda d: d.year)
            for y, g in tr.groupby(yr):
                year_rows.append({"market": m, "year": int(y), **stats(g)})
            # (2) random twins
            tw = ft.twins_test(mk, tr, f"breakout_checks:{key}")
            r["twins"] = {k: (round(x, 4) if isinstance(x, float) else x) for k, x in tw.items()}
            # (3) long and short
            r["long"], r["short"] = stats(tr[tr["side"] == 1]), stats(tr[tr["side"] == -1])
            # (4) volatility gate, applied to the signals before the engine
            gs = pd.Series(mk.sessions[mk.sess[np.asarray(o["t"])]]).map(gate).to_numpy()
            for name, mask in (("gate_on", gs == 1), ("gate_off", gs == 0), ("gate_defined", np.isfinite(gs))):
                om = {k: np.asarray(x)[mask] for k, x in o.items()}
                r[name] = stats(engine.run(mk, om, **extra)) if mask.any() else stats(tr.iloc[:0])
            r["share_of_signals_gate_on"] = round(float(np.nanmean(gs)), 3)
            res[key] = r
            print(key, json.dumps(r), flush=True)
    yt = pd.DataFrame(year_rows).groupby(["market", "year"], as_index=False).agg(
        trades=("trades", "sum"), net=("net", "sum"), total_R=("total_R", "sum"))
    yt["avg_R"] = (yt["total_R"] / yt["trades"]).round(4)
    io.write_table(yt, out / "by_year_R.csv")
    nq = [res[f"NQ_{p}"] for p in PERIODS]
    es_ = [res[f"ES_{p}"] for p in PERIODS]
    res["verdict"] = {
        "levels_beat_random_on_NQ_all_three": bool(all(r["twins"]["p_value"] < 0.05 for r in nq)),
        "shorts_positive_avg_R_on_NQ_in_at_least_two": bool(sum((r["short"]["avg_R"] or 0) > 0 for r in nq) >= 2),
        "gate_passes": bool(all(r["gate_on"]["avg_R"] > r["gate_defined"]["avg_R"] for r in nq)
                            and sum(r["gate_on"]["avg_R"] > r["gate_defined"]["avg_R"] for r in es_) >= 2
                            and all(r["gate_off"]["avg_R"] < r["gate_defined"]["avg_R"] for r in nq))}
    io.write_json({**res, **stamp()}, out / "summary.json")
    pd.set_option("display.width", 200)
    print(yt.to_string(index=False))
    print(json.dumps(res["verdict"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
