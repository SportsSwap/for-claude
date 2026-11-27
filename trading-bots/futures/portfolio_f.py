"""Contract portfolio of the futures bots that passed: 1 micro contract per bot.
Out-of-sample only (2022-2026). Reports dollars, drawdown and how many
contracts are open at the same time (which sets the margin you need)."""
import json

import numpy as np
import pandas as pd

from portfolio import grade
from engine.validate import RESULTS
from . import engine as E

OUT = RESULTS / "futures"


def main():
    S = json.loads((OUT / "summary.json").read_text())
    rows, members = [], []
    for o in S:
        g = grade(o)
        c = o["contracts"][E.MICRO[o["sym"]]]["OOS 2022-2026"]
        rows.append((o["name"], g, c.get("usd_per_year", 0), c.get("profit_factor", 0), c.get("trades", 0)))
        if g in ("A", "B"):
            members.append(o)
    print("Grades:")
    for r in rows:
        print(f"  {r[1]}  {r[0]:32s} ${r[2]:>8,.0f}/yr  PF {r[3]:.2f}  trades {r[4]}")
    pnl, open_ = {}, {}
    days = pd.bdate_range("2022-01-01", "2026-11-13")
    for o in members:
        micro = E.MICRO[o["sym"]]
        t = pd.read_csv(OUT / f"{o['name'].lower().replace(' ', '_')}_trades.csv", parse_dates=["entry_time", "exit_time"])
        t = t[t["entry_time"] >= "2022-01-01"]
        s = E.SPEC[micro]
        cost = np.array([E.cost_points(micro, int(v)) for v in t["slipped"]])
        usd = (t["side"] * (t["exit"] - t["entry"]) - cost) * s["usd"]
        pnl[o["name"]] = usd.groupby(t["exit_time"].dt.normalize().values).sum().reindex(days).fillna(0.0)
        held = pd.Series(0, index=days)
        for a, b in zip(t["entry_time"].dt.normalize(), t["exit_time"].dt.normalize()):
            held.loc[a:b] += 1
        open_[o["name"]] = held
    P = pd.DataFrame(pnl)
    tot = P.sum(axis=1)
    eq = tot.cumsum()
    dd = (eq - eq.cummax()).min()
    yearly = tot.groupby(tot.index.year).sum()
    years = (days[-1] - days[0]).days / 365.25
    held = pd.DataFrame(open_).sum(axis=1)
    out = {"members": list(P.columns), "usd_per_year": float(tot.sum() / years), "net_usd": float(tot.sum()),
           "max_dd_usd": float(dd), "sharpe": float(tot.mean() / tot.std() * np.sqrt(252)),
           "yearly_usd": {int(k): round(float(v)) for k, v in yearly.items()},
           "max_contracts_open": int(held.max()), "avg_contracts_open": float(held.mean()),
           "corr": P.corr().round(2).to_dict()}
    print("\nMembers (1 micro each):", out["members"])
    print(f"Portfolio 2022-2026: ${out['usd_per_year']:,.0f}/yr, net ${out['net_usd']:,.0f}, max DD ${dd:,.0f}, "
          f"Sharpe {out['sharpe']:.2f}, max contracts open {out['max_contracts_open']}, avg {out['avg_contracts_open']:.1f}")
    print("Yearly:", out["yearly_usd"])
    (OUT / "portfolio.json").write_text(json.dumps(out, indent=1))
    P.assign(total=tot).cumsum().to_csv(OUT / "portfolio_equity_usd.csv")


if __name__ == "__main__":
    main()
