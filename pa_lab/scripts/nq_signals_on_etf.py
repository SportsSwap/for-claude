"""Approach A: NQ decides, TQQQ (or SPXL from ES) trades. Discovery window only.

    python scripts/nq_signals_on_etf.py [--ids id,id,...] [--set candidates|survivors|sample]

For each version: build its orders on the futures market (data/clean in this lab,
warm-up + discovery only; the guard keeps the sealed window out), then move every
order onto the ETF:
  - it is acted on at the first ETF minute at or after the decision (signals after
    16:00 wait for the 09:30 open),
  - limit, stop and target are converted with the ETF's 3x leverage relative to the
    futures price at the moment the ETF acts,
  - time, limit-window and structure exits that fall outside ETF hours happen at the
    last ETF minute before them,
  - each trade is $10,000 of the ETF, no commission, 1 tick ($0.01) slippage.
Writes results/etf_execution/<set>_{NQ,ES}.csv in the ETF lab (tqqq_lab).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lab import engine, io  # noqa: E402
from lab import strategy as sg  # noqa: E402
from lab.charts import ORDER  # noqa: E402
from lab.config import stamp  # noqa: E402
from lab.market import Market  # noqa: E402

LEV = 3.0
FUT_ROOT = ROOT
ETF_ROOT = ROOT / "tqqq_lab"


def load(root: Path, name: str) -> Market:
    os.environ["LAB_ROOT"] = str(root)
    return Market.load(name)


def map_after(src_ns, dst_ns, idx):
    """First destination bar opening at or after the source bar's close."""
    idx = np.asarray(idx, np.int64)
    out = np.full(len(idx), -1, np.int64)
    ok = idx >= 0
    out[ok] = np.searchsorted(dst_ns, src_ns[idx[ok]] + 60_000_000_000, side="left")
    out[out >= len(dst_ns)] = -1
    return out


def map_before(src_ns, dst_ns, idx):
    """Last destination bar opening at or before the source bar."""
    idx = np.asarray(idx, np.int64)
    out = np.full(len(idx), -1, np.int64)
    ok = idx >= 0
    out[ok] = np.searchsorted(dst_ns, src_ns[idx[ok]], side="right") - 1
    return out


def to_etf(fut: Market, etf: Market, version: dict):
    o, extra = sg.orders(fut, version)
    if o is None or not len(o["t"]):
        return None, {}
    j = map_after(fut.ts_ns, etf.ts_ns, o["t"])                      # ETF bar where it is acted on
    k = np.searchsorted(fut.ts_ns, etf.ts_ns[np.maximum(j, 0)], side="right") - 1   # futures price then
    ok = (j >= 0) & (k >= 0)
    fut_now = fut.c[np.maximum(k, 0)]
    etf_now = etf.c[np.maximum(j, 0)]
    side = o["side"]
    conv = lambda p: etf_now * (1 + LEV * (p / fut_now - 1))  # noqa: E731
    stop = conv(o["stop"])
    target = np.where(np.isfinite(o["target"]), conv(o["target"]), np.nan)
    px = np.where(o["limit"], conv(o["px"]), etf_now)
    risk = side * (px - stop)
    ok &= np.isfinite(risk) & (risk >= etf.tick)
    # a limit must still be on the right side of the ETF price when placed
    ok &= ~o["limit"] | (side * (etf_now - px) > 0)
    te = map_before(fut.ts_ns, etf.ts_ns, o["time_exit"])
    le = map_before(fut.ts_ns, etf.ts_ns, o["lim_end"])
    ok &= (te > j)
    size = np.where(px > 0, etf.notional / (etf.pv * px), 0.0) * np.where(o["size"] < 1, 0.5, 1.0)
    out = dict(t=j, side=side, limit=o["limit"], px=px, lim_end=np.where(le > j, le, j), stop=stop,
               target=target, close_stop=o["close_stop"], use_struct=o["use_struct"], time_exit=te, size=size)
    out = {kk: np.asarray(vv)[ok] for kk, vv in out.items()}
    ex = {}
    if "trig_close" in extra:   # close-based stops: the ETF's own trigger-chart closes
        tc = version["trigger_chart"]
        mark = np.zeros(etf.n, bool)
        L = etf.charts[tc].last_1m
        mark[L[L >= 0]] = True
        ex["trig_close"] = mark
    if "struct_up" in extra:
        ex["struct_up"] = np.sort(np.unique(map_after(fut.ts_ns, etf.ts_ns, extra["struct_up"] - 1)))
        ex["struct_dn"] = np.sort(np.unique(map_after(fut.ts_ns, etf.ts_ns, extra["struct_dn"] - 1)))
        ex["struct_up"] = ex["struct_up"][ex["struct_up"] >= 0]
        ex["struct_dn"] = ex["struct_dn"][ex["struct_dn"] >= 0]
    return out, ex


def run_one(fut, etf, version):
    o, ex = to_etf(fut, etf, version)
    if o is None or not len(o["t"]):
        return {"trades": 0}
    tr = engine.run(etf, o, **ex)
    m = engine.metrics(etf, tr)
    d = engine.daily_pnl(etf, tr)
    for e in (1, 2):
        dm = etf.era[etf.tradable] == e
        m[f"net_era{e}"] = float(d[dm].sum())
        m[f"sharpe_era{e}"] = engine.sharpe(d[dm])
    return m


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="candidates", choices=["candidates", "survivors", "common", "all"])
    a = ap.parse_args(argv)
    vers = {json.loads(l)["id"]: json.loads(l) for l in open(FUT_ROOT / "results/funnel/versions.jsonl")}
    if a.set == "survivors":
        ids = ["C-breakout-00051", "C-fair_value_gap-00364"]
    elif a.set == "candidates":
        c = json.load(open(FUT_ROOT / "results/funnel/candidates.json"))["candidates"]
        ids = [x["id"] for x in c]
    elif a.set == "common":
        ids = [i for i, v in vers.items() if v.get("set") == "common"]
    else:
        ids = list(vers)
    skip = {"id", "set", "name", "nq_signals", "graded"}
    rows = []
    for fut_name in ("NQ", "ES"):
        fut = load(FUT_ROOT, fut_name)
        etf = load(ETF_ROOT, fut_name)
        for n, i in enumerate(ids):
            v = {k: x for k, x in vers[i].items() if k not in skip}
            sg.clear_cache()
            m = run_one(fut, etf, v)
            rows.append({"id": i, "signal_market": fut_name, "etf": "TQQQ" if fut_name == "NQ" else "SPXL", **m})
            if n % 25 == 24:
                print(f"  {fut_name} {n + 1}/{len(ids)}", flush=True)
    os.environ["LAB_ROOT"] = str(ETF_ROOT)
    df = pd.DataFrame(rows)
    out = ETF_ROOT / "results" / "etf_execution"
    out.mkdir(parents=True, exist_ok=True)
    io.write_table(df, out / f"{a.set}.csv")
    io.write_json({"set": a.set, "versions": len(ids), "window": "discovery only (warm-up excluded)", **stamp()},
                  out / f"{a.set}_meta.json")
    print(df.groupby("etf")[["trades", "net", "sharpe"]].describe().round(2).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
