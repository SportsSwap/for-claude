"""D46: walk-forward optimization and candidate baskets from saved daily P&L (no market data read)."""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lab import io
from lab.config import P, stamp

FAST = {"1m", "5m", "15m"}
MIN_EXIT_DAYS = 30

def matrix(m):
    parts = []
    for p in glob.glob(str(P.results() / f"funnel/daily/{m}/*.parquet")):
        parts.append(pd.read_parquet(p).rename(columns={"session": "day"})[["id", "day", "pnl"]])
    for p in glob.glob(str(P.results() / f"final/daily/{m}/*.parquet")):
        parts.append(pd.read_parquet(p)[["id", "day", "pnl"]])
    d = pd.concat(parts); d["day"] = pd.to_datetime(d["day"])
    return d.pivot_table(index="day", columns="id", values="pnl", aggfunc="sum").fillna(0.0).sort_index()

def sharpe(x):
    sd = x.std(ddof=1)
    return float(x.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0

def stats(x):
    eq = x.cumsum()
    return {"net": round(float(x.sum())), "sharpe": round(sharpe(x), 2), "max_drawdown": round(float((eq.cummax() - eq).max())),
            "exit_days": int((x != 0).sum())}

def main():
    vers = {json.loads(l)["id"]: json.loads(l) for l in open(P.results() / "funnel/versions.jsonl")}
    cand = [c["id"] for c in io.read_json(P.results() / "funnel/candidates.json")["candidates"]]
    out = {"declared": "decisions.md D46"}
    rows = []
    for m in ("NQ", "ES"):
        M = matrix(m)
        fast_ids = [i for i in M.columns if vers.get(i, {}).get("setup_chart") in FAST]
        starts = pd.date_range("2023-01-01", "2026-07-01", freq="6MS")
        oos = {"top1": [], "top10": [], "top10_fast": [], "median": []}
        for s in starts:
            tr = M[(M.index >= s - pd.DateOffset(months=12)) & (M.index < s)]
            te = M[(M.index >= s) & (M.index < s + pd.DateOffset(months=6))]
            if not len(te):
                continue
            ok = (tr != 0).sum() >= MIN_EXIT_DAYS
            sh = tr.loc[:, ok].apply(sharpe).sort_values(ascending=False)
            top1, top10 = sh.index[0], sh.index[:10]
            shf = sh[[i for i in sh.index if i in set(fast_ids)]]
            top10f = shf.index[:10]
            oos["top1"].append(te[top1]); oos["top10"].append(te[top10].mean(axis=1))
            oos["top10_fast"].append(te[top10f].mean(axis=1)); oos["median"].append(te.median(axis=1))
            rows.append({"market": m, "test_from": str(s.date()), "top1_id": top1, "top1_train_sharpe": round(sh.iloc[0], 2),
                         "top1_test_net": round(float(te[top1].sum())), "top10_test_net": round(float(te[top10].mean(axis=1).sum())),
                         "top10_fast_test_net": round(float(te[top10f].mean(axis=1).sum())),
                         "share_of_versions_profitable": round(float((te.sum() > 0).mean()), 3)})
        out[m] = {"walk_forward_unseen_2023_to_2026": {k: stats(pd.concat(v)) for k, v in oos.items()}}
        fin = M[M.index >= "2024-08-01"]
        c_all = [i for i in cand if i in fin.columns]
        c_fast = [i for i in c_all if vers[i]["setup_chart"] in FAST]
        out[m]["baskets_final_window"] = {
            "all_candidates": {"versions": len(c_all), **stats(fin[c_all].mean(axis=1)), "exits_per_day_across_basket": round(float((fin[c_all] != 0).sum(axis=1).mean()), 2)},
            "fast_candidates": {"versions": len(c_fast), **stats(fin[c_fast].mean(axis=1)), "exits_per_day_across_basket": round(float((fin[c_fast] != 0).sum(axis=1).mean()), 2)}}
    io.write_table(pd.DataFrame(rows), P.results() / "analysis" / "walk_forward_folds.csv")
    io.write_json({**out, **stamp()}, P.results() / "analysis" / "walk_forward_and_baskets.json")
    print(pd.DataFrame(rows).to_string(index=False)); print(json.dumps(out, indent=1))

main()
