"""Walk-forward optimization: does picking the best version actually pay on data it has not seen?

    python scripts/walk_forward_etf.py [--workers 4] [--etf NQ|ES]

Every version in results/funnel/versions.jsonl is traded on the ETF (NQ signals -> TQQQ,
or ES signals -> SPXL; see scripts/nq_signals_on_etf.py) over the discovery window only.
Folds: optimize on a training stretch, trade the pick on the next six months unseen.
  train 2022-01-01..2022-12-31 -> test 2023-01-01..2023-06-30
  train 2022-07-01..2023-06-30 -> test 2023-07-01..2023-12-31
  train 2023-01-01..2023-12-31 -> test 2024-01-01..2024-07-31
For each fold: the single best version by training Sharpe (at least MIN_TRADES trades), the
top 10 averaged, and the median of all versions, each measured on the unseen test months.
Writes tqqq_lab/results/walk_forward/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from lab import engine, io  # noqa: E402
from lab import strategy as sg  # noqa: E402
from lab.config import stamp  # noqa: E402
import nq_signals_on_etf as ne  # noqa: E402

D = dt.date
FOLDS = [((D(2022, 1, 1), D(2022, 12, 31)), (D(2023, 1, 1), D(2023, 6, 30))),
         ((D(2022, 7, 1), D(2023, 6, 30)), (D(2023, 7, 1), D(2023, 12, 31))),
         ((D(2023, 1, 1), D(2023, 12, 31)), (D(2024, 1, 1), D(2024, 7, 31)))]
MIN_TRADES = 10
ACCOUNT = 10_000.0   # one $10,000 position at a time = returns as a % of a $10k account
SKIP = {"id", "set", "name", "nq_signals", "graded"}
_G = {}


def _init(slot):
    _G["fut"] = ne.load(ne.FUT_ROOT, slot)
    _G["etf"] = ne.load(ne.ETF_ROOT, slot)


def _work(rec):
    fut, etf = _G["fut"], _G["etf"]
    sg.clear_cache()
    v = {k: x for k, x in rec.items() if k not in SKIP}
    try:
        o, ex = ne.to_etf(fut, etf, v)
        if o is None or not len(o["t"]):
            return rec["id"], None, None
        tr = engine.run(etf, o, **ex)
        d = engine.daily_pnl(etf, tr)
        n_by_day = tr.groupby("exit_session").size().reindex(d.index, fill_value=0)
        return rec["id"], d.to_numpy(np.float32), n_by_day.to_numpy(np.int16)
    except Exception as e:  # noqa: BLE001
        return rec["id"], None, str(e)


def stats(pnl: np.ndarray) -> tuple[float, float]:
    sd = pnl.std(ddof=1)
    return float(pnl.sum()), float(pnl.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--etf", default="NQ", choices=["NQ", "ES"])
    a = ap.parse_args(argv)
    recs = [json.loads(l) for l in open(ne.FUT_ROOT / "results/funnel/versions.jsonl")]
    t0 = time.time()
    _init(a.etf)
    days = pd.Index(_G["etf"].sessions[_G["etf"].tradable])
    ctx = mp.get_context("fork")
    ids, P, N, errors = [], [], [], 0
    with ctx.Pool(a.workers, initializer=_init, initargs=(a.etf,)) as pool:
        for i, (vid, pnl, n) in enumerate(pool.imap_unordered(_work, recs, chunksize=8)):
            if pnl is None:
                errors += isinstance(n, str)
            else:
                ids.append(vid); P.append(pnl); N.append(n)
            if i % 250 == 249:
                print(f"  {i + 1}/{len(recs)} versions ({time.time() - t0:.0f}s)", flush=True)
    P, N = np.vstack(P), np.vstack(N)
    os.environ["LAB_ROOT"] = str(ne.ETF_ROOT)
    out = ne.ETF_ROOT / "results" / "walk_forward"
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / f"daily_{a.etf}.npz", pnl=P, trades=N, ids=np.array(ids), days=np.array([str(d) for d in days]))
    dd = np.array(days)
    rows, oos_best, oos_top10, oos_median = [], [], [], []
    for (tr0, tr1), (te0, te1) in FOLDS:
        trm = (dd >= tr0) & (dd <= tr1)
        tem = (dd >= te0) & (dd <= te1)
        n_tr = N[:, trm].sum(axis=1)
        sh_tr = np.array([stats(p[trm])[1] for p in P])
        sh_tr[n_tr < MIN_TRADES] = -np.inf
        order = np.argsort(-sh_tr)
        best = order[0]
        top10 = order[:10]
        net_te_all = P[:, tem].sum(axis=1)
        b_net, b_sh = stats(P[best, tem])
        rows.append({"train": f"{tr0}..{tr1}", "test": f"{te0}..{te1}", "best_id": ids[best],
                     "best_train_sharpe": round(float(sh_tr[best]), 2),
                     "best_train_net": round(float(P[best, trm].sum()), 0),
                     "best_test_net": round(b_net, 0), "best_test_sharpe": round(b_sh, 2),
                     "best_test_trades": int(N[best, tem].sum()),
                     "top10_test_net_mean": round(float(net_te_all[top10].mean()), 0),
                     "all_test_net_median": round(float(np.median(net_te_all)), 0),
                     "share_versions_profitable_in_test": round(float((net_te_all > 0).mean()), 3)})
        oos_best.append(P[best, tem]); oos_top10.append(P[top10][:, tem].mean(axis=0)); oos_median.append(np.median(P[:, tem], axis=0))
    table = pd.DataFrame(rows)
    io.write_table(table, out / f"folds_{a.etf}.csv")
    ob, ot, om = (np.concatenate(x) for x in (oos_best, oos_top10, oos_median))
    summary = {"etf": "TQQQ" if a.etf == "NQ" else "SPXL", "versions": len(ids), "errors": errors,
               "unseen_months": "2023-01 .. 2024-07 (three folds)",
               "best_pick_unseen_net": round(float(ob.sum()), 0), "best_pick_unseen_return_pct": round(float(ob.sum() / ACCOUNT * 100), 1),
               "best_pick_unseen_sharpe": round(stats(ob)[1], 2),
               "top10_unseen_net": round(float(ot.sum()), 0), "top10_unseen_sharpe": round(stats(ot)[1], 2),
               "median_version_unseen_net": round(float(om.sum()), 0),
               "wall_seconds": round(time.time() - t0), **stamp()}
    io.write_json(summary, out / f"summary_{a.etf}.json")
    print(table.to_string(index=False))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
