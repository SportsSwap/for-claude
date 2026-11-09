"""Engine check: 20,000 market entries at random discovery minutes, random
direction, a 1 ATR stop (5m ATR) and a 2R target, each trade on its own.
After costs they should lose a little (the reference lab got -$9.80 a trade).

    LAB_ROOT=... python scripts/random_entries.py [--peek-ahead MIN]

--peek-ahead is only for the deliberate cheat run (see decisions.md).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lab import engine, io  # noqa: E402
from lab.config import P, stamp  # noqa: E402
from lab.market import Market  # noqa: E402
from lab.seed import rng  # noqa: E402

N = 20_000


def random_orders(mk: Market, n: int, stream: str, peek: int = 0):
    g = rng(stream)
    ch = mk.charts["5m"]
    ok = mk.tradable[mk.sess] & ~mk.no_entry
    ok[-(peek + 2):] = False
    cand = np.flatnonzero(ok)
    t = np.sort(g.choice(cand, n, replace=False))
    i5 = np.searchsorted(ch.avail_ns, mk.ts_ns[t] + 60_000_000_000, side="right") - 1
    atr = ch.atr[np.maximum(i5, 0)]
    keep = (i5 >= 0) & np.isfinite(atr) & (atr > 0)
    t, atr = t[keep], atr[keep]
    if peek:
        side = np.where(mk.c[t + peek] >= mk.c[t], 1, -1)   # the cheat: looks 60 minutes ahead
    else:
        side = g.choice(np.array([-1, 1]), len(t))
    px = mk.c[t]
    size = mk.notional / (mk.pv * px) if getattr(mk, "notional", 0.0) else np.ones(len(t))
    return dict(t=t, side=side, stop=px - side * atr, target=px + side * 2 * atr, size=size)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--peek-ahead", type=int, default=0)
    ap.add_argument("--markets", default="NQ,ES")
    a = ap.parse_args(argv)
    name = "cheat_peek60" if a.peek_ahead else "random_entries"
    out = {}
    for m in a.markets.split(","):
        mk = Market.load(m)
        o = random_orders(mk, N, f"engine:{name}:{m}", a.peek_ahead)
        tr = engine.run(mk, o, independent=True)
        io.write_table(tr, P.results() / "engine" / f"{name}_{m}_trades.csv")
        out[m] = {"trades": int(len(tr)), "per_trade_dollars": round(float(tr.dollars.mean()), 2),
                  "total_dollars": round(float(tr.dollars.sum()), 2),
                  "win_rate": round(float((tr.dollars > 0).mean()), 4),
                  "per_trade_points_before_costs": round(float(((tr.exit_px - tr.entry_px) * tr.side).mean()), 3),
                  "exit_reasons": tr.reason.value_counts().to_dict()}
        print(m, out[m])
    io.write_json({"check": name, "n_requested": N, "stop": "1 ATR (5m)", "target": "2R",
                   "results": out, **stamp()}, P.results() / "engine" / f"{name}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
