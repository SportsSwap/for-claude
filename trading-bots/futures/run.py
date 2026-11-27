"""Run every futures bot on NQ and ES through the same validation as the
systematic bots, then report dollars per contract and QQQ/TQQQ equivalents.

    python3 -m futures.run            # everything
    python3 -m futures.run F05 F06    # some bots

Periods (as in the earlier PA Lab): in-sample 2011-2021 (settings picked here),
NEW 2022-01 to 2024-07 and FIN 2024-08 to 2026-11 (never used to pick).
"""
import json
import math
import sys
import time

import numpy as np
import pandas as pd

from engine import metrics as M
from engine import validate as V
from . import engine as E
from . import mdata as D
from .bots import REGISTRY, session

OUT = V.RESULTS / "futures"
OUT.mkdir(exist_ok=True)
IS_END = "2021-12-31"
PERIODS = {"IS 2011-2021": ("2011-01-01", "2021-12-31"), "NEW 2022-Jul 2024": ("2022-01-01", "2024-07-31"),
           "FIN Aug 2024-2026": ("2024-08-01", None), "OOS 2022-2026": ("2022-01-01", None)}


def parse(chosen, space):
    out = {}
    for part in chosen.split(","):
        k, v = part.split("=", 1)
        out[k] = next(x for x in space[k] if str(x) == v)
    return out


def lev_stats(r: pd.Series, lev: float) -> dict:
    """Compounded result of putting the whole account in each trade at `lev`x
    (QQQ = 1x, TQQQ ~ 3x of the index's move, ignoring TQQQ's fees and drag)."""
    x = (r * lev).clip(lower=-0.99)
    s = M.summary(x)
    return {"CAGR": s.get("CAGR"), "maxDD": s.get("maxDD"), "Sharpe": s.get("Sharpe")}


def main():
    only = sys.argv[1:]
    allout = []
    for spec in REGISTRY:
        if only and not any(spec["name"].startswith(o) for o in only):
            continue
        for sym in ("NQ", "ES"):
            t0 = time.time()
            fn = lambda p, cm, f=spec["fn"], s=sym: f(p, cm, s)
            daily = session(sym)["daily"]["close"]
            bench = daily.pct_change().fillna(0.0)
            name = f"{spec['name']} {sym}"
            out = V.study(name, fn, spec["space"], spec["default"], IS_END, benchmark=bench, notes=spec["notes"])
            p = parse(out["chosen"], spec["space"])
            res = spec["fn"](p, 1.0, sym)
            res2 = spec["fn"](p, 2.0, sym)
            resd = spec["fn"](spec["default"], 1.0, sym)
            t = res.raw_trades
            micro, mini = E.MICRO[sym], sym
            out["sym"] = sym
            out["contracts"] = {}
            for c in (micro, mini):
                out["contracts"][c] = {k: E.dollars(t, c, a, b) for k, (a, b) in PERIODS.items()}
                out["contracts"][c]["OOS 2022-2026 at 2x costs"] = E.dollars(res2.raw_trades, c, "2022-01-01", None, 2.0)
            out["default_contracts"] = {micro: {k: E.dollars(resd.raw_trades, micro, a, b) for k, (a, b) in PERIODS.items()}}
            r_oos = res.returns.loc["2022-01-01":]
            if sym == "NQ":
                out["etf_equivalent_oos"] = {"QQQ (1x)": lev_stats(r_oos, 1.0), "TQQQ (~3x)": lev_stats(r_oos, 3.0)}
            else:
                out["etf_equivalent_oos"] = {"SPY (1x)": lev_stats(r_oos, 1.0), "UPRO (~3x)": lev_stats(r_oos, 3.0)}
            yearly = {}
            if len(t):
                s_ = E.SPEC[micro]
                cost = np.array([E.cost_points(micro, int(v)) for v in t["slipped"]])
                pnl = (t["side"] * (t["exit"] - t["entry"]) - cost) * s_["usd"]
                yearly = pnl.groupby(pd.to_datetime(t["exit_time"]).dt.year).sum().round(0).to_dict()
            out["yearly_usd_micro"] = {str(k): v for k, v in yearly.items()}
            if len(t):
                t.to_csv(OUT / f"{name.lower().replace(' ', '_')}_trades.csv", index=False)
            allout.append(out)
            c = out["contracts"][micro]
            o = out["out_of_sample"]
            print(f"== {name}  chosen [{out['chosen']}]  default [{out['default']}]  grid {out['grid_size']}  ({time.time()-t0:.0f}s)")
            for per in PERIODS:
                d = c[per]
                if d.get("trades", 0) == 0:
                    print(f"   {per:20s} no trades"); continue
                print(f"   {per:20s} {micro} trades {d['trades']:5d}  ${d['usd_per_year']:>8,.0f}/yr  net ${d['net_usd']:>9,.0f}  win {d['win_rate']:.0%}  PF {d['profit_factor']:.2f}  maxDD ${d['max_dd_usd']:,.0f}  Sharpe {d['sharpe']:.2f}  yrs up {d['years_up']}")
            d2 = c["OOS 2022-2026 at 2x costs"]
            dflt = out["default_contracts"][micro]["OOS 2022-2026"]
            print(f"   OOS at 2x costs ${d2.get('usd_per_year', 0):,.0f}/yr | default setting OOS ${dflt.get('usd_per_year', 0):,.0f}/yr"
                  f" | DSR {o.get('DSR', float('nan')):.2f} PBO {out['pbo'].get('PBO', float('nan')):.2f} WF Sharpe {out['walk_forward'].get('Sharpe', float('nan')):.2f}"
                  f" | {list(out['etf_equivalent_oos'])[1]} CAGR {out['etf_equivalent_oos'][list(out['etf_equivalent_oos'])[1]]['CAGR']*100:.1f}%", flush=True)
    if not only:
        (OUT / "summary.json").write_text(json.dumps(allout, indent=1, default=str))
    else:
        prev = []
        try:
            prev = json.loads((OUT / "summary.json").read_text())
        except Exception:
            pass
        names = {o["name"] for o in allout}
        merged = [o for o in prev if o["name"] not in names] + allout
        (OUT / "summary.json").write_text(json.dumps(merged, indent=1, default=str))


if __name__ == "__main__":
    main()
