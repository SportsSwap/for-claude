"""D48: the two final-test survivors, unchanged, on years the lab never touched (2013-2021).

    python scripts/run_history_test.py [--src vendor_input/dukascopy_2013_2021]
                                       [--warmup-end 2012-12-31] [--out results/history_2013_2021]

Everything here was fixed before the data was in (decisions.md D48, D49):
  - versions: C-breakout-00051 and C-fair_value_gap-00364, dials read from
    results/funnel/versions.jsonl, nothing changed;
  - same cleaning, charts, engine and costs as the lab;
  - news days: BLS release dates (data/news/news_calendar.csv) plus the scheduled FOMC
    decision days from the Fed's historical pages (data/news/fomc_history.csv);
  - pass: NQ made money with a Sharpe of 0.5 or more over the whole period, and ES made money;
  - a year is "thin" when its median bars per session is under 80% of the discovery
    window's median, or more than 5% of its weekday sessions are missing. Thin years are
    reported separately; none is dropped.
The data-quality table is written first, the results after it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lab import audit, engine, ingest, io  # noqa: E402
from lab import strategy as sg  # noqa: E402
from lab.config import P, stamp, thresholds  # noqa: E402
from lab.market import Market  # noqa: E402
from lab.news import load_calendar  # noqa: E402
from lab.sessions import weekday_sessions  # noqa: E402

IDS = ["C-breakout-00051", "C-fair_value_gap-00364"]
SKIP = {"id", "set", "name", "nq_signals", "graded"}
PASS_SHARPE = 0.5
THIN_BARS_FRAC = 0.80
THIN_MISSING_FRAC = 0.05


def clean_bars(path: Path) -> tuple[pd.DataFrame, dict]:
    th = thresholds()
    fl = audit.flag_bars(ingest.load_bars(path), th["audit"]["gap_minutes"], th["session"]["halt_hour_et"])
    return ingest.clean(fl)


def bars_audit(m1: pd.DataFrame, ref_median: float) -> pd.DataFrame:
    per = m1.groupby("session").size()
    year = pd.Series([d.year for d in per.index], index=per.index)
    rows = []
    for y, g in per.groupby(year):
        wk = len(weekday_sessions(max(g.index.min(), dt.date(y, 1, 1)), min(g.index.max(), dt.date(y, 12, 31))))
        med = float(g.median())
        missing = 1 - len(g) / wk if wk else 0.0
        rows.append({"year": int(y), "sessions": int(len(g)), "weekdays": wk, "missing_frac": round(missing, 3),
                     "bars_median": med, "bars_p05": float(g.quantile(0.05)), "bars_min": int(g.min()),
                     "bars_vs_discovery": round(med / ref_median, 3) if ref_median else None,
                     "thin": bool(ref_median and (med < THIN_BARS_FRAC * ref_median or missing > THIN_MISSING_FRAC))})
    return pd.DataFrame(rows)


def drawdown(daily: pd.Series) -> float:
    eq = daily.cumsum()
    return float((eq.cummax().clip(lower=0) - eq).max()) if len(eq) else 0.0


def by_year(mk: Market, tr: pd.DataFrame, daily: pd.Series) -> pd.DataFrame:
    yr = np.array([d.year for d in daily.index])
    tyr = tr["exit_session"].map(lambda d: d.year) if len(tr) else pd.Series(dtype=int)
    rows = []
    for y in sorted(set(yr)):
        d = daily[yr == y]
        t = tr[tyr == y] if len(tr) else tr
        rows.append({"year": int(y), "trades": int(len(t)), "net": round(float(d.sum()), 0),
                     "sharpe": round(engine.sharpe(d), 2), "max_drawdown": round(drawdown(d), 0),
                     "win_rate": round(float((t["dollars"] > 0).mean()), 3) if len(t) else None})
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=ROOT / "vendor_input" / "dukascopy_2013_2021")
    ap.add_argument("--warmup-end", default="2012-12-31")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    warm_end = dt.date.fromisoformat(a.warmup_end)
    out = a.out or P.results() / "history_2013_2021"
    out.mkdir(parents=True, exist_ok=True)
    vers = {}
    for line in open(ROOT / "results" / "funnel" / "versions.jsonl"):
        r = json.loads(line)
        if r["id"] in IDS:
            vers[r["id"]] = {k: x for k, x in r.items() if k not in SKIP}
    assert sorted(vers) == sorted(IDS)

    news = set(load_calendar()["date"])
    fomc = io.read_table(P.news() / "fomc_history.csv", parse_dates=["date"])
    news |= set(fomc["date"].dt.date)

    # ---- data quality first
    frames, audits = {}, []
    for m in ("NQ", "ES"):
        m1, dropped = clean_bars(a.src / f"{m}_1m_backadjusted.parquet")
        ref = io.read_table(P.clean() / f"{m}_1m.parquet")      # warm-up + discovery only
        ref_med = float(ref.groupby("session").size().median())
        au = bars_audit(m1, ref_med)
        au.insert(0, "market", m)
        audits.append(au)
        frames[m] = m1
        print(f"{m}: {len(m1):,} clean bars, {m1['session'].min()} .. {m1['session'].max()}, dropped {dropped}; "
              f"discovery median {ref_med:.0f} bars a session", flush=True)
    au = pd.concat(audits, ignore_index=True)
    io.write_table(au, out / "audit_bars_by_year.csv")
    print(au.to_string(index=False), flush=True)
    same_sessions = set(frames["NQ"]["session"]) == set(frames["ES"]["session"])

    # ---- the two versions, unchanged
    no_rolls = pd.DataFrame(columns=ingest.ROLL_COLS)
    rows, summary = [], {}
    (out / "daily").mkdir(exist_ok=True)
    for m in ("NQ", "ES"):
        mk = Market.from_frames(m, frames[m], no_rolls, frozenset(news), warm_end, None)
        news_in = int(mk.news[mk.tradable].sum())
        for vid in IDS:
            sg.clear_cache()
            tr = sg.run_version(mk, vers[vid])
            d = engine.daily_pnl(mk, tr)
            io.write_table(d.rename("pnl").reset_index(), out / "daily" / f"{m}_{vid}.parquet")
            io.write_table(tr, out / f"trades_{m}_{vid}.csv")
            mt = engine.metrics(mk, tr, d)
            yt = by_year(mk, tr, d)
            yt.insert(0, "id", vid)
            yt.insert(0, "market", m)
            rows.append(yt)
            summary[f"{m}:{vid}"] = {"trades": mt["trades"], "net": round(mt["net"], 0), "sharpe": round(mt["sharpe"], 2),
                                     "win_rate": round(mt["win_rate"], 3), "max_drawdown": round(drawdown(d), 0),
                                     "sessions": mt["days"], "first": str(d.index.min()), "last": str(d.index.max()),
                                     "years_profitable": int((yt["net"] > 0).sum()), "years": int(len(yt)),
                                     "news_days_in_period": news_in}
    table = pd.concat(rows, ignore_index=True)
    thin = au.set_index(["market", "year"])["thin"]
    table["thin_year"] = [bool(thin.get((m, y), False)) for m, y in zip(table["market"], table["year"])]
    io.write_table(table, out / "by_year.csv")

    verdict = {}
    for vid in IDS:
        nq, es = summary[f"NQ:{vid}"], summary[f"ES:{vid}"]
        verdict[vid] = {"nq_net": nq["net"], "nq_sharpe": nq["sharpe"], "es_net": es["net"], "es_sharpe": es["sharpe"],
                        "pass": bool(nq["net"] > 0 and nq["sharpe"] >= PASS_SHARPE and es["net"] > 0)}
    io.write_json({"rule": f"NQ net > 0 and NQ Sharpe >= {PASS_SHARPE} over the whole period, and ES net > 0",
                   "source": str(a.src.relative_to(ROOT)) if a.src.is_relative_to(ROOT) else str(a.src),
                   "warmup_end": str(warm_end), "nq_es_same_sessions": same_sessions,
                   "thin_years": {m: [int(y) for y in au[(au.market == m) & au.thin]["year"]] for m in ("NQ", "ES")},
                   "versions": summary, "verdict": verdict, **stamp()}, out / "summary.json")
    print(table.to_string(index=False))
    print(json.dumps({"summary": summary, "verdict": verdict}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
